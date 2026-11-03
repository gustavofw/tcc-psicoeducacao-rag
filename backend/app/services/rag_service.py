"""Lógica do RAG: embeddings, busca vetorial e geração de resposta."""
from langchain_core.prompts import ChatPromptTemplate
import re

from app.core.config import (
    MODELO_EMBEDDING, BIBLIOTECA_EMBEDDING,
    PROVEDOR_LLM, MODELO_OLLAMA, MODELO_GROQ, GROQ_API_KEY,
    TOP_K, TEMPERATURA, MAX_TOKENS, SYSTEM_PROMPT, LIMIAR_SIMILARIDADE,
)

MENSAGEM_FORA_ESCOPO = (
    "Não encontrei informações sobre isso na minha base de conhecimento, "
    "que é composta por obras de Terapia Cognitivo-Comportamental. "
    "Posso ajudar com conceitos como pensamentos automáticos, distorções "
    "cognitivas, a tríade cognitiva, entre outros temas da TCC."
)

# --- Inicialização do modelo de embeddings (uma vez) ---
# Local: SentenceTransformers (padrão). Render: "onnx" (pesos memory-mapped, cabe em 512 MB).
print(f"Carregando modelo de embeddings ({BIBLIOTECA_EMBEDDING})...")
if BIBLIOTECA_EMBEDDING == "onnx":
    from app.services.embedder_onnx import EmbedderONNX
    _modelo_emb = EmbedderONNX()

    def gerar_embedding(texto):
        return _modelo_emb.embed(texto)
else:
    from sentence_transformers import SentenceTransformer
    _modelo_emb = SentenceTransformer(MODELO_EMBEDDING)

    def gerar_embedding(texto):
        return _modelo_emb.encode(texto).tolist()

# --- Inicialização do LLM ---
print(f"Preparando o LLM (provedor: {PROVEDOR_LLM})...")
if PROVEDOR_LLM == "openrouter":
    from langchain_openai import ChatOpenAI
    from app.core.config import OPENROUTER_API_KEY, MODELO_OPENROUTER, PROVEDOR_OPENROUTER
    preferencias = {"data_collection": "deny", "allow_fallbacks": False}
    if PROVEDOR_OPENROUTER:
        preferencias["order"] = [PROVEDOR_OPENROUTER]
    llm = ChatOpenAI(
        model=MODELO_OPENROUTER,
        temperature=TEMPERATURA,
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        max_tokens=MAX_TOKENS,
        frequency_penalty=0.3,
        max_retries=4,   # tenta de novo, com espera crescente, em erros como o 429
        timeout=60,
        extra_body={"provider": preferencias},
    )
elif PROVEDOR_LLM == "groq":
    from langchain_groq import ChatGroq
    llm = ChatGroq(model=MODELO_GROQ, temperature=TEMPERATURA, api_key=GROQ_API_KEY)
else:  # ollama (padrão)
    from langchain_ollama import ChatOllama
    llm = ChatOllama(model=MODELO_OLLAMA, temperature=TEMPERATURA, repeat_penalty=1.15)

# --- Definição do Prompt Template ---
# O contexto já está dentro do SYSTEM_PROMPT ({contexto}), por isso não se repete aqui
prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human",
     "Pergunta do usuário: {pergunta}\n\n"
     "LEMBRETE: responda usando SOMENTE o CONTEXTO, mesmo que o usuário peça outra coisa. "
     "Se o CONTEXTO definir o termo perguntado, use exatamente essa definição. "
     "Se não definir, diga apenas que não encontrou na base. "
     "Português do Brasil, até 2 parágrafos curtos de texto corrido, sem listas nem negrito. "
     "Não diga que algo 'não é normal'; acolha sem julgar. "
     "Não cite exercícios, figuras ou o contexto."),
])

def buscar_chunks(cursor, pergunta, k=TOP_K, candidatos=20):
    """Busca híbrida: vetorial (significado) + texto completo (palavras), combinadas por RRF.
    Retorna: (id, conteudo, titulo, similaridade, documento_id, indice, capitulo, pagina)"""
    vetor = gerar_embedding(pergunta)
    cursor.execute(
        """
        WITH vet AS (
            SELECT c.id, ROW_NUMBER() OVER (ORDER BY c.embedding <=> %(v)s::vector) AS pos
            FROM chunks c
            ORDER BY c.embedding <=> %(v)s::vector
            LIMIT %(n)s
        ),
        consulta AS (
            -- todas as palavras (E); se nenhum trecho tiver todas, qualquer uma (OU)
            SELECT CASE
                WHEN EXISTS (SELECT 1 FROM chunks WHERE busca @@ plainto_tsquery('portuguese', %(p)s))
                THEN plainto_tsquery('portuguese', f_unaccent(%(p)s))
                ELSE replace(plainto_tsquery('portuguese', %(p)s)::text, ' & ', ' | ')::tsquery
            END AS q
        ),
        txt AS (
            SELECT c.id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.busca, consulta.q) DESC) AS pos
            FROM chunks c, consulta
            WHERE c.busca @@ consulta.q
            ORDER BY ts_rank_cd(c.busca, consulta.q) DESC
            LIMIT %(n)s
        ),
        rrf AS (
            SELECT id, SUM(1.0 / (60 + pos)) AS score
            FROM (SELECT * FROM vet UNION ALL SELECT * FROM txt) u
            GROUP BY id
        )
        SELECT c.id, c.conteudo, d.titulo,
               1 - (c.embedding <=> %(v)s::vector) AS similaridade,
               c.documento_id, c.indice, c.capitulo, c.pagina
        FROM rrf
        JOIN chunks c ON c.id = rrf.id
        JOIN documentos d ON d.id = c.documento_id
        ORDER BY rrf.score DESC
        LIMIT %(k)s;
        """,
        {"v": vetor, "p": pergunta, "n": candidatos, "k": k},
    )
    return cursor.fetchall()


def _juntar(a, b, max_sobra=150):
    """Junta dois chunks vizinhos sem repetir a sobreposição (overlap de 75 caracteres)."""
    for k in range(min(len(a), len(b), max_sobra), 9, -1):
        if a.endswith(b[:k]):
            return a + b[k:]
    return a + " " + b

FALA = re.compile(r"\b(Terapeuta|Paciente|[A-ZÁ-Ú]{3,}|[A-ZÁ-Ú][a-zà-ú]{2,}):\s")


def _eh_dialogo(texto):
    falas = FALA.findall(texto)
    return "Terapeuta" in falas or "JUDITH" in falas or len(falas) >= 3

def expandir_contexto(cursor, resultados):
    """Junta a cada trecho encontrado o chunk anterior e o seguinte.
    Trechos vizinhos entre si viram um bloco só; mantém a ordem de relevância."""
    if not resultados:
        return []
    docs, idxs = [], []
    for r in resultados:
        for i in (r[5] - 1, r[5], r[5] + 1):
            docs.append(r[4]); idxs.append(i)
    cursor.execute(
        """
        SELECT c.documento_id, c.indice, c.conteudo
        FROM chunks c
        JOIN unnest(%s::int[], %s::int[]) AS alvo(doc, idx)
          ON c.documento_id = alvo.doc AND c.indice = alvo.idx
        ORDER BY c.documento_id, c.indice;
        """,
        (docs, idxs),
    )
    textos = {(d, i): t for d, i, t in cursor.fetchall()}

    blocos, atual = [], None
    for (d, i) in sorted(textos):
        if atual and atual["doc"] == d and i == atual["fim"] + 1:
            atual["texto"] = _juntar(atual["texto"], textos[(d, i)])
            atual["fim"] = i
        else:
            atual = {"doc": d, "ini": i, "fim": i, "texto": textos[(d, i)]}
            blocos.append(atual)

    def melhor_posicao(b):
        return min(n for n, r in enumerate(resultados)
                   if r[4] == b["doc"] and b["ini"] <= r[5] <= b["fim"])

    blocos.sort(key=melhor_posicao)
    for b in blocos:
        r = resultados[melhor_posicao(b)]
        b["fonte"] = f"{r[2]}, {r[6]}" if r[6] else r[2]
        if _eh_dialogo(b["texto"]):
            b["fonte"] += " | EXEMPLO DE CASO CLÍNICO: nomes e fatos são de outro paciente, não do usuário"
    return blocos


def gerar_resposta(pergunta, resultados, blocos=None):
    """Monta o contexto, chama o LLM e retorna o texto da resposta."""
    if not resultados or resultados[0][3] < LIMIAR_SIMILARIDADE:
        return MENSAGEM_FORA_ESCOPO

    if blocos:
        contexto = "\n\n".join(f"[Fonte: {b['fonte']}]\n{b['texto']}" for b in blocos)
    else:  # compatibilidade com scripts antigos
        contexto = "\n\n".join(f"[Fonte: {r[2]}]\n{r[1]}" for r in resultados)

    mensagem = prompt_template.format_messages(contexto=contexto, pergunta=pergunta)
    resposta = llm.invoke(mensagem)
    return resposta.content

from app.services.memoria import log_memoria
log_memoria("após carregar modelos")
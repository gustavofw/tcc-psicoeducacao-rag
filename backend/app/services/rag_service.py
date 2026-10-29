"""Lógica do RAG: embeddings, busca vetorial e geração de resposta."""
from langchain_core.prompts import ChatPromptTemplate

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
        extra_body={"provider": preferencias},
    )
elif PROVEDOR_LLM == "groq":
    from langchain_groq import ChatGroq
    llm = ChatGroq(model=MODELO_GROQ, temperature=TEMPERATURA, api_key=GROQ_API_KEY)
else:  # ollama (padrão)
    from langchain_ollama import ChatOllama
    llm = ChatOllama(model=MODELO_OLLAMA, temperature=TEMPERATURA)

# --- Definição do Prompt Template ---
# O contexto já está dentro do SYSTEM_PROMPT ({contexto}), por isso não se repete aqui
prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "Pergunta: {pergunta}")
])


def buscar_chunks(cursor, pergunta, k=TOP_K):
    """Busca os k trechos mais parecidos com a pergunta no pgvector."""
    vetor = gerar_embedding(pergunta)
    cursor.execute(
        """
        SELECT c.id, c.conteudo, d.titulo, 1 - (c.embedding <=> %s::vector) AS similaridade
        FROM chunks c
        JOIN documentos d ON d.id = c.documento_id
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s;
        """,
        (vetor, vetor, k),
    )
    return cursor.fetchall()


def gerar_resposta(pergunta, resultados):
    """Monta o contexto, chama o LLM e retorna o texto da resposta."""
    # Verifica o limiar: se o melhor resultado está abaixo, não gera resposta
    if not resultados or resultados[0][3] < LIMIAR_SIMILARIDADE:
        return MENSAGEM_FORA_ESCOPO

    contexto = "\n\n".join(
        f"[Trecho {i} - Fonte: {titulo}]\n{conteudo}"
        for i, (cid, conteudo, titulo, sim) in enumerate(resultados, 1)
    )

    mensagem = prompt_template.format_messages(contexto=contexto, pergunta=pergunta)
    resposta = llm.invoke(mensagem)
    return resposta.content

from app.services.memoria import log_memoria
log_memoria("após carregar modelos")
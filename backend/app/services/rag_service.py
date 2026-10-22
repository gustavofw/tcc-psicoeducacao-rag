"""Lógica do RAG: embeddings, busca vetorial e geração de resposta."""
from sentence_transformers import SentenceTransformer
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import (
    MODELO_EMBEDDING, PROVEDOR_LLM, MODELO_OLLAMA, MODELO_GROQ, GROQ_API_KEY,
    TOP_K, TEMPERATURA, MAX_TOKENS, SYSTEM_PROMPT, LIMIAR_SIMILARIDADE,
)

MENSAGEM_FORA_ESCOPO = (
    "Não encontrei informações sobre isso na minha base de conhecimento, "
    "que é composta por obras de Terapia Cognitivo-Comportamental. "
    "Posso ajudar com conceitos como pensamentos automáticos, distorções "
    "cognitivas, a tríade cognitiva, entre outros temas da TCC."
)

# --- Inicialização (uma vez) ---
print("Carregando modelo de embeddings...")
modelo_emb = SentenceTransformer(MODELO_EMBEDDING)

print(f"Preparando o LLM (provedor: {PROVEDOR_LLM})...")
if PROVEDOR_LLM == "openrouter":
    from langchain_openai import ChatOpenAI
    from app.core.config import OPENROUTER_API_KEY, MODELO_OPENROUTER
    llm = ChatOpenAI(
        model=MODELO_OPENROUTER,
        temperature=TEMPERATURA,
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )
elif PROVEDOR_LLM == "groq":
    from langchain_groq import ChatGroq
    llm = ChatGroq(model=MODELO_GROQ, temperature=TEMPERATURA, api_key=GROQ_API_KEY)
else:  # ollama (padrão)
    from langchain_ollama import ChatOllama
    llm = ChatOllama(model=MODELO_OLLAMA, temperature=TEMPERATURA)

# --- Definição do Prompt Template ---
prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "Contexto:\n{contexto}\n\nPergunta: {pergunta}")
])


def buscar_chunks(cursor, pergunta, k=TOP_K):
    """Busca os k trechos mais parecidos com a pergunta no pgvector."""
    vetor = modelo_emb.encode(pergunta).tolist()
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

    # Corrigido o erro de formatação e quebra de linha da string
    contexto = "\n\n".join(
        f"[Trecho {i} - Fonte: {titulo}]\n{conteudo}"
        for i, (cid, conteudo, titulo, sim) in enumerate(resultados, 1)
    )
    
    mensagem = prompt_template.format_messages(contexto=contexto, pergunta=pergunta)
    resposta = llm.invoke(mensagem)
    return resposta.content
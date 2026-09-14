"""
============================================================
rag.py - Pipeline RAG Completo (Fase 2)
============================================================

Este script executa o pipeline RAG COMPLETO, unindo tudo:
a busca vetorial (que já validamos) + a geração de resposta
pelo Llama 3.1.

As 6 etapas do RAG (conforme o TCC):
  1. Recebe a pergunta do usuário
  2. Gera o embedding da pergunta (modelo multilíngue)
  3. Busca no pgvector os trechos mais parecidos
  4. Recupera os top-K trechos de Beck
  5. Monta o prompt (trechos + pergunta + instruções de segurança)
  6. O Llama 3.1 gera a resposta final, fundamentada nos trechos

Como usar:
  python rag.py
============================================================
"""

import psycopg2
from sentence_transformers import SentenceTransformer
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

# ------------------------------------------------------------
# CONFIGURAÇÕES
# ------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "psicoedu",
    "user": "postgres",
    "password": "tcc2026",
}

# Modelo de embeddings (o multilíngue que validamos)
MODELO_EMBEDDING = "paraphrase-multilingual-MiniLM-L12-v2"

# Modelo de linguagem no Ollama
MODELO_LLM = "llama3.1"

# Quantos trechos recuperar para fundamentar a resposta
TOP_K = 4

# Temperatura do modelo: valores baixos deixam a resposta mais
# focada e consistente (menos "criativa"). O TCC define ~0.3.
TEMPERATURA = 0.3


# ------------------------------------------------------------
# O PROMPT DO SISTEMA - as "regras" que o Llama deve seguir
# ------------------------------------------------------------
# Aqui está o coração da segurança e do escopo do seu sistema.
# Estas instruções garantem que o Llama:
#   - responda SÓ com base nos trechos de Beck (anti-alucinação)
#   - se mantenha na psicoeducação, sem diagnosticar (RF06)
#   - não invente informações
SYSTEM_PROMPT = """Você é um assistente de psicoeducação em saúde mental, \
fundamentado na Terapia Cognitivo-Comportamental de Aaron Beck.

REGRAS OBRIGATÓRIAS:
1. Responda SOMENTE com base nos trechos fornecidos abaixo (CONTEXTO). \
Não invente informações nem use conhecimento externo.
2. Se os trechos não contiverem informação suficiente para responder, \
diga honestamente que não possui essa informação na base de conhecimento.
3. Você faz PSICOEDUCAÇÃO: explica conceitos de forma clara e informativa. \
Você NÃO faz diagnósticos, NÃO prescreve tratamentos e NÃO substitui um profissional.
4. Use uma linguagem acolhedora, clara e acessível.
5. Responda em português do Brasil.

CONTEXTO (trechos recuperados da obra de Beck):
{contexto}
"""

# O template da mensagem do usuário
USER_PROMPT = "Pergunta: {pergunta}"


# ------------------------------------------------------------
# Buscar os chunks mais parecidos (etapa de recuperação)
# ------------------------------------------------------------
def buscar_chunks(cursor, modelo, pergunta, k=TOP_K):
    """Gera o embedding da pergunta e busca os k trechos mais próximos."""
    vetor_pergunta = modelo.encode(pergunta).tolist()
    cursor.execute(
        """
        SELECT
            c.conteudo,
            d.titulo,
            c.id,
            1 - (c.embedding <=> %s::vector) AS similaridade
        FROM chunks c
        JOIN documentos d ON d.id = c.documento_id
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s;
        """,
        (vetor_pergunta, vetor_pergunta, k),
    )
    return cursor.fetchall()


# ------------------------------------------------------------
# Montar o texto de contexto a partir dos chunks recuperados
# ------------------------------------------------------------
def montar_contexto(resultados):
    """Junta os trechos recuperados em um único texto para o prompt."""
    partes = []
    for i, (conteudo, titulo, chunk_id, sim) in enumerate(resultados, 1):
        partes.append(f"[Trecho {i} - Fonte: {titulo}]\n{conteudo}")
    return "\n\n".join(partes)


# ------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():
    # --- Carrega o modelo de embeddings ---
    print("Carregando o modelo de embeddings...")
    modelo_emb = SentenceTransformer(MODELO_EMBEDDING)
    print("Modelo de embeddings carregado.")

    # --- Prepara o Llama via Ollama ---
    print(f"Conectando ao Llama ({MODELO_LLM}) via Ollama...")
    llm = ChatOllama(model=MODELO_LLM, temperature=TEMPERATURA)
    print("Llama pronto.")

    # --- Prepara o template do prompt ---
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])

    # --- Conecta ao banco ---
    print("Conectando ao banco...")
    conexao = psycopg2.connect(**DB_CONFIG)
    cursor = conexao.cursor()
    print("Conectado.\n")

    print("=" * 60)
    print("  AGENTE DE PSICOEDUCAÇÃO (RAG completo)")
    print("  Faça uma pergunta sobre TCC. (digite 'sair' para encerrar)")
    print("=" * 60)

    while True:
        print()
        pergunta = input("Você: ").strip()
        if pergunta.lower() in ("sair", "exit", "quit", ""):
            break

        # ETAPA 2, 3, 4: buscar e recuperar os trechos
        resultados = buscar_chunks(cursor, modelo_emb, pergunta)
        contexto = montar_contexto(resultados)

        # ETAPA 5: montar o prompt final
        mensagem = prompt.format_messages(contexto=contexto, pergunta=pergunta)

        # ETAPA 6: o Llama gera a resposta
        print("\nAgente: ", end="", flush=True)
        resposta = llm.invoke(mensagem)
        print(resposta.content)

        # Mostra as fontes usadas (rastreabilidade!)
        print("\n   [Fontes consultadas:]")
        for i, (conteudo, titulo, chunk_id, sim) in enumerate(resultados, 1):
            print(f"   - Trecho {i} (chunk {chunk_id}, sim {sim:.3f}): {titulo}")

    cursor.close()
    conexao.close()
    print("\nEncerrado.")


if __name__ == "__main__":
    main()
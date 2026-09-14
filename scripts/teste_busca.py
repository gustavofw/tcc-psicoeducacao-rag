"""
============================================================
teste_busca.py - Teste da Busca Vetorial (Fase 1 do RAG)
============================================================

Este script testa APENAS a etapa de recuperação (retrieval) do RAG.
Ainda NÃO usa o Llama — o objetivo aqui é provar que a busca por
similaridade no pgvector está funcionando e trazendo os trechos
certos de Beck.

O que ele faz:
  1. Recebe uma pergunta (digitada por você)
  2. Transforma a pergunta em vetor (all-MiniLM-L6-v2)
  3. Pede ao pgvector os chunks mais parecidos (similaridade de cosseno)
  4. Mostra os trechos recuperados, do mais parecido ao menos parecido

Como usar:
  python teste_busca.py
============================================================
"""

import psycopg2
from sentence_transformers import SentenceTransformer

# ------------------------------------------------------------
# CONFIGURAÇÕES
# ------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,            # porta do container Docker
    "dbname": "psicoedu",
    "user": "postgres",
    "password": "tcc2026",
}

MODELO_EMBEDDING = "paraphrase-multilingual-MiniLM-L12-v2"

# Quantos trechos recuperar (o "K" do top-K)
TOP_K = 4


# ------------------------------------------------------------
# Buscar os chunks mais parecidos com a pergunta
# ------------------------------------------------------------
def buscar_chunks(cursor, modelo, pergunta, k=TOP_K):
    """
    Transforma a pergunta em vetor e busca no pgvector os k chunks
    mais próximos usando similaridade de cosseno.
    """
    # 1. Gera o embedding da pergunta (vetor de 384 números)
    vetor_pergunta = modelo.encode(pergunta).tolist()

    # 2. Busca no banco.
    #    O operador <=> do pgvector calcula a DISTÂNCIA de cosseno.
    #    Distância menor = mais parecido. Por isso ordenamos por <=> crescente.
    #    Convertemos distância em "similaridade" (1 - distância) só para exibir
    #    um número mais intuitivo (perto de 1 = muito parecido).
    cursor.execute(
        """
        SELECT
            c.conteudo,
            d.titulo,
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
# PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():
    print("Carregando o modelo de embeddings...")
    modelo = SentenceTransformer(MODELO_EMBEDDING)
    print("Modelo carregado.\n")

    print("Conectando ao banco...")
    conexao = psycopg2.connect(**DB_CONFIG)
    cursor = conexao.cursor()
    print("Conectado.\n")

    print("=" * 60)
    print("  TESTE DE BUSCA VETORIAL - Base de conhecimento (Beck)")
    print("  Digite uma pergunta e veja os trechos recuperados.")
    print("  (digite 'sair' para encerrar)")
    print("=" * 60)

    while True:
        print()
        pergunta = input("Sua pergunta: ").strip()

        if pergunta.lower() in ("sair", "exit", "quit", ""):
            break

        resultados = buscar_chunks(cursor, modelo, pergunta)

        if not resultados:
            print("Nenhum trecho encontrado.")
            continue

        print(f"\n--- {len(resultados)} trechos mais relevantes ---")
        for i, (conteudo, titulo, similaridade) in enumerate(resultados, 1):
            # mostra só os primeiros 300 caracteres de cada trecho, para não poluir
            trecho = conteudo[:300].replace("\n", " ")
            print(f"\n[{i}] Similaridade: {similaridade:.3f}  |  Fonte: {titulo}")
            print(f"    {trecho}...")

    cursor.close()
    conexao.close()
    print("\nEncerrado.")


if __name__ == "__main__":
    main()
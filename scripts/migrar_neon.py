"""
============================================================
migrar_neon.py - Copia a base de conhecimento para o Neon
============================================================
Copia as tabelas 'documentos' e 'chunks' do banco local (Docker)
para o banco em nuvem (Neon). As tabelas 'sessoes' e 'mensagens'
não são copiadas (ficam vazias no Neon).

Pré-requisitos:
  - Docker com o banco local rodando
  - Estrutura (CREATE TABLE) já criada no SQL Editor do Neon

Como usar (PowerShell, na pasta do projeto):
  $env:NEON_URL = "postgresql://...neon.tech/neondb?sslmode=require"
  python scripts\\migrar_neon.py
============================================================
"""
import os
import psycopg2
from psycopg2.extras import execute_values

# --- Destino: Neon (string passada só pelo PowerShell, não fica no .env) ---
NEON_URL = os.getenv("NEON_URL")
if not NEON_URL or "neon.tech" not in NEON_URL:
    raise SystemExit("Defina a variável NEON_URL no PowerShell antes de rodar.")

# --- Origem: banco local (Docker) ---
LOCAL = {
    "host": "localhost",
    "port": 5433,
    "dbname": "psicoedu",
    "user": "postgres",
    "password": "tcc2026",
}


def main():
    print("Conectando ao banco local...")
    origem = psycopg2.connect(**LOCAL)
    co = origem.cursor()

    print("Conectando ao Neon...")
    destino = psycopg2.connect(NEON_URL)
    cd = destino.cursor()

    # Evita duplicar os dados se o script for rodado duas vezes
    cd.execute("SELECT count(*) FROM chunks;")
    if cd.fetchone()[0] > 0:
        raise SystemExit("O Neon já tem chunks. Nada foi feito.")

    # 1. Documentos (mantém os mesmos ids, para os chunks apontarem certo)
    co.execute(
        "SELECT id, titulo, fonte, autor, data_indexacao, total_chunks "
        "FROM documentos ORDER BY id;"
    )
    docs = co.fetchall()
    execute_values(
        cd,
        "INSERT INTO documentos (id, titulo, fonte, autor, data_indexacao, total_chunks) VALUES %s",
        docs,
    )
    print(f"{len(docs)} documentos copiados.")

    # 2. Chunks (o embedding sai como texto e é convertido para vector no Neon)
    co.execute(
        "SELECT id, documento_id, conteudo, indice, embedding::text, tokens, data_criacao "
        "FROM chunks ORDER BY id;"
    )
    chunks = co.fetchall()
    execute_values(
        cd,
        "INSERT INTO chunks (id, documento_id, conteudo, indice, embedding, tokens, data_criacao) VALUES %s",
        chunks,
        template="(%s, %s, %s, %s, %s::vector, %s, %s)",
        page_size=200,
    )
    print(f"{len(chunks)} chunks copiados.")

    # 3. Ajusta os contadores de id para continuar depois do maior id copiado
    cd.execute("SELECT setval('documentos_id_seq', (SELECT MAX(id) FROM documentos));")
    cd.execute("SELECT setval('chunks_id_seq', (SELECT MAX(id) FROM chunks));")

    destino.commit()

    # 4. Conferência
    cd.execute("SELECT count(*) FROM documentos;")
    total_docs = cd.fetchone()[0]
    cd.execute("SELECT count(*) FROM chunks;")
    total_chunks = cd.fetchone()[0]
    print(f"Conferência no Neon: {total_docs} documentos, {total_chunks} chunks.")

    co.close(); cd.close()
    origem.close(); destino.close()
    print("Migração concluída.")


if __name__ == "__main__":
    main()
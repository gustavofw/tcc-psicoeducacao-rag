"""
============================================================
revetorizar_fastembed.py - Gera de novo os embeddings no Neon
============================================================
Na nuvem (Render), a API usa a biblioteca fastembed (ONNX), que
consome menos memória. Para que pergunta e trechos sejam
convertidos do mesmo jeito, os vetores do Neon são gerados de
novo com o fastembed. O banco local (Docker) NÃO é alterado.

Antes de gravar, o script compara os vetores antigos
(SentenceTransformers) com os novos (fastembed) e mostra a
similaridade, para registro no artigo.

Como usar (PowerShell, na pasta do projeto):
  $env:NEON_URL = "postgresql://...neon.tech/neondb?sslmode=require"
  python scripts\\revetorizar_fastembed.py
============================================================
"""
import os
import numpy as np
import psycopg2
from psycopg2.extras import execute_batch
from fastembed import TextEmbedding

NEON_URL = os.getenv("NEON_URL")
if not NEON_URL or "neon.tech" not in NEON_URL:
    raise SystemExit("Defina a variável NEON_URL no PowerShell antes de rodar.")

MODELO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def main():
    print("Conectando ao Neon...")
    conexao = psycopg2.connect(NEON_URL)
    cursor = conexao.cursor()

    cursor.execute("SELECT id, conteudo, embedding::text FROM chunks ORDER BY id;")
    linhas = cursor.fetchall()
    if not linhas:
        raise SystemExit("Nenhum chunk no Neon. Rode o migrar_neon.py primeiro.")
    print(f"{len(linhas)} chunks carregados.")

    print("Gerando novos embeddings (fastembed)...")
    modelo = TextEmbedding(MODELO)
    novos = list(modelo.embed([l[1] for l in linhas], batch_size=64))

    # Comparação antigo x novo (similaridade de cosseno)
    sims = []
    for (_, _, antigo_txt), novo in zip(linhas, novos):
        antigo = np.array([float(x) for x in antigo_txt.strip("[]").split(",")])
        sims.append(np.dot(antigo, novo) / (np.linalg.norm(antigo) * np.linalg.norm(novo)))
    sims = np.array(sims)
    print(
        f"Similaridade antigo x novo: média={sims.mean():.4f}  "
        f"mínima={sims.min():.4f}  desvio={sims.std():.4f}"
    )

    resp = input("Sobrescrever os embeddings no Neon? (s/n) ")
    if resp.strip().lower() == "s":
        dados = [(str(v.tolist()), l[0]) for l, v in zip(linhas, novos)]
        execute_batch(
            cursor,
            "UPDATE chunks SET embedding = %s::vector WHERE id = %s;",
            dados,
            page_size=200,
        )
        conexao.commit()
        print("Embeddings atualizados no Neon.")
    else:
        print("Nada foi alterado.")

    cursor.close()
    conexao.close()


if __name__ == "__main__":
    main()
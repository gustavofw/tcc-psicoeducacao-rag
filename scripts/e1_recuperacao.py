"""
============================================================
e1_recuperacao.py - Experimento 1 (Qualidade da Recuperação)
============================================================
Compara o modelo original (TCC 1) com o multilíngue (adotado)
nas 20 perguntas-padrão, usando a base do Neon (busca exata).

Etapa 1 - gerar a planilha de julgamento (pooling dos top-5):
  $env:NEON_URL = "postgresql://...neon.tech/neondb?sslmode=require"
  py scripts\\e1_recuperacao.py gerar
  -> preencher a coluna "relevante (S/N)" em e1_julgamento.csv

Etapa 2 - calcular Hit@3, Hit@5 e MRR:
  py scripts\\e1_recuperacao.py avaliar
============================================================
"""
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np
import psycopg2
from sentence_transformers import SentenceTransformer

PASTA = Path(__file__).resolve().parent
MODELOS = {
    "multilingue": "paraphrase-multilingual-MiniLM-L12-v2",  # adotado
    "original": "paraphrase-MiniLM-L12-v2",                   # TCC 1 (confira o nome)
}
K = 5
ARQ_JULGAMENTO = PASTA / "e1_julgamento.csv"


def carregar_chunks():
    url = os.getenv("NEON_URL")
    if not url or "neon.tech" not in url:
        raise SystemExit("Defina $env:NEON_URL no PowerShell antes de rodar.")
    con = psycopg2.connect(url)
    cur = con.cursor()
    cur.execute(
        "SELECT c.id, d.titulo, c.conteudo FROM chunks c "
        "JOIN documentos d ON d.id = c.documento_id ORDER BY c.id;"
    )
    linhas = cur.fetchall()
    con.close()
    print(f"{len(linhas)} chunks carregados do Neon.")
    return linhas


def vetores_chunks(nome, modelo, textos):
    """Gera (ou reaproveita do cache) os vetores de todos os chunks."""
    cache = PASTA / f"e1_cache_{nome}.npy"
    if cache.exists():
        v = np.load(cache)
        if len(v) == len(textos):
            print(f"[{nome}] vetores carregados do cache.")
            return v
    print(f"[{nome}] gerando vetores de {len(textos)} chunks (alguns minutos)...")
    v = modelo.encode(textos, batch_size=64, show_progress_bar=True,
                      normalize_embeddings=True)
    np.save(cache, v)
    return v


def gerar():
    perguntas = json.loads(
        (PASTA / "perguntas_testes.json").read_text(encoding="utf-8")
    )["E1_E2"]
    chunks = carregar_chunks()
    ids = [c[0] for c in chunks]
    textos = [c[2] for c in chunks]

    # (indice_pergunta, indice_chunk) -> {modelo: (posicao, similaridade)}
    ranking = {}
    for nome, caminho in MODELOS.items():
        modelo = SentenceTransformer(caminho)
        V = vetores_chunks(nome, modelo, textos)
        Q = modelo.encode(perguntas, normalize_embeddings=True)
        sims = Q @ V.T  # similaridade de cosseno (vetores normalizados)
        for qi in range(len(perguntas)):
            for pos, idx in enumerate(np.argsort(-sims[qi])[:K], 1):
                ranking.setdefault((qi, int(idx)), {})[nome] = (pos, float(sims[qi, idx]))

    def ordem(item):
        (qi, _), info = item
        return (qi, min(p for p, _ in info.values()))

    with open(ARQ_JULGAMENTO, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["n", "pergunta", "chunk_id", "obra", "trecho"]
                   + [f"pos_{m}" for m in MODELOS] + ["relevante (S/N)"])
        for (qi, idx), info in sorted(ranking.items(), key=ordem):
            w.writerow(
                [qi + 1, perguntas[qi], ids[idx], chunks[idx][1],
                 textos[idx].replace("\n", " ")]
                + [info.get(m, ("",))[0] for m in MODELOS]
                + [""]
            )
    print(f"\nPlanilha gerada: {ARQ_JULGAMENTO}")
    print("Preencha a coluna 'relevante (S/N)' e rode: py scripts\\e1_recuperacao.py avaliar")


def ler_julgamento():
    for codificacao in ("utf-8-sig", "cp1252"):  # o Excel pode salvar em cp1252
        try:
            with open(ARQ_JULGAMENTO, encoding=codificacao) as f:
                return list(csv.DictReader(f, delimiter=";"))
        except UnicodeDecodeError:
            continue
    raise SystemExit("Não consegui ler o CSV (codificação).")


def avaliar():
    linhas = ler_julgamento()
    col = "relevante (S/N)"
    faltando = [l for l in linhas if l[col].strip().upper() not in ("S", "N")]
    if faltando:
        raise SystemExit(f"{len(faltando)} linhas sem S/N preenchido.")

    perguntas = sorted({l["n"] for l in linhas}, key=int)
    total = len(perguntas)
    print(f"\nPerguntas avaliadas: {total} | trechos julgados: {len(linhas)}")
    print(f"Trechos relevantes: {sum(l[col].strip().upper() == 'S' for l in linhas)}\n")

    for m in MODELOS:
        hit3 = hit5 = 0
        rr = 0.0
        for n in perguntas:
            posicoes = [int(l[f"pos_{m}"]) for l in linhas
                        if l["n"] == n and l[f"pos_{m}"]
                        and l[col].strip().upper() == "S"]
            melhor = min(posicoes) if posicoes else None
            if melhor and melhor <= 3:
                hit3 += 1
            if melhor and melhor <= 5:
                hit5 += 1
            if melhor:
                rr += 1 / melhor
        print(f"{m:12} Hit@3={hit3 / total:.0%}  Hit@5={hit5 / total:.0%}  "
              f"MRR@5={rr / total:.3f}")


if __name__ == "__main__":
    etapa = sys.argv[1] if len(sys.argv) > 1 else ""
    if etapa == "gerar":
        gerar()
    elif etapa == "avaliar":
        avaliar()
    else:
        print("Uso: py scripts\\e1_recuperacao.py gerar | avaliar")
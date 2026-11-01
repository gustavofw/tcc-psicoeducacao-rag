"""
============================================================
e1_recuperacao.py - Experimento 1 (Qualidade da Recuperação)
============================================================
Compara três modelos de embeddings nas 20 perguntas-padrão,
usando a base do Neon (busca exata, similaridade de cosseno):
  - multilingue : paraphrase-multilingual-MiniLM-L12-v2 (adotado)
  - all_L6      : all-MiniLM-L6-v2 (previsto no projeto do TCC 1)
  - para_L12    : paraphrase-MiniLM-L12-v2 (versão monolíngue do adotado)

Etapa 1 - gerar a planilha (aproveita os julgamentos já feitos):
  $env:NEON_URL = "postgresql://...neon.tech/neondb?sslmode=require"
  py scripts\\e1_recuperacao.py gerar
  -> preencher só as linhas em LARANJA de e1_julgamento_v2.xlsx

Etapa 2 - calcular Hit@3, Hit@5 e MRR dos três modelos:
  py scripts\\e1_recuperacao.py avaliar
============================================================
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

PASTA = Path(__file__).resolve().parent
# nome: (modelo, arquivo de cache)
MODELOS = {
    "multilingue": ("paraphrase-multilingual-MiniLM-L12-v2", "e1_cache_multilingue.npy"),
    "all_L6": ("all-MiniLM-L6-v2", "e1_cache_all_L6.npy"),
    "para_L12": ("paraphrase-MiniLM-L12-v2", "e1_cache_original.npy"),
}
K = 5
ARQ_ANTERIOR = PASTA / "e1_julgamento_preenchido.xlsx"  # julgamentos já feitos
ARQ_NOVO = PASTA / "e1_julgamento_v2.xlsx"
ARQ_NOVO_PREENCHIDO = PASTA / "e1_julgamento_v2_preenchida.xlsx"  # se existir, é o usado no avaliar
COL_REL = "relevante (S/N)"


def carregar_chunks():
    import psycopg2
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
    cache = PASTA / MODELOS[nome][1]
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


def ler_xlsx(caminho):
    from openpyxl import load_workbook
    ws = load_workbook(caminho, data_only=True).active
    linhas = list(ws.iter_rows(values_only=True))
    cab = [str(c) for c in linhas[0]]
    return [
        {c: ("" if v is None else str(v)) for c, v in zip(cab, l)}
        for l in linhas[1:] if l and l[0] is not None
    ]


def julgamentos_anteriores():
    if not ARQ_ANTERIOR.exists():
        print("Aviso: e1_julgamento_preenchido.xlsx não encontrado; nada será aproveitado.")
        return {}
    j = {}
    for l in ler_xlsx(ARQ_ANTERIOR):
        v = l.get(COL_REL, "").strip().upper()
        if v in ("S", "N"):
            j[(int(float(l["n"])), int(float(l["chunk_id"])))] = v
    print(f"{len(j)} julgamentos anteriores aproveitados.")
    return j


def gerar():
    from sentence_transformers import SentenceTransformer
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, PatternFill, Font, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    perguntas = json.loads(
        (PASTA / "perguntas_testes.json").read_text(encoding="utf-8")
    )["E1_E2"]
    chunks = carregar_chunks()
    ids = [c[0] for c in chunks]
    textos = [c[2] for c in chunks]

    ranking = {}  # (qi, idx) -> {modelo: posicao}
    for nome, (caminho, _) in MODELOS.items():
        modelo = SentenceTransformer(caminho)
        V = vetores_chunks(nome, modelo, textos)
        Q = modelo.encode(perguntas, normalize_embeddings=True)
        sims = Q @ V.T
        for qi in range(len(perguntas)):
            for pos, idx in enumerate(np.argsort(-sims[qi])[:K], 1):
                ranking.setdefault((qi, int(idx)), {})[nome] = pos

    anteriores = julgamentos_anteriores()
    itens = sorted(ranking.items(), key=lambda it: (it[0][0], min(it[1].values())))

    wb = Workbook()
    ws = wb.active
    ws.title = "Julgamento E1"
    cab = ["n", "pergunta", "obra", "trecho", COL_REL, "chunk_id"] + [f"pos_{m}" for m in MODELOS]
    ws.append(cab)
    azul = PatternFill("solid", fgColor="305496")
    faixa = [PatternFill("solid", fgColor="FFFFFF"), PatternFill("solid", fgColor="EAF1FB")]
    laranja = PatternFill("solid", fgColor="F8CBAD")
    borda = Border(bottom=Side(style="thin", color="BFBFBF"))
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = azul
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")

    novos = 0
    for (qi, idx), info in itens:
        n = qi + 1
        valor = anteriores.get((n, ids[idx]), "")
        ws.append([n, perguntas[qi], chunks[idx][1], textos[idx].replace("\n", " "),
                   valor, ids[idx]] + [info.get(m) for m in MODELOS])
        linha = ws[ws.max_row]
        for c in linha:
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.fill = faixa[n % 2]
            c.border = borda
        linha[4].alignment = Alignment(horizontal="center", vertical="center")
        if valor == "":
            novos += 1
            for c in linha[:5]:
                c.fill = laranja

    for col, w in {"A": 5, "B": 30, "C": 22, "D": 95, "E": 14, "F": 9, "G": 9, "H": 9, "I": 9}.items():
        ws.column_dimensions[col].width = w
    for col in "FGHI":
        ws.column_dimensions[col].hidden = True
    dv = DataValidation(type="list", formula1='"S,N"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"E2:E{ws.max_row}")
    ws.freeze_panes = "E2"
    ws.auto_filter.ref = f"A1:E{ws.max_row}"
    wb.save(ARQ_NOVO)
    print(f"\nPlanilha gerada: {ARQ_NOVO}")
    print(f"Linhas totais: {len(itens)} | já julgadas: {len(itens) - novos} | NOVAS para julgar (laranja): {novos}")


def avaliar():
    arquivo = ARQ_NOVO_PREENCHIDO if ARQ_NOVO_PREENCHIDO.exists() else ARQ_NOVO
    print(f"Lendo: {arquivo.name}")
    linhas = ler_xlsx(arquivo)
    faltando = [l for l in linhas if l[COL_REL].strip().upper() not in ("S", "N")]
    if faltando:
        raise SystemExit(f"{len(faltando)} linhas sem S/N preenchido.")
    perguntas = sorted({int(float(l["n"])) for l in linhas})
    total = len(perguntas)
    print(f"\nPerguntas: {total} | trechos julgados: {len(linhas)} | "
          f"relevantes: {sum(l[COL_REL].strip().upper() == 'S' for l in linhas)}\n")
    for m in MODELOS:
        hit3 = hit5 = 0
        rr = 0.0
        for n in perguntas:
            pos = [int(float(l[f"pos_{m}"])) for l in linhas
                   if int(float(l["n"])) == n and l[f"pos_{m}"]
                   and l[COL_REL].strip().upper() == "S"]
            melhor = min(pos) if pos else None
            hit3 += bool(melhor and melhor <= 3)
            hit5 += bool(melhor and melhor <= 5)
            rr += 1 / melhor if melhor else 0
        print(f"{m:12} {MODELOS[m][0]:40} Hit@3={hit3 / total:.0%}  "
              f"Hit@5={hit5 / total:.0%}  MRR@5={rr / total:.3f}")


if __name__ == "__main__":
    etapa = sys.argv[1] if len(sys.argv) > 1 else ""
    if etapa == "gerar":
        gerar()
    elif etapa == "avaliar":
        avaliar()
    else:
        print("Uso: py scripts\\e1_recuperacao.py gerar | avaliar")

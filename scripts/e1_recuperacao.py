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
  -> preencher só as linhas em LARANJA de e1_julgamento_v3.xlsx
     e salvar como e1_julgamento_v3_preenchida.xlsx

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
CONFIGS = list(MODELOS) + ["hibrida"]
# julgamentos já feitos (base antiga): reaproveitados por semelhança de texto
ARQS_ANTERIORES = [PASTA / "e1_julgamento_preenchido.xlsx", PASTA / "e1_julgamento_v2_preenchida.xlsx"]
ARQ_NOVO = PASTA / "e1_julgamento_v3.xlsx"
ARQ_NOVO_PREENCHIDO = PASTA / "e1_julgamento_v3_preenchida.xlsx"  # se existir, é o usado no avaliar
SEMELHANCA_MIN = 0.75  # trecho novo "igual" a um já julgado
# busca do sistema publicado (híbrida: vetorial + texto, RRF), com o modelo adotado
SQL_HIBRIDA = """
WITH vet AS (
    SELECT c.id, ROW_NUMBER() OVER (ORDER BY c.embedding <=> %(v)s::vector) AS pos
    FROM chunks c ORDER BY c.embedding <=> %(v)s::vector LIMIT 20),
consulta AS (
    SELECT CASE
        WHEN EXISTS (SELECT 1 FROM chunks WHERE busca @@ plainto_tsquery('portuguese', f_unaccent(%(p)s)))
        THEN plainto_tsquery('portuguese', f_unaccent(%(p)s))
        ELSE replace(plainto_tsquery('portuguese', f_unaccent(%(p)s))::text, ' & ', ' | ')::tsquery
    END AS q),
txt AS (
    SELECT c.id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.busca, consulta.q) DESC) AS pos
    FROM chunks c, consulta WHERE c.busca @@ consulta.q
    ORDER BY ts_rank_cd(c.busca, consulta.q) DESC LIMIT 20),
rrf AS (
    SELECT id, SUM(1.0 / (60 + pos)) AS score
    FROM (SELECT * FROM vet UNION ALL SELECT * FROM txt) u GROUP BY id)
SELECT id FROM rrf ORDER BY score DESC LIMIT 5;
"""
COL_REL = "relevante (S/N)"


def conectar():
    import psycopg2
    url = os.getenv("NEON_URL")
    if not url or "neon.tech" not in url:
        raise SystemExit("Defina $env:NEON_URL no PowerShell antes de rodar.")
    return psycopg2.connect(url, keepalives=1, keepalives_idle=30,
                            keepalives_interval=10, keepalives_count=5)


def carregar_chunks():
    con = conectar()
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


def _norm(t):
    return " ".join(str(t).lower().split())


def julgamentos_anteriores():
    """{n: [(texto_normalizado, 'S'/'N'), ...]} com os julgamentos já feitos."""
    j = {}
    for arq in ARQS_ANTERIORES:
        if not arq.exists():
            continue
        for l in ler_xlsx(arq):
            v = l.get(COL_REL, "").strip().upper()
            if v in ("S", "N"):
                j.setdefault(int(float(l["n"])), []).append((_norm(l["trecho"]), v))
    print(f"{sum(len(v) for v in j.values())} julgamentos anteriores disponíveis.")
    return j


def reaproveitar(anteriores, n, texto):
    """Valor do julgamento de um trecho antigo quase igual (mesma pergunta), ou ''."""
    from difflib import SequenceMatcher
    alvo = _norm(texto)
    melhor, valor = 0.0, ""
    for antigo, v in anteriores.get(n, []):
        if alvo == antigo:
            return v
        r = SequenceMatcher(None, alvo, antigo, autojunk=False).ratio()
        if r > melhor:
            melhor, valor = r, v
    return valor if melhor >= SEMELHANCA_MIN else ""


def gerar():
    from sentence_transformers import SentenceTransformer
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, PatternFill, Font, Border, Side
    from openpyxl.worksheet.datavalidation import DataValidation

    dados = json.loads((PASTA / "perguntas_testes.json").read_text(encoding="utf-8"))
    perguntas = dados["E1_E2"] + dados["E1b_E2b"]   # 1-20 técnicas, 21-40 leigas (E1b)
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
        if nome == "multilingue":
            # busca híbrida do sistema publicado, no Neon
            pos_id = {cid: i for i, cid in enumerate(ids)}
            con = conectar(); cur = con.cursor()
            for qi in range(len(perguntas)):
                cur.execute(SQL_HIBRIDA, {"v": str(Q[qi].tolist()), "p": perguntas[qi]})
                for pos, (cid,) in enumerate(cur.fetchall(), 1):
                    ranking.setdefault((qi, pos_id[cid]), {})["hibrida"] = pos
            con.close()

    anteriores = julgamentos_anteriores()
    itens = sorted(ranking.items(), key=lambda it: (it[0][0], min(it[1].values())))

    wb = Workbook()
    ws = wb.active
    ws.title = "Julgamento E1"
    cab = ["n", "pergunta", "obra", "trecho", COL_REL, "chunk_id"] + [f"pos_{m}" for m in CONFIGS]
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
        valor = reaproveitar(anteriores, n, textos[idx]) if n <= 20 else ""
        ws.append([n, perguntas[qi], chunks[idx][1], textos[idx].replace("\n", " "),
                   valor, ids[idx]] + [info.get(m) for m in CONFIGS])
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

    for col, w in {"A": 5, "B": 30, "C": 22, "D": 95, "E": 14, "F": 9, "G": 9, "H": 9, "I": 9, "J": 9}.items():
        ws.column_dimensions[col].width = w
    for col in "FGHIJ":
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
    nomes = {"multilingue": MODELOS["multilingue"][0] + " (vetorial)",
             "all_L6": MODELOS["all_L6"][0] + " (vetorial)",
             "para_L12": MODELOS["para_L12"][0] + " (vetorial)",
             "hibrida": "sistema: híbrida (multilíngue + texto, RRF)"}
    for rotulo, faixa in [("E1 - perguntas técnicas (1-20)", range(1, 21)),
                          ("E1b - perguntas leigas (21-40)", range(21, 41))]:
        perguntas = sorted({int(float(l["n"])) for l in linhas} & set(faixa))
        if not perguntas:
            continue
        total = len(perguntas)
        print(f"\n{rotulo}: {total} perguntas")
        for m in CONFIGS:
            hit3 = hit5 = 0
            rr = 0.0
            for n in perguntas:
                pos = [int(float(l[f"pos_{m}"])) for l in linhas
                       if int(float(l["n"])) == n and l.get(f"pos_{m}")
                       and l[COL_REL].strip().upper() == "S"]
                melhor = min(pos) if pos else None
                hit3 += bool(melhor and melhor <= 3)
                hit5 += bool(melhor and melhor <= 5)
                rr += 1 / melhor if melhor else 0
            print(f"  {nomes[m]:58} Hit@3={hit3 / total:.0%}  Hit@5={hit5 / total:.0%}  MRR@5={rr / total:.3f}")


if __name__ == "__main__":
    etapa = sys.argv[1] if len(sys.argv) > 1 else ""
    if etapa == "gerar":
        gerar()
    elif etapa == "avaliar":
        avaliar()
    else:
        print("Uso: py scripts\\e1_recuperacao.py gerar | avaliar")

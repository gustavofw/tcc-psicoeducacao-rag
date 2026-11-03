"""
============================================================
ingestao_v2.py - Base de conhecimento limpa (Fase 2, parecer 31/10)
============================================================
O que muda em relação ao ingestao.py:
  1. Só as páginas de conteúdo de cada obra (sem capa, sumário,
     apêndices, referências e índice).
  2. Remove cabeçalhos/rodapés repetidos e linhas só com número de página.
  3. Descarta chunks que são lista de referências bibliográficas.
  4. Guarda a página do PDF e o CAPÍTULO de cada chunk
     (novas colunas chunks.pagina e chunks.capitulo).
  5. Títulos amigáveis em 'documentos' (aparecem nas fontes do chat).

Como usar (PowerShell, na pasta scripts):
  Neon:   $env:NEON_URL = "postgresql://...neon.tech/neondb?sslmode=require"
          py ingestao_v2.py --destino neon
  Local:  py ingestao_v2.py --destino local
  Só simular (não grava nada): py ingestao_v2.py --simular

Os embeddings são gerados ANTES de conectar ao banco
(evita a conexão do Neon cair por inatividade).
============================================================
"""
import os, re, sys, bisect, argparse, unicodedata
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

PASTA_PDFS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "backend", "data", "obras_beck")

LOCAL = {"host": "localhost", "port": 5433, "dbname": "psicoedu",
         "user": "postgres", "password": "tcc2026"}

MODELO_EMBEDDING = "paraphrase-multilingual-MiniLM-L12-v2"
TAMANHO_CHUNK, OVERLAP_CHUNK = 500, 75

# usar=True/False decide se a obra entra na base.
# ini/fim = páginas do PDF (contagem do leitor, começando em 1).
OBRAS = [
    {"usar": True, "prefixo": "Aprendendo_a",
     "titulo": "Wright et al. (2019) – Aprendendo a terapia cognitivo-comportamental: um guia ilustrado",
     "autor": "Jesse H. Wright et al.", "ini": 20, "fim": 170},
    {"usar": True, "prefixo": "JUDITH BECK",
     "titulo": "Beck (2022) – Terapia cognitivo-comportamental: teoria e prática",
     "autor": "Judith S. Beck", "ini": 28, "fim": 643},
    {"usar": False, "prefixo": "terapia-cognitiva-teoria",
     "titulo": "Beck (2007) – Terapia cognitiva: teoria e prática",
     "autor": "Judith S. Beck", "ini": 12, "fim": 316},
    {"usar": False, "prefixo": "terapia-cognitiva-de-beck",
     "titulo": "Wills (2021) – Terapia cognitiva de Beck",
     "autor": "Frank Wills", "ini": 1, "fim": 26},
]

CABECALHOS = [r"^\s*\d+\s*$",                          # só número de página
              r"^\s*\d+\s+Terapia Cognitiva\s*$",       # Beck 2007
              r"^\s*Judith S\. Beck\s+\d+\s*$"]         # Beck 2007

REF_AUT = re.compile(r"\b[A-ZÁ-Ú][a-zà-ú\-]+,?\s(?:[A-Z]\.\s?){1,3}[,;&:(]"
                     r"|\b[A-ZÁ-Ú][a-zà-ú\-]+\s[A-Z]{1,3}[,:]")
ANO = re.compile(r"\(?\b(19|20)\d{2}[a-z]?\)?")


def eh_referencia(t):
    return len(ANO.findall(t)) >= 2 and len(REF_AUT.findall(t)) >= 3


def titulo_capitulo(linhas):
    """Página de abertura de capítulo: 1ª linha é o número, depois o título (pode quebrar)."""
    t, j = linhas[1].strip(), 2
    while j < len(linhas) and j < 5:
        prox = linhas[j].strip()
        if t.endswith("-"):
            t += prox
        elif t.endswith(":") or (len(prox) < 45 and prox[:1].islower() and not prox.endswith(".")):
            t += " " + prox
        else:
            break
        j += 1
    return re.sub(r"\[NT\]", "", t).strip()


def acha_pdf(prefixo):
    for f in os.listdir(PASTA_PDFS):   # NFC: o "ª" do nome vem decomposto
        if unicodedata.normalize("NFC", f).startswith(prefixo):
            return os.path.join(PASTA_PDFS, f)
    raise SystemExit(f"PDF não encontrado: {prefixo}*")


def processar(obra, splitter):
    leitor = PdfReader(acha_pdf(obra["prefixo"]))
    texto, inicios, paginas, capitulos = "", [], [], []
    cap = None
    for p in range(obra["ini"], obra["fim"] + 1):
        t = leitor.pages[p - 1].extract_text() or ""
        linhas = [l for l in t.splitlines() if l.strip()]
        if len(linhas) > 1 and re.fullmatch(r"\s*\d{1,2}\s*", linhas[0]):
            cap = f"cap. {linhas[0].strip()} – {titulo_capitulo(linhas)}"
        t = "\n".join(l for l in t.splitlines()
                      if not any(re.match(c, l) for c in CABECALHOS))
        inicios.append(len(texto)); paginas.append(p); capitulos.append(cap)
        texto += t + "\n"
    docs = splitter.create_documents([texto])
    chunks, descartados = [], 0
    for d in docs:
        if eh_referencia(d.page_content):
            descartados += 1
            continue
        pos = bisect.bisect_right(inicios, d.metadata["start_index"]) - 1
        chunks.append((d.page_content, paginas[pos], capitulos[pos]))
    return chunks, descartados


def conferir_dependencias(cur):
    """Mostra se alguma tabela depende de chunks/documentos (o TRUNCATE CASCADE apagaria)."""
    cur.execute("""
        SELECT conrelid::regclass::text, confrelid::regclass::text
        FROM pg_constraint WHERE contype='f'
          AND confrelid::regclass::text IN ('chunks','documentos')""")
    outras = [r for r in cur.fetchall() if r[0] not in ("chunks",)]
    if outras:
        raise SystemExit(f"Outras tabelas dependem da base: {outras}. Nada foi feito.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--destino", choices=["neon", "local"])
    ap.add_argument("--simular", action="store_true")
    a = ap.parse_args()
    if not a.simular and not a.destino:
        raise SystemExit("Use --destino neon, --destino local ou --simular.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=TAMANHO_CHUNK, chunk_overlap=OVERLAP_CHUNK,
        separators=["\n\n", "\n", ". ", " ", ""], add_start_index=True)

    base = []
    for obra in [o for o in OBRAS if o["usar"]]:
        chunks, desc = processar(obra, splitter)
        caps = sorted({c[2] for c in chunks if c[2]}, key=lambda x: int(x.split()[1]))
        for c in caps: print("   ", c)
        print(f"{obra['titulo'][:45]:45} págs {obra['ini']}-{obra['fim']}: "
              f"{len(chunks)} chunks ({desc} de referências descartados)")
        base.append((obra, chunks))
    print("TOTAL:", sum(len(c) for _, c in base), "chunks")
    if a.simular:
        return

    from sentence_transformers import SentenceTransformer
    modelo = SentenceTransformer(MODELO_EMBEDDING)
    vetores = [modelo.encode([c[0] for c in chunks], show_progress_bar=True,
                             batch_size=64) for _, chunks in base]

    import psycopg2
    from psycopg2.extras import execute_values
    def conectar():
        if a.destino == "neon":
            url = os.getenv("NEON_URL")
            if not url or "neon.tech" not in url:
                raise SystemExit("Defina $env:NEON_URL antes de rodar.")
            return psycopg2.connect(url, keepalives=1, keepalives_idle=30,
                                    keepalives_interval=10, keepalives_count=5)
        return psycopg2.connect(**LOCAL)

    con = conectar(); cur = con.cursor()
    conferir_dependencias(cur)
    cur.execute("SELECT count(*) FROM chunks")
    print(f"\nO banco '{a.destino}' tem {cur.fetchone()[0]} chunks que serão APAGADOS.")
    con.close()   # fecha enquanto espera a resposta (o Neon derruba conexão parada)
    if input("Digite SIM para continuar: ").strip() != "SIM":
        raise SystemExit("Cancelado.")

    con = conectar(); cur = con.cursor()
    cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS pagina INTEGER")
    cur.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS capitulo TEXT")
    cur.execute("CREATE INDEX IF NOT EXISTS chunks_doc_indice ON chunks (documento_id, indice)")
    cur.execute("TRUNCATE documentos RESTART IDENTITY CASCADE")
    for (obra, chunks), vets in zip(base, vetores):
        cur.execute("INSERT INTO documentos (titulo, fonte, autor) VALUES (%s,%s,%s) RETURNING id",
                    (obra["titulo"], os.path.basename(acha_pdf(obra["prefixo"])), obra["autor"]))
        doc_id = cur.fetchone()[0]
        linhas = [(doc_id, c, i, str(v.tolist()), len(c) // 4, p, cap)
                  for i, ((c, p, cap), v) in enumerate(zip(chunks, vets))]
        execute_values(cur, "INSERT INTO chunks (documento_id, conteudo, indice, embedding, tokens, pagina, capitulo) VALUES %s",
                       linhas, page_size=500)
        cur.execute("UPDATE documentos SET total_chunks=%s WHERE id=%s", (len(chunks), doc_id))
        print(f"  gravado: {obra['titulo'][:45]} ({len(chunks)})")
    con.commit()
    cur.execute("SELECT d.titulo, count(*), count(DISTINCT c.capitulo), min(c.pagina), max(c.pagina) "
                "FROM chunks c JOIN documentos d ON d.id=c.documento_id GROUP BY d.titulo")
    for r in cur.fetchall():
        print("  conferência:", r)
    con.close()


if __name__ == "__main__":
    main()

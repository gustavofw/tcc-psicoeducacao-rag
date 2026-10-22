"""
============================================================
ingestao.py - Chunking + Embeddings das obras de Aaron Beck
============================================================

Este script faz a "Preparação dos Dados" (Data Preparation do CRISP-DM):

  1. Lê os PDFs das obras de Aaron Beck
  2. Extrai o texto de cada PDF
  3. Divide o texto em pedaços (chunks) de ~500 tokens
  4. Gera um embedding (vetor de 384 números) para cada chunk
  5. Salva tudo no banco PostgreSQL (tabelas 'documentos' e 'chunks')

Como usar:
  1. Coloque os PDFs de Beck na pasta definida em PASTA_PDFS
  2. Rode: python ingestao.py
============================================================
"""

import os
import glob
import psycopg2
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ------------------------------------------------------------
# CONFIGURAÇÕES  (ajuste conforme o seu ambiente)
# ------------------------------------------------------------

# Pasta onde estão os PDFs das obras de Beck
PASTA_PDFS = r"C:\Users\gfabr\OneDrive\Documentos\projeto_tcc_gustavo\backend\data\obras_beck"

# Dados de conexão com o banco (os mesmos do seu arquivo .env)
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,            # porta do container Docker
    "dbname": "psicoedu",
    "user": "postgres",
    "password": "tcc2026",
}

# Modelo de embeddings (o mesmo definido no TCC)
MODELO_EMBEDDING = "paraphrase-multilingual-MiniLM-L12-v2"

# Tamanho de cada chunk. O RecursiveCharacterTextSplitter conta CARACTERES,
# não tokens. Como ~1 token ≈ 4 caracteres, usamos ~2000 caracteres para
# chegar perto de 500 tokens. O overlap mantém um pouco de contexto entre
# pedaços vizinhos, para não "cortar" ideias no meio.
TAMANHO_CHUNK = 500      # 125 tokens
OVERLAP_CHUNK = 75        # 15 tokens de sobreposição


# ------------------------------------------------------------
# PASSO 1 - Ler o texto de um PDF
# ------------------------------------------------------------
def ler_pdf(caminho_pdf):
    """Abre um PDF e devolve todo o texto dele como uma string."""
    leitor = PdfReader(caminho_pdf)
    texto_completo = ""
    for pagina in leitor.pages:
        texto = pagina.extract_text()
        if texto:                       # algumas páginas podem vir vazias
            texto_completo += texto + "\n"
    return texto_completo


# ------------------------------------------------------------
# PASSO 2 - Dividir o texto em chunks
# ------------------------------------------------------------
def dividir_em_chunks(texto):
    """
    Divide um texto grande em pedaços menores.
    O RecursiveCharacterTextSplitter tenta quebrar em pontos naturais
    (parágrafos, depois frases, depois palavras), preservando o sentido.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=TAMANHO_CHUNK,
        chunk_overlap=OVERLAP_CHUNK,
        separators=["\n\n", "\n", ". ", " ", ""],  # ordem de preferência
    )
    return splitter.split_text(texto)


# ------------------------------------------------------------
# PASSO 3 - Salvar um documento no banco e devolver seu id
# ------------------------------------------------------------
def salvar_documento(cursor, titulo, fonte):
    """Insere uma linha na tabela 'documentos' e devolve o id gerado."""
    cursor.execute(
        """
        INSERT INTO documentos (titulo, fonte, autor)
        VALUES (%s, %s, %s)
        RETURNING id;
        """,
        (titulo, fonte, "Aaron Beck"),
    )
    return cursor.fetchone()[0]


# ------------------------------------------------------------
# PASSO 4 - Salvar um chunk (com seu embedding) no banco
# ------------------------------------------------------------
def salvar_chunk(cursor, documento_id, conteudo, indice, embedding, tokens):
    """Insere uma linha na tabela 'chunks'."""
    cursor.execute(
        """
        INSERT INTO chunks (documento_id, conteudo, indice, embedding, tokens)
        VALUES (%s, %s, %s, %s, %s);
        """,
        (documento_id, conteudo, indice, embedding, tokens),
    )


# ------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():
    # --- Carrega o modelo de embeddings (baixa na primeira vez) ---
    print(f"Carregando o modelo de embeddings '{MODELO_EMBEDDING}'...")
    modelo = SentenceTransformer(MODELO_EMBEDDING)
    print("Modelo carregado.\n")

    # --- Conecta ao banco ---
    print("Conectando ao banco de dados...")
    conexao = psycopg2.connect(**DB_CONFIG)
    cursor = conexao.cursor()
    print("Conectado.\n")

    # --- Procura todos os PDFs na pasta ---
    padrao = os.path.join(PASTA_PDFS, "*.pdf")
    lista_pdfs = glob.glob(padrao)

    if not lista_pdfs:
        print(f"Nenhum PDF encontrado em '{PASTA_PDFS}'.")
        print("Coloque os PDFs de Beck nessa pasta e rode novamente.")
        return

    print(f"Encontrados {len(lista_pdfs)} PDF(s).\n")

    # --- Processa cada PDF ---
    for caminho in lista_pdfs:
        nome_arquivo = os.path.basename(caminho)
        print(f"Processando: {nome_arquivo}")

        # 1. Ler o texto
        texto = ler_pdf(caminho)
        if not texto.strip():
            print(f"  [AVISO] Não consegui extrair texto de {nome_arquivo}. Pulei.")
            continue

        # 2. Dividir em chunks
        chunks = dividir_em_chunks(texto)
        print(f"  Texto dividido em {len(chunks)} chunks.")

        # 3. Registrar o documento no banco
        documento_id = salvar_documento(cursor, titulo=nome_arquivo, fonte=caminho)

        # 4. Gerar embeddings de todos os chunks de uma vez (mais rápido)
        print("  Gerando embeddings...")
        embeddings = modelo.encode(chunks, show_progress_bar=True)

        # 5. Salvar cada chunk com seu embedding
        for indice, (texto_chunk, vetor) in enumerate(zip(chunks, embeddings)):
            # o pgvector aceita o vetor como uma lista Python convertida em string
            vetor_lista = vetor.tolist()
            tokens_aprox = len(texto_chunk) // 4   # estimativa simples
            salvar_chunk(cursor, documento_id, texto_chunk, indice, vetor_lista, tokens_aprox)

        # 6. Atualizar o total de chunks do documento
        cursor.execute(
            "UPDATE documentos SET total_chunks = %s WHERE id = %s;",
            (len(chunks), documento_id),
        )

        conexao.commit()   # confirma as inserções deste PDF
        print(f"  {nome_arquivo} concluído: {len(chunks)} chunks salvos.\n")

    # --- Fecha a conexão ---
    cursor.close()
    conexao.close()
    print("Ingestão concluída! Todos os PDFs foram processados.")


if __name__ == "__main__":
    main()
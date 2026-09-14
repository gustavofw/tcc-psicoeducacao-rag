"""
check_ambiente.py
-----------------
Script de diagnóstico do ambiente de desenvolvimento do TCC 2.
Verifica se todas as ferramentas e bibliotecas necessárias estão
instaladas e funcionando.

Como usar:
    python check_ambiente.py
"""

import sys
import shutil
import subprocess
import importlib.util

VERDE = "\033[92m"
VERMELHO = "\033[91m"
AMARELO = "\033[93m"
AZUL = "\033[94m"
NEGRITO = "\033[1m"
RESET = "\033[0m"

def ok(msg):
    print(f"  {VERDE}[OK]{RESET} {msg}")

def falha(msg):
    print(f"  {VERMELHO}[FALTA]{RESET} {msg}")

def aviso(msg):
    print(f"  {AMARELO}[AVISO]{RESET} {msg}")

def titulo(msg):
    print(f"\n{AZUL}{NEGRITO}== {msg} =={RESET}")


def checar_python():
    titulo("1. Python")
    v = sys.version_info
    versao = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor >= 10:
        ok(f"Python {versao} (recomendado 3.10 ou superior)")
    else:
        aviso(f"Python {versao} — recomenda-se 3.10 ou superior para melhor compatibilidade")


def checar_bibliotecas():
    titulo("2. Bibliotecas Python")
    libs = {
        "fastapi":            "FastAPI (framework do back-end)",
        "uvicorn":            "Uvicorn (servidor da API)",
        "langchain":          "LangChain (orquestrador do RAG)",
        "langchain_community":"LangChain Community (integrações)",
        "sentence_transformers":"SentenceTransformers (embeddings)",
        "psycopg2":           "psycopg2 (conexão com PostgreSQL)",
        "pgvector":           "pgvector (suporte a vetores no Python)",
        "pydantic":           "Pydantic (validação de dados)",
        "dotenv":             "python-dotenv (variáveis de ambiente)",
    }
    for modulo, descricao in libs.items():
        if importlib.util.find_spec(modulo) is not None:
            ok(descricao)
        else:
            falha(f"{descricao}  ->  instale com: pip install {modulo.replace('_', '-')}")


def rodar(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def checar_ferramentas():
    titulo("3. Ferramentas externas")

    if shutil.which("ollama"):
        sucesso, saida = rodar(["ollama", "--version"])
        ok(f"Ollama instalado ({saida.splitlines()[0] if saida else 'versão desconhecida'})")
    else:
        falha("Ollama não encontrado  ->  baixe em https://ollama.com/download")

    if shutil.which("psql"):
        sucesso, saida = rodar(["psql", "--version"])
        ok(f"PostgreSQL cliente ({saida if saida else 'versão desconhecida'})")
    else:
        aviso("psql (cliente PostgreSQL) não encontrado no PATH — verifique a instalação do PostgreSQL")

    if shutil.which("node"):
        sucesso, saida = rodar(["node", "--version"])
        ok(f"Node.js instalado ({saida})")
    else:
        aviso("Node.js não encontrado — necessário para o front-end React (pode instalar depois)")

    if shutil.which("git"):
        sucesso, saida = rodar(["git", "--version"])
        ok(f"Git instalado ({saida})")
    else:
        falha("Git não encontrado  ->  baixe em https://git-scm.com/downloads")


def checar_modelo_llama():
    titulo("4. Modelo Llama 3.1 no Ollama")
    if not shutil.which("ollama"):
        aviso("Ollama não está instalado — pulei esta verificação")
        return
    sucesso, saida = rodar(["ollama", "list"])
    if not sucesso:
        aviso("Não consegui listar os modelos do Ollama. O serviço do Ollama está rodando?")
        return
    if "llama3.1" in saida.lower() or "llama3" in saida.lower():
        ok("Modelo Llama 3.1 encontrado no Ollama")
    else:
        falha("Modelo Llama 3.1 não encontrado  ->  baixe com: ollama pull llama3.1")


def checar_conexao_banco():
    titulo("5. Conexão com o banco de dados")
    if importlib.util.find_spec("psycopg2") is None:
        aviso("psycopg2 não instalado — pulei o teste de conexão")
        return
    print("  (Este teste usa as variáveis do arquivo .env, se existir)")
    print(f"  {AMARELO}Ajuste os dados de conexão abaixo e rode novamente para testar.{RESET}")
    # Descomente e ajuste quando o PostgreSQL estiver pronto:
    #
    # import psycopg2
    # try:
    #     conn = psycopg2.connect(
    #         host="localhost", port=5432,
    #         dbname="psicoedu", user="postgres", password="SUA_SENHA"
    #     )
    #     cur = conn.cursor()
    #     cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
    #     if cur.fetchone():
    #         ok("Conectado e extensão pgvector ativa no banco")
    #     else:
    #         falha("Conectado, mas a extensão pgvector não está ativa -> rode: CREATE EXTENSION vector;")
    #     conn.close()
    # except Exception as e:
    #     falha(f"Não consegui conectar ao PostgreSQL: {e}")


def main():
    print(f"{NEGRITO}{AZUL}")
    print("=" * 60)
    print("  DIAGNÓSTICO DO AMBIENTE - TCC 2 (Plataforma de Psicoeducação)")
    print("=" * 60)
    print(RESET)

    checar_python()
    checar_bibliotecas()
    checar_ferramentas()
    checar_modelo_llama()
    checar_conexao_banco()

    print(f"\n{NEGRITO}Verificação concluída.{RESET}")
    print("Corrija os itens marcados como [FALTA] antes de prosseguir.\n")


if __name__ == "__main__":
    main()
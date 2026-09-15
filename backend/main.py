"""
============================================================
main.py - API do back-end (FastAPI)
============================================================

Esta é a API que expõe o RAG como um serviço web. O front-end
(React) vai enviar as perguntas do usuário para cá, e receber
de volta as respostas geradas.

Por enquanto, temos apenas o endpoint principal:
  POST /chat  -> recebe uma pergunta, roda o RAG, devolve a resposta

Como rodar:
  uvicorn main:app --reload

Depois de rodar, abra no navegador:
  http://localhost:8000/docs
  (página de testes interativa gerada automaticamente pelo FastAPI)
============================================================
"""

import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

MODELO_EMBEDDING = "paraphrase-multilingual-MiniLM-L12-v2"
MODELO_LLM = "llama3.1"
TOP_K = 4
TEMPERATURA = 0.3

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

# ------------------------------------------------------------
# INICIALIZAÇÃO (roda uma vez, quando a API sobe)
# ------------------------------------------------------------
# Carregamos o modelo de embeddings e o Llama UMA VEZ, na inicialização,
# para não ter que recarregar a cada requisição (o que seria lento).
print("Carregando modelo de embeddings...")
modelo_emb = SentenceTransformer(MODELO_EMBEDDING)

print("Preparando o Llama...")
llm = ChatOllama(model=MODELO_LLM, temperature=TEMPERATURA)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "Pergunta: {pergunta}"),
])

# ------------------------------------------------------------
# Cria a aplicação FastAPI
# ------------------------------------------------------------
app = FastAPI(title="API de Psicoeducação - TCC", version="0.1.0")

# CORS: permite que o front-end (React, em outra porta) acesse a API.
# Durante o desenvolvimento, liberamos tudo ("*"). Em produção, restringir.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# MODELOS DE DADOS (o que entra e o que sai da API)
# ------------------------------------------------------------
# O Pydantic valida automaticamente os dados recebidos.

class PerguntaEntrada(BaseModel):
    """O que o front-end envia."""
    pergunta: str

class FonteSaida(BaseModel):
    """Cada fonte usada na resposta (rastreabilidade)."""
    trecho: int
    titulo: str
    similaridade: float

class RespostaSaida(BaseModel):
    """O que a API devolve."""
    resposta: str
    fontes: list[FonteSaida]


# ------------------------------------------------------------
# Função de busca (a mesma lógica já validada)
# ------------------------------------------------------------
def buscar_chunks(pergunta, k=TOP_K):
    """Conecta ao banco, busca os k trechos mais parecidos e devolve."""
    vetor = modelo_emb.encode(pergunta).tolist()
    conexao = psycopg2.connect(**DB_CONFIG)
    cursor = conexao.cursor()
    cursor.execute(
        """
        SELECT c.conteudo, d.titulo, 1 - (c.embedding <=> %s::vector) AS similaridade
        FROM chunks c
        JOIN documentos d ON d.id = c.documento_id
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s;
        """,
        (vetor, vetor, k),
    )
    resultados = cursor.fetchall()
    cursor.close()
    conexao.close()
    return resultados


# ------------------------------------------------------------
# ENDPOINT: POST /chat
# ------------------------------------------------------------
@app.post("/chat", response_model=RespostaSaida)
def chat(entrada: PerguntaEntrada):
    """
    Recebe uma pergunta, executa o pipeline RAG e devolve
    a resposta gerada + as fontes consultadas.
    """
    # 1-4. Buscar e recuperar os trechos
    resultados = buscar_chunks(entrada.pergunta)

    # Montar o contexto para o prompt
    contexto = "\n\n".join(
        f"[Trecho {i} - Fonte: {titulo}]\n{conteudo}"
        for i, (conteudo, titulo, sim) in enumerate(resultados, 1)
    )

    # 5. Montar o prompt final
    mensagem = prompt_template.format_messages(
        contexto=contexto, pergunta=entrada.pergunta
    )

    # 6. Gerar a resposta com o Llama
    resposta_llm = llm.invoke(mensagem)

    # Montar a lista de fontes (rastreabilidade)
    fontes = [
        FonteSaida(trecho=i, titulo=titulo, similaridade=round(sim, 3))
        for i, (conteudo, titulo, sim) in enumerate(resultados, 1)
    ]

    return RespostaSaida(resposta=resposta_llm.content, fontes=fontes)


# ------------------------------------------------------------
# ENDPOINT: GET / (só para testar se a API está no ar)
# ------------------------------------------------------------
@app.get("/")
def raiz():
    return {"status": "API de Psicoeducação no ar", "docs": "/docs"}
"""
============================================================
main.py - API do back-end (FastAPI) - com ciclo de sessão
============================================================

Endpoints:
  POST /sessao/iniciar    -> cria uma nova sessão (UC01)
  POST /chat              -> recebe pergunta, roda o RAG, salva a mensagem (RF01-RF05)
  POST /feedback          -> registra avaliação 1-5 de uma resposta (RF09)
  POST /sessao/encerrar   -> encerra a sessão e descarta o histórico (RF07)
  GET  /                  -> status da API

Como rodar:
  uvicorn main:app --reload
Página de testes:
  http://localhost:8000/docs
============================================================
"""
import psycopg2
from fastapi import FastAPI, HTTPException
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
# INICIALIZAÇÃO (uma vez, quando a API sobe)
# ------------------------------------------------------------
print("Carregando modelo de embeddings...")
modelo_emb = SentenceTransformer(MODELO_EMBEDDING)

print("Preparando o Llama...")
llm = ChatOllama(model=MODELO_LLM, temperature=TEMPERATURA)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "Pergunta: {pergunta}"),
])

app = FastAPI(title="API de Psicoeducação - TCC", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# Helper: abrir conexão com o banco
# ------------------------------------------------------------
def get_conexao():
    return psycopg2.connect(**DB_CONFIG)


# ------------------------------------------------------------
# MODELOS DE DADOS (entrada e saída)
# ------------------------------------------------------------
class PerguntaEntrada(BaseModel):
    sessao_id: int          # a qual sessão esta mensagem pertence
    pergunta: str

class FonteSaida(BaseModel):
    trecho: int
    titulo: str
    similaridade: float

class RespostaSaida(BaseModel):
    mensagem_id: int        # id da mensagem salva (usado depois no feedback)
    resposta: str
    fontes: list[FonteSaida]

class SessaoSaida(BaseModel):
    sessao_id: int

class FeedbackEntrada(BaseModel):
    mensagem_id: int
    nota: int               # de 1 a 5

class OkSaida(BaseModel):
    ok: bool
    detalhe: str


# ------------------------------------------------------------
# ENDPOINT: iniciar sessão (UC01)
# ------------------------------------------------------------
@app.post("/sessao/iniciar", response_model=SessaoSaida)
def iniciar_sessao():
    """Cria uma nova sessão de conversa e devolve o id dela."""
    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute("INSERT INTO sessoes DEFAULT VALUES RETURNING id;")
    sessao_id = cursor.fetchone()[0]
    conexao.commit()
    cursor.close()
    conexao.close()
    return SessaoSaida(sessao_id=sessao_id)


# ------------------------------------------------------------
# Função de busca vetorial
# ------------------------------------------------------------
def buscar_chunks(cursor, pergunta, k=TOP_K):
    vetor = modelo_emb.encode(pergunta).tolist()
    cursor.execute(
        """
        SELECT c.id, c.conteudo, d.titulo, 1 - (c.embedding <=> %s::vector) AS similaridade
        FROM chunks c
        JOIN documentos d ON d.id = c.documento_id
        ORDER BY c.embedding <=> %s::vector
        LIMIT %s;
        """,
        (vetor, vetor, k),
    )
    return cursor.fetchall()

# ------------------------------------------------------------
# ENDPOINT: chat (RF01-RF05)
# ------------------------------------------------------------
@app.post("/chat", response_model=RespostaSaida)
def chat(entrada: PerguntaEntrada):
    """Recebe a pergunta, roda o RAG, salva a mensagem e devolve a resposta."""
    conexao = get_conexao()
    cursor = conexao.cursor()

    # Salva a mensagem do usuário
    cursor.execute(
        "INSERT INTO mensagens (sessao_id, papel, conteudo) VALUES (%s, 'usuario', %s);",
        (entrada.sessao_id, entrada.pergunta),
    )
    
    # 1-4. Buscar e recuperar os trechos
    resultados = buscar_chunks(cursor, entrada.pergunta)
    chunks_ids = [r[0] for r in resultados]

    # Montar contexto
    contexto = "\n\n".join(
        f"[Trecho {i} - Fonte: {titulo}]\n{conteudo}"
        for i, (cid, conteudo, titulo, sim) in enumerate(resultados, 1)
    )

    # 5. Montar prompt
    mensagem = prompt_template.format_messages(
        contexto=contexto, pergunta=entrada.pergunta
    )

    # 6. Gerar resposta
    resposta_llm = llm.invoke(mensagem)
    texto_resposta = resposta_llm.content

    # Salva a resposta do agente (com os chunks usados) e pega o id
    cursor.execute(
        """
        INSERT INTO mensagens (sessao_id, papel, conteudo, chunks_usados)
        VALUES (%s, 'agente', %s, %s)
        RETURNING id;
        """,
        (entrada.sessao_id, texto_resposta, chunks_ids),
    )
    mensagem_id = cursor.fetchone()[0]

    conexao.commit()
    cursor.close()
    conexao.close()

    fontes = [
        FonteSaida(trecho=i, titulo=titulo, similaridade=round(sim, 3))
        for i, (cid, conteudo, titulo, sim) in enumerate(resultados, 1)
    ]
    return RespostaSaida(mensagem_id=mensagem_id, resposta=texto_resposta, fontes=fontes)


# ------------------------------------------------------------
# ENDPOINT: feedback (RF09)
# ------------------------------------------------------------
@app.post("/feedback", response_model=OkSaida)
def feedback(entrada: FeedbackEntrada):
    """Registra a avaliação (1-5) de uma resposta do agente."""
    if entrada.nota < 1 or entrada.nota > 5:
        raise HTTPException(status_code=400, detail="A nota deve ser entre 1 e 5.")

    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute(
        "UPDATE mensagens SET feedback_usuario = %s WHERE id = %s AND papel = 'agente';",
        (entrada.nota, entrada.mensagem_id),
    )
    afetadas = cursor.rowcount
    conexao.commit()
    cursor.close()
    conexao.close()

    if afetadas == 0:
        raise HTTPException(status_code=404, detail="Mensagem não encontrada.")
    return OkSaida(ok=True, detalhe="Feedback registrado.")


# ------------------------------------------------------------
# ENDPOINT: encerrar sessão (RF07)
# ------------------------------------------------------------
@app.post("/sessao/encerrar", response_model=OkSaida)
def encerrar_sessao(entrada: SessaoSaida):
    """
    Encerra a sessão (marca encerrada_em) e descarta o histórico
    de mensagens dela, em conformidade com o RNF02 (não persistência).
    """
    conexao = get_conexao()
    cursor = conexao.cursor()

    # Marca a sessão como encerrada
    cursor.execute(
        "UPDATE sessoes SET encerrada_em = CURRENT_TIMESTAMP WHERE id = %s;",
        (entrada.sessao_id,),
    )

    # Descarta o histórico de mensagens da sessão (RNF02).
    cursor.execute(
        "DELETE FROM mensagens WHERE sessao_id = %s;",
        (entrada.sessao_id,),
    )

    conexao.commit()
    cursor.close()
    conexao.close()
    return OkSaida(ok=True, detalhe="Sessão encerrada e histórico descartado.")


# ------------------------------------------------------------
# ENDPOINT: status
# ------------------------------------------------------------
@app.get("/")
def raiz():
    return {"status": "API de Psicoeducação no ar", "docs": "/docs"}
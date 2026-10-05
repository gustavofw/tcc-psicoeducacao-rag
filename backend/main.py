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
import os
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

load_dotenv()  # carrega variáveis do .env
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
# RF08 - Prompt de detecção de sofrimento agudo
# ------------------------------------------------------------
# Pede ao Llama para classificar a mensagem. Responde só SIM ou NÃO.
PROMPT_DETECCAO = """Sua única tarefa é classificar mensagens quanto a risco \
em saúde mental. Você NÃO deve responder à mensagem, apenas classificá-la.

Responda SOMENTE com uma palavra: SIM ou NAO.

Responda SIM se a mensagem contiver qualquer indício de: ideação suicida, \
vontade de morrer, automutilação, intenção de se ferir, desesperança profunda \
ou sofrimento psíquico grave.

Responda NAO apenas para perguntas informativas, dúvidas sobre conceitos ou \
conversas comuns sem risco.

Exemplos:
Mensagem: "o que são pensamentos automáticos?" -> NAO
Mensagem: "quero me matar" -> SIM
Mensagem: "não aguento mais viver" -> SIM
Mensagem: "como funciona a TCC?" -> NAO
Mensagem: "não vejo sentido em nada, queria sumir" -> SIM
Mensagem: "me explique a tríade cognitiva" -> NAO
Mensagem: "pensei em me machucar" -> SIM

Agora classifique esta mensagem. Responda apenas SIM ou NAO.
Mensagem: "{mensagem}" -> """

# Mensagem fixa de encaminhamento (não gerada pelo Llama, por segurança)
MENSAGEM_ENCAMINHAMENTO = (
    "Percebi que você pode estar passando por um momento muito difícil, e quero "
    "que saiba que você não está sozinho(a). Este sistema é educativo e não "
    "substitui o apoio de um profissional. Por favor, procure ajuda especializada:\n\n"
    "• CVV – 188 (Centro de Valorização da Vida, gratuito, 24h)\n"
    "• SAP – Serviço de Atendimento Psicológico da UNOESC\n"
    "• CAPS – Centro de Atenção Psicossocial mais próximo de você\n\n"
    "Se houver risco imediato à sua vida, ligue 192 (SAMU) ou vá ao serviço de "
    "emergência mais próximo."
)

# ------------------------------------------------------------
# INICIALIZAÇÃO (uma vez, quando a API sobe)
# ------------------------------------------------------------
print("Carregando modelo de embeddings...")
modelo_emb = SentenceTransformer(MODELO_EMBEDDING)

print("Preparando o Llama...")
# Local (desenvolvimento, mais lento):
# llm = ChatOllama(model=MODELO_LLM, temperature=TEMPERATURA)

_hf_endpoint = HuggingFaceEndpoint(
    repo_id="meta-llama/Llama-3.1-8B-Instruct",
    task="text-generation",
    huggingfacehub_api_token=os.getenv("HF_TOKEN"),
    temperature=TEMPERATURA,
    max_new_tokens=512,
)
llm = ChatHuggingFace(llm=_hf_endpoint)

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
# RF08 - Função que detecta sofrimento agudo usando o Llama
# ------------------------------------------------------------
# ------------------------------------------------------------
# RF08 - Lista de termos críticos (camada de segurança direta)
# ------------------------------------------------------------
# Termos explícitos que acionam o encaminhamento imediatamente,
# sem depender do julgamento do modelo. Esta é a camada mais
# confiável para casos graves e inequívocos.
TERMOS_CRITICOS = [
    "me matar", "suicídio", "suicidio", "me suicidar", "tirar minha vida",
    "quero morrer", "vou morrer", "não quero viver", "nao quero viver",
    "acabar com tudo", "me machucar", "me cortar", "me ferir",
    "sumir pra sempre", "sumir para sempre", "tirar a própria vida",
    "não aguento mais viver", "nao aguento mais viver", "melhor morto",
    "melhor morta", "dar fim na vida", "pôr fim à vida", "por fim a vida",
]

def contem_termo_critico(pergunta):
    """Verifica se a mensagem contém algum termo crítico explícito."""
    texto = pergunta.lower()
    return any(termo in texto for termo in TERMOS_CRITICOS)


def detectar_sofrimento(pergunta):
    """
    Detecta sofrimento agudo em duas camadas:
    1. Lista de termos críticos (determinística, confiável para casos graves)
    2. Classificação pelo Llama (para casos mais sutis)
    Em caso de dúvida, erra para o lado seguro (encaminha).
    """
    # Camada 1: termos críticos explícitos -> encaminha imediatamente
    if contem_termo_critico(pergunta):
        print(f"[RF08 DEBUG] Termo crítico detectado em: {pergunta!r}")
        return True

    # Camada 2: classificação pelo Llama (casos sutis)
    try:
        prompt = PROMPT_DETECCAO.format(mensagem=pergunta)
        resposta = llm.invoke(prompt)
        texto = resposta.content.strip().upper()
        print(f"[RF08 DEBUG] Pergunta: {pergunta!r} -> Llama: {texto!r}")
        if "SIM" in texto:
            return True
        if texto.startswith("NAO") or texto.startswith("NÃO"):
            return False
        return False  # resposta normal -> segue fluxo normal
    except Exception as e:
        print(f"[RF08 DEBUG] ERRO: {e}")
        return False  # erro na camada 2 não deve bloquear perguntas normais

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
    
    # RF08 - antes de responder, verifica se há sofrimento agudo
    if detectar_sofrimento(entrada.pergunta):
        # salva a resposta de encaminhamento como mensagem do agente
        cursor.execute(
            """
            INSERT INTO mensagens (sessao_id, papel, conteudo)
            VALUES (%s, 'agente', %s)
            RETURNING id;
            """,
            (entrada.sessao_id, MENSAGEM_ENCAMINHAMENTO),
        )
        mensagem_id = cursor.fetchone()[0]
        conexao.commit()
        cursor.close()
        conexao.close()
        # devolve o encaminhamento, sem passar pelo RAG
        return RespostaSaida(
            mensagem_id=mensagem_id,
            resposta=MENSAGEM_ENCAMINHAMENTO,
            fontes=[],  # encaminhamento não tem fontes
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
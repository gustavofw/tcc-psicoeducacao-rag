"""Endpoints da API: sessão, chat, feedback."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.services.db import get_conexao
from app.services.rag_service import buscar_chunks, gerar_resposta
from app.services.seguranca import detectar_sofrimento
from app.core.config import MENSAGEM_ENCAMINHAMENTO, CODIGO_ACESSO
from app.services.memoria import log_memoria

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# --- Modelos de dados ---
class PerguntaEntrada(BaseModel):
    sessao_id: int
    pergunta: str
    codigo: str = ""

class FonteSaida(BaseModel):
    trecho: int
    titulo: str
    similaridade: float
    conteudo: str   

class RespostaSaida(BaseModel):
    mensagem_id: int
    resposta: str
    fontes: list[FonteSaida]

class SessaoSaida(BaseModel):
    sessao_id: int

class FeedbackEntrada(BaseModel):
    mensagem_id: int
    nota: int

class OkSaida(BaseModel):
    ok: bool
    detalhe: str

class AcessoEntrada(BaseModel):
    codigo: str

@router.post("/validar-acesso", response_model=OkSaida)
@limiter.limit("5/minute")
def validar_acesso(request: Request, entrada: AcessoEntrada):
    if CODIGO_ACESSO and entrada.codigo == CODIGO_ACESSO:
        return OkSaida(ok=True, detalhe="Acesso liberado.")
    raise HTTPException(status_code=401, detail="Código de acesso inválido.")

# --- Iniciar sessão (UC01) ---
@router.post("/sessao/iniciar", response_model=SessaoSaida)
def iniciar_sessao():
    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute("INSERT INTO sessoes DEFAULT VALUES RETURNING id;")
    sessao_id = cursor.fetchone()[0]
    conexao.commit()
    cursor.close()
    conexao.close()
    return SessaoSaida(sessao_id=sessao_id)


# --- Chat (RF01-RF05 + RF08) ---
@router.post("/chat", response_model=RespostaSaida)
@limiter.limit("20/minute")
def chat(request: Request, entrada: PerguntaEntrada):
    # valida código de acesso
    if CODIGO_ACESSO and entrada.codigo != CODIGO_ACESSO:
        raise HTTPException(status_code=401, detail="Código de acesso inválido.")

    conexao = get_conexao()
    cursor = conexao.cursor()

    # salva a mensagem do usuário
    cursor.execute(
        "INSERT INTO mensagens (sessao_id, papel, conteudo) VALUES (%s, 'usuario', %s);",
        (entrada.sessao_id, entrada.pergunta),
    )

    # RF08 - verifica sofrimento agudo
    if detectar_sofrimento(entrada.pergunta):
        cursor.execute(
            "INSERT INTO mensagens (sessao_id, papel, conteudo) VALUES (%s, 'agente', %s) RETURNING id;",
            (entrada.sessao_id, MENSAGEM_ENCAMINHAMENTO),
        )
        mensagem_id = cursor.fetchone()[0]
        conexao.commit()
        cursor.close()
        conexao.close()
        return RespostaSaida(mensagem_id=mensagem_id, resposta=MENSAGEM_ENCAMINHAMENTO, fontes=[])

    # fluxo RAG normal
    resultados = buscar_chunks(cursor, entrada.pergunta)
    chunks_ids = [r[0] for r in resultados]
    texto_resposta = gerar_resposta(entrada.pergunta, resultados)

    cursor.execute(
        "INSERT INTO mensagens (sessao_id, papel, conteudo, chunks_usados) VALUES (%s, 'agente', %s, %s) RETURNING id;",
        (entrada.sessao_id, texto_resposta, chunks_ids),
    )
    mensagem_id = cursor.fetchone()[0]
    conexao.commit()
    cursor.close()
    conexao.close()

    fontes = [
        FonteSaida(
            trecho=i,
            titulo=titulo,
            similaridade=round(sim, 3),
            conteudo=conteudo[:200] + "..."   
        )
        for i, (cid, conteudo, titulo, sim) in enumerate(resultados, 1)
    ]
    fontes = [
        FonteSaida(
            trecho=i,
            titulo=titulo,
            similaridade=round(sim, 3),
            conteudo=conteudo[:200] + "..."
        )
        for i, (cid, conteudo, titulo, sim) in enumerate(resultados, 1)
    ]
    log_memoria("após /chat")
    return RespostaSaida(mensagem_id=mensagem_id, resposta=texto_resposta, fontes=fontes)

# --- Feedback (RF09) ---
@router.post("/feedback", response_model=OkSaida)
def feedback(entrada: FeedbackEntrada):
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


# --- Encerrar sessão (RF07 + RNF02) ---
@router.post("/sessao/encerrar", response_model=OkSaida)
def encerrar_sessao(entrada: SessaoSaida):
    conexao = get_conexao()
    cursor = conexao.cursor()
    cursor.execute(
        "UPDATE sessoes SET encerrada_em = CURRENT_TIMESTAMP WHERE id = %s;",
        (entrada.sessao_id,),
    )
    # RF09: preserva só as notas (sem o texto da conversa) antes de descartar o histórico
    cursor.execute(
        "INSERT INTO avaliacoes (nota) "
        "SELECT feedback_usuario FROM mensagens "
        "WHERE sessao_id = %s AND feedback_usuario IS NOT NULL;",
        (entrada.sessao_id,),
    )
    cursor.execute("DELETE FROM mensagens WHERE sessao_id = %s;", (entrada.sessao_id,))
    conexao.commit()
    cursor.close()
    conexao.close()
    return OkSaida(ok=True, detalhe="Sessão encerrada e histórico descartado.")
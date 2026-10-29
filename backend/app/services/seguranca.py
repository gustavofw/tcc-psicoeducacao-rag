"""RF08 - Detecção de sofrimento agudo em duas camadas."""
import re
import unicodedata
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.services.rag_service import llm


def _normalizar_texto(texto):
    """Minúsculas, sem acentos e com espaços simples (para a lista de termos)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


# Camada 1: termos críticos (escritos sem acento; a comparação ignora acentos)
TERMOS_CRITICOS = [
    # ideação suicida explícita
    "me matar", "matar a mim mesmo", "me suicidar", "suicidio", "suicida",
    "tirar minha vida", "tirar a minha vida", "tirar a propria vida",
    "acabar com minha vida", "acabar com a minha vida",
    "dar fim na vida", "dar fim a vida", "dar fim na minha vida",
    "por fim a vida", "por fim a minha vida",
    # desejo de morrer / não viver
    "quero morrer", "queria morrer", "vontade de morrer", "desejo de morrer",
    "prefiro morrer", "vou morrer", "nao quero viver", "nao quero mais viver",
    "nao aguento mais viver", "cansei de viver", "sem vontade de viver",
    "melhor morto", "melhor morta", "seria melhor se eu morresse",
    "dormir e nao acordar", "nao acordar mais",
    "sumir pra sempre", "sumir para sempre", "acabar com tudo",
    # autolesão
    "me machucar", "me cortar", "me ferir", "me mutilar",
    "automutilacao", "auto mutilacao", "me jogar de", "me jogar da",
    "tomar todos os remedios", "overdose",
]
_TERMOS_NORMALIZADOS = [_normalizar_texto(t) for t in TERMOS_CRITICOS]

# Camada 2: instrução do classificador (enquadramento protetor, rótulos neutros)
INSTRUCAO_CLASSIFICADOR = (
    "Você é o componente de triagem de um sistema educativo de psicoeducação. "
    "Sua função é PROTEGER o usuário: quando uma mensagem indicar risco, o sistema "
    "exibe contatos de ajuda (como o CVV, 188). Você não diagnostica, não aconselha "
    "e não conversa com ninguém; apenas rotula o texto.\n\n"
    "Rótulos:\n"
    "RISCO = a pessoa expressa, sobre si mesma, ideação suicida, vontade de morrer, "
    "intenção de se ferir, desesperança profunda ou sofrimento psíquico grave.\n"
    "NORMAL = qualquer outra mensagem: perguntas sobre conceitos, assuntos gerais, "
    "assuntos fora do tema, saudações ou textos sem sentido.\n\n"
    "Responda somente com o rótulo (RISCO ou NORMAL), sem explicações."
)

EXEMPLOS = [
    ("o que são pensamentos automáticos?", "NORMAL"),
    ("não aguento mais viver", "RISCO"),
    ("fale sobre futebol", "NORMAL"),
    ("ultimamente nada vale a pena e eu queria sumir", "RISCO"),
    ("como funciona a TCC?", "NORMAL"),
    ("asdkj qwe", "NORMAL"),
]


def contem_termo_critico(pergunta):
    texto = _normalizar_texto(pergunta)
    return any(termo in texto for termo in _TERMOS_NORMALIZADOS)


def _montar_mensagens(pergunta):
    mensagens = [SystemMessage(content=INSTRUCAO_CLASSIFICADOR)]
    for exemplo, rotulo in EXEMPLOS:
        mensagens.append(HumanMessage(content=f'Mensagem: "{exemplo}"'))
        mensagens.append(AIMessage(content=rotulo))
    mensagens.append(HumanMessage(content=f'Mensagem: "{pergunta}"'))
    return mensagens


def classificar_com_llm(pergunta):
    """Camada 2: True = risco. Recusa, formato inesperado ou erro -> risco."""
    try:
        resposta = llm.invoke(_montar_mensagens(pergunta))
        texto = _normalizar_texto(resposta.content).upper()
        palavras = re.findall(r"[A-Z]+", texto)
        print(f"[RF08] Classificação da camada 2: {texto[:40]!r}")
        if palavras == ["NORMAL"]:
            return False
        if palavras == ["RISCO"]:
            return True
        print("[RF08] Resposta fora do formato -> tratada como risco (segurança)")
        return True
    except Exception as e:
        print(f"[RF08] ERRO -> tratado como risco (segurança): {type(e).__name__}")
        return True


def detectar_sofrimento(pergunta, modo="combinado"):
    """
    modo="combinado" (sistema): lista primeiro; se não detectar, LLM.
    modo="lista" / modo="llm": usados apenas no Experimento 4.
    """
    if modo in ("lista", "combinado") and contem_termo_critico(pergunta):
        print("[RF08] Termo crítico detectado na camada 1.")
        return True
    if modo == "lista":
        return False
    return classificar_com_llm(pergunta)
"""RF08 - Detecção de sofrimento agudo em duas camadas."""
import re
import unicodedata
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.services.rag_service import llm

# Camada 1: termos críticos explícitos
TERMOS_CRITICOS = [
    "me matar", "suicídio", "suicidio", "me suicidar", "tirar minha vida",
    "quero morrer", "vou morrer", "não quero viver", "nao quero viver",
    "acabar com tudo", "me machucar", "me cortar", "me ferir",
    "sumir pra sempre", "sumir para sempre", "tirar a própria vida",
    "não aguento mais viver", "nao aguento mais viver", "melhor morto",
    "melhor morta", "dar fim na vida", "pôr fim à vida", "por fim a vida",
]

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

# Exemplos em formato de conversa (few-shot)
EXEMPLOS = [
    ("o que são pensamentos automáticos?", "NORMAL"),
    ("não aguento mais viver", "RISCO"),
    ("fale sobre futebol", "NORMAL"),
    ("ultimamente nada vale a pena e eu queria sumir", "RISCO"),
    ("como funciona a TCC?", "NORMAL"),
    ("asdkj qwe", "NORMAL"),
]


def contem_termo_critico(pergunta):
    texto = pergunta.lower()
    return any(termo in texto for termo in TERMOS_CRITICOS)


def _normalizar(texto):
    """Remove acentos e deixa em maiúsculas."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.upper()


def _montar_mensagens(pergunta):
    mensagens = [SystemMessage(content=INSTRUCAO_CLASSIFICADOR)]
    for exemplo, rotulo in EXEMPLOS:
        mensagens.append(HumanMessage(content=f'Mensagem: "{exemplo}"'))
        mensagens.append(AIMessage(content=rotulo))
    mensagens.append(HumanMessage(content=f'Mensagem: "{pergunta}"'))
    return mensagens


def detectar_sofrimento(pergunta):
    """Detecta sofrimento agudo (camada 1: lista; camada 2: Llama)."""
    # Camada 1: termos críticos explícitos -> encaminha imediatamente
    if contem_termo_critico(pergunta):
        print("[RF08] Termo crítico detectado na camada 1.")
        return True

    # Camada 2: classificação pelo Llama (casos sutis)
    try:
        resposta = llm.invoke(_montar_mensagens(pergunta))
        texto = _normalizar(resposta.content.strip())
        palavras = re.findall(r"[A-Z]+", texto)
        print(f"[RF08] Classificação da camada 2: {texto[:40]!r}")

        # Aceita somente um único rótulo; recusas/frases -> risco (segurança)
        if palavras == ["NORMAL"]:
            return False
        if palavras == ["RISCO"]:
            return True
        print("[RF08] Resposta fora do formato -> tratada como risco (segurança)")
        return True
    except Exception as e:
        print(f"[RF08] ERRO -> tratado como risco (segurança): {type(e).__name__}")
        return True
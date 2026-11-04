"""RF08 - Detecção de sofrimento agudo em duas camadas."""
import os
import re
import unicodedata
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.core.config import PROVEDOR_LLM
from app.services.rag_service import llm

# Classificador do RF08: modelo próprio na nuvem (8B por padrão, o mesmo validado no E4),
# independente do modelo que gera as respostas. No Ollama local usa o mesmo modelo.
if PROVEDOR_LLM == "openrouter":
    from langchain_openai import ChatOpenAI
    from app.core.config import OPENROUTER_API_KEY, PROVEDOR_OPENROUTER
    _pref = {"data_collection": "deny", "allow_fallbacks": False}
    _lista = [p.strip() for p in os.getenv("PROVEDOR_CLASSIFICADOR", PROVEDOR_OPENROUTER or "").split(",") if p.strip()]
    if _lista:
        _pref["order"] = _lista
        _pref["only"] = _lista
        _pref["allow_fallbacks"] = len(_lista) > 1
    MODELO_CLASSIFICADOR = os.getenv("MODELO_CLASSIFICADOR", "meta-llama/llama-3.1-8b-instruct")
    print(f"Modelo do classificador RF08: {MODELO_CLASSIFICADOR}", flush=True)
    _llm_classificador = ChatOpenAI(
        model=MODELO_CLASSIFICADOR,
        temperature=0,
        max_tokens=8,
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        max_retries=4,
        timeout=30,
        extra_body={"provider": _pref},
    )
else:
    _llm_classificador = llm


class ServicoIndisponivel(Exception):
    """A chamada ao modelo falhou (provedor fora do ar, limite ou crédito)."""


def _normalizar_texto(texto):
    """Minúsculas, sem acentos e com espaços simples (para a lista de termos)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


# Expressões populares com palavras de risco que NÃO indicam risco.
# São removidas do texto antes da busca pelos termos críticos.
EXPRESSOES_SEM_RISCO = [
    r"\bmorr\w* de (rir|vergonha|saudades?|medo|fome|sono|calor|frio|tedio|cansaco|preguica|inveja)\b",
    r"\bmat\w* (a |as )?saudades?\b",
    r"\bmatando de (calor|frio|rir|fome|sono|cansaco)\b",
]

# Camada 1: termos críticos (sem acento; a comparação ignora acentos)
TERMOS_CRITICOS = [
    # ideação suicida explícita ("me matar" só com intenção, para não pegar "o trânsito vai me matar")
    "quero me matar", "vou me matar", "vontade de me matar", "pensando em me matar",
    "penso em me matar", "pensei em me matar", "planejando me matar", "tentar me matar",
    "matar a mim mesmo", "me suicidar", "suicidio", "suicida",
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

# Camada 2: instrução do classificador
INSTRUCAO_CLASSIFICADOR = (
    "Você é o componente de triagem de um sistema educativo de psicoeducação. "
    "Sua função é PROTEGER o usuário: quando uma mensagem indicar risco de vida, o sistema "
    "exibe contatos de ajuda (como o CVV, 188). Você não diagnostica, não aconselha "
    "e não conversa com ninguém; apenas rotula o texto.\n\n"
    "Rótulos:\n"
    "RISCO = a pessoa expressa, sobre si mesma, desejo de morrer, ideação ou plano suicida, "
    "intenção de se ferir ou desesperança extrema (sentir que não há saída ou que seria "
    "melhor não existir).\n"
    "NORMAL = qualquer outra mensagem, inclusive: perguntas sobre conceitos escritas na "
    "primeira pessoa; relatos de tristeza, ansiedade, estresse ou preocupação do dia a dia "
    "sem desejo de morrer; perguntas sobre diagnóstico, remédios ou sobre o próprio sistema; "
    "expressões populares (\"morri de rir\", \"matar a saudade\"); assuntos fora do tema; "
    "saudações ou textos sem sentido.\n\n"
    "Responda somente com o rótulo (RISCO ou NORMAL), sem explicações."
)

# Exemplos (diferentes das mensagens usadas nos testes, para não enviesar a avaliação)
EXEMPLOS = [
    ("o que são pensamentos automáticos?", "NORMAL"),
    ("por que eu fico pensando que vou fracassar em tudo?", "NORMAL"),
    ("sempre imagino que meus colegas me acham chato, isso é uma distorção?", "NORMAL"),
    ("o que é pensar em preto e branco?", "NORMAL"),
    ("ando estressado com o trabalho, como a TCC pode ajudar?", "NORMAL"),
    ("qual remédio é bom pra ansiedade?", "NORMAL"),
    ("você substitui um psicólogo?", "NORMAL"),
    ("morri de vergonha na reunião hoje kkk", "NORMAL"),
    ("quais sintomas são mais comuns na depressão?", "NORMAL"),
    ("não quero mais estar vivo", "RISCO"),
    ("tenho pensado em me machucar de propósito", "RISCO"),
    ("seria um alívio se eu não existisse", "RISCO"),
    ("já decidi que hoje é minha última noite", "RISCO"),
    ("asdkj qwe", "NORMAL"),
]


def contem_termo_critico(pergunta):
    texto = _normalizar_texto(pergunta)
    for padrao in EXPRESSOES_SEM_RISCO:
        texto = re.sub(padrao, " ", texto)
    return any(termo in texto for termo in _TERMOS_NORMALIZADOS)


def _montar_mensagens(pergunta):
    mensagens = [SystemMessage(content=INSTRUCAO_CLASSIFICADOR)]
    for exemplo, rotulo in EXEMPLOS:
        mensagens.append(HumanMessage(content=f'Mensagem: "{exemplo}"'))
        mensagens.append(AIMessage(content=rotulo))
    mensagens.append(HumanMessage(content=f'Mensagem: "{pergunta}"'))
    return mensagens


def classificar_llm_detalhado(pergunta):
    """Camada 2: 'RISCO', 'NORMAL' ou 'FORMATO' (recusa/fora do formato).
    Levanta ServicoIndisponivel se a chamada ao modelo falhar."""
    try:
        resposta = _llm_classificador.invoke(_montar_mensagens(pergunta))
    except Exception as e:
        # registra o tipo e a mensagem do erro (sem o texto do usuário)
        print(f"[RF08] ERRO na chamada ao modelo: {type(e).__name__}: {str(e)[:200]}", flush=True)
        raise ServicoIndisponivel() from e
    texto = _normalizar_texto(resposta.content).upper()
    palavras = re.findall(r"[A-Z]+", texto)
    if palavras == ["NORMAL"]:
        return "NORMAL"
    if palavras == ["RISCO"]:
        return "RISCO"
    print(f"[RF08] Resposta do classificador fora do formato: {texto[:40]!r}", flush=True)
    return "FORMATO"


def avaliar_risco(pergunta):
    """Usado pelo sistema. Retorna o motivo do encaminhamento ('lista', 'modelo' ou
    'recusa') ou None. Levanta ServicoIndisponivel se o modelo estiver fora do ar."""
    if contem_termo_critico(pergunta):
        motivo = "lista"
    else:
        rotulo = classificar_llm_detalhado(pergunta)
        motivo = {"RISCO": "modelo", "FORMATO": "recusa"}.get(rotulo)
    print(f"[RF08] encaminhamento={'sim' if motivo else 'nao'} motivo={motivo or '-'}", flush=True)
    return motivo


# --- Compatibilidade com o e4_rf08.py (True = encaminhar) ---
def classificar_com_llm(pergunta):
    try:
        return classificar_llm_detalhado(pergunta) != "NORMAL"
    except ServicoIndisponivel:
        return True


def detectar_sofrimento(pergunta, modo="combinado"):
    if modo in ("lista", "combinado") and contem_termo_critico(pergunta):
        return True
    if modo == "lista":
        return False
    return classificar_com_llm(pergunta)
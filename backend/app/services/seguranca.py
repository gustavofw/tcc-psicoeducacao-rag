"""RF08 - Detecção de sofrimento agudo em duas camadas."""
from app.core.config import PROMPT_DETECCAO
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

def contem_termo_critico(pergunta):
    texto = pergunta.lower()
    return any(termo in texto for termo in TERMOS_CRITICOS)

def detectar_sofrimento(pergunta):
    """Detecta sofrimento agudo (camada 1: lista; camada 2: Llama)."""
    # Camada 1: termos críticos explícitos -> encaminha imediatamente
    if contem_termo_critico(pergunta):
        print("[RF08] Termo crítico detectado na camada 1.")
        return True

    # Camada 2: classificação pelo Llama (casos sutis)
    try:
        prompt = PROMPT_DETECCAO.format(mensagem=pergunta)
        resposta = llm.invoke(prompt)
        texto = resposta.content.strip().upper()
        print(f"[RF08] Classificação da camada 2: {texto!r}")

        # Resposta curta e clara "NAO" -> sem risco
        if texto in ("NAO", "NÃO", "NAO.", "NÃO."):
            return False
        # Resposta curta e clara "SIM" -> risco
        if texto in ("SIM", "SIM."):
            return True
        # Qualquer outra coisa (recusa, formato inesperado, texto longo)
        # é tratada como risco, por segurança (orientação do parecer)
        print(f"[RF08] Resposta fora do formato -> tratada como risco (segurança)")
        return True
    except Exception as e:
        print(f"[RF08] ERRO -> tratado como risco (segurança): {e}")
        return True
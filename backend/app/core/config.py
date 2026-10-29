"""Configurações centralizadas da aplicação."""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Banco de dados ---
# Na nuvem (Render/Neon) usa DATABASE_URL; localmente cai no Docker
DATABASE_URL = os.getenv("DATABASE_URL")
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5433")),
    "dbname": os.getenv("DB_NAME", "psicoedu"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "tcc2026"),
}

# --- Modelos ---
MODELO_EMBEDDING = "paraphrase-multilingual-MiniLM-L12-v2"
BIBLIOTECA_EMBEDDING = os.getenv("BIBLIOTECA_EMBEDDING", "sentence-transformers")

# Provedor do LLM: "ollama" (local), "groq" ou "openrouter" (nuvem) — configurável pelo .env
PROVEDOR_LLM = os.getenv("PROVEDOR_LLM", "ollama")
MODELO_OLLAMA = "llama3.1"
MODELO_GROQ = "llama-3.1-8b-instant"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# OpenRouter (nuvem, mantém o Llama 3.1 8B)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODELO_OPENROUTER = "meta-llama/llama-3.1-8b-instruct"
# Provedor fixo no OpenRouter (parecer 3.1) — definido no .env / Render
PROVEDOR_OPENROUTER = os.getenv("PROVEDOR_OPENROUTER", "")

# --- Parâmetros ---
TOP_K = 5
TEMPERATURA = 0.3
MAX_TOKENS = 600

# Limiar de similaridade: abaixo disso, considera que não há conteúdo relevante
LIMIAR_SIMILARIDADE = 0.35

# --- Prompts ---
SYSTEM_PROMPT = """Você é um assistente de psicoeducação em saúde mental, \
fundamentado na Terapia Cognitivo-Comportamental de Aaron Beck.

REGRAS OBRIGATÓRIAS:
1. Responda SOMENTE com base nos trechos fornecidos abaixo (CONTEXTO). \
Não invente informações nem use conhecimento externo.
2. Se os trechos não contiverem informação suficiente para responder, \
diga honestamente que não possui essa informação na base de conhecimento.
3. Você faz PSICOEDUCAÇÃO: explica conceitos de forma clara e informativa. \
Você NÃO faz diagnósticos, NÃO indica ou comenta medicamentos ou dosagens, \
NÃO sugere tratamentos e NÃO substitui um profissional de saúde. \
Se perguntarem sobre diagnóstico, medicação ou tratamento, explique que isso \
deve ser avaliado por um profissional e oriente a procurar ajuda especializada.
4. Use uma linguagem acolhedora, clara e acessível.
5. Responda em português do Brasil.
6. Seja conciso e objetivo. Responda em no máximo 2 parágrafos curtos.

CONTEXTO (trechos recuperados da obra de Beck):
{contexto}
"""

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
Mensagem: "me explique a tríade cognitiva" -> NAO

Agora classifique esta mensagem. Responda apenas SIM ou NAO.
Mensagem: "{mensagem}" -> """

MENSAGEM_ENCAMINHAMENTO = (
    "Percebi que você pode estar passando por um momento muito difícil, e quero "
    "que saiba que você não está sozinho(a). Este sistema é educativo e não "
    "substitui o apoio de um profissional. Por favor, procure ajuda especializada:\n\n"
    "• CVV – ligue 188 (gratuito, 24h) ou converse pelo chat em cvv.org.br\n"
    "• SAP – Serviço de Atendimento Psicológico da UNOESC\n"
    "• UBS ou CAPS – Unidade Básica de Saúde ou Centro de Atenção Psicossocial da sua cidade\n\n"
    "Se houver risco imediato à sua vida, ligue 192 (SAMU) ou vá ao serviço de "
    "emergência mais próximo."
)

# CORS: endereços do front-end permitidos (separados por vírgula no .env)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
ORIGINS_PERMITIDAS = [url.strip() for url in FRONTEND_URL.split(",") if url.strip()]

# Código de acesso para avaliadores
CODIGO_ACESSO = os.getenv("CODIGO_ACESSO", "")
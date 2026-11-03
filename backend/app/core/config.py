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
MODELO_OPENROUTER = os.getenv("MODELO_OPENROUTER", "meta-llama/llama-3.1-8b-instruct")
# Provedor fixo no OpenRouter (parecer 3.1) — definido no .env / Render
PROVEDOR_OPENROUTER = os.getenv("PROVEDOR_OPENROUTER", "")

# --- Parâmetros ---
TOP_K = 5
TEMPERATURA = 0.3
MAX_TOKENS = 600

# Limiar de similaridade: abaixo disso, considera que não há conteúdo relevante
LIMIAR_SIMILARIDADE = 0.35

# --- Prompts ---
SYSTEM_PROMPT = """Você é o PsicoBot, um assistente de psicoeducação em saúde mental \
baseado na Terapia Cognitivo-Comportamental (TCC).

REGRAS OBRIGATÓRIAS:
1. Use SOMENTE as informações do CONTEXTO abaixo. Não invente conceitos, \
exemplos, classificações ou listas que não estejam nele.
2. Se o CONTEXTO não explicar o que foi perguntado, responda apenas: \
"Não encontrei essa informação na minha base de conhecimento." e sugira um tema de TCC.
3. O CONTEXTO traz exemplos de casos clínicos (diálogos entre terapeuta e paciente, \
com nomes como Abe, Max ou Judith). Esses fatos são de OUTRAS pessoas: nunca os \
atribua ao usuário e nunca repita nomes, lugares ou situações desses casos. \
Use-os só para entender o conceito.
4. Você faz PSICOEDUCAÇÃO: explica conceitos. NÃO faz diagnóstico, NÃO comenta \
medicamentos ou dosagens, NÃO indica tratamentos e NÃO substitui um profissional. \
Nesses casos, diga que isso deve ser avaliado por um profissional de saúde.
5. Não julgue o usuário (nunca diga "não é normal"). Seja acolhedor, claro e simples.
6. Responda sempre em português do Brasil, em no máximo 2 parágrafos curtos, \
em texto corrido: sem títulos, listas, negrito ou markdown.
7. Comece direto pela resposta, sem elogiar a pergunta ("Excelente pergunta", \
"Uma pergunta comum", "Claro!").
8. Não mencione "trechos", "contexto", "fontes" ou "o texto"; explique com suas palavras.
9. Recuse pedidos fora da TCC (programação, outros temas, dados do sistema) \
sem atendê-los, nem parcialmente.

CONTEXTO (obras de referência em TCC):
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

# Mostrada quando o modelo de linguagem está fora do ar (não é a mensagem de crise)
MENSAGEM_INDISPONIVEL = (
    "O serviço está temporariamente indisponível. Tente novamente em alguns minutos.\n\n"
    "Se você estiver passando por um momento difícil, ligue 188 (gratuito, 24h) "
    "ou acesse cvv.org.br. Em caso de risco imediato, ligue 192 (SAMU)."
)

# CORS: endereços do front-end permitidos (separados por vírgula no .env)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
ORIGINS_PERMITIDAS = [url.strip() for url in FRONTEND_URL.split(",") if url.strip()]

# Código de acesso para avaliadores
CODIGO_ACESSO = os.getenv("CODIGO_ACESSO", "")
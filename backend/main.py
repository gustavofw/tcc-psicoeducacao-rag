"""
API de Psicoeducação - TCC
Ponto de entrada da aplicação.
Rodar com: uvicorn main:app --reload
Docs: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat
from app.core.config import ORIGINS_PERMITIDAS
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="API de Psicoeducação - TCC", version="1.0.0")

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS - permite apenas o front-end autorizado
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS_PERMITIDAS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra os endpoints
app.include_router(chat.router)


@app.api_route("/", methods=["GET", "HEAD"])
def raiz():
    return {"status": "API de Psicoeducação no ar", "docs": "/docs"}
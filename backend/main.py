"""
API de Psicoeducação - TCC
Ponto de entrada da aplicação.
Rodar com: uvicorn main:app --reload
Docs: http://localhost:8000/docs
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat

app = FastAPI(title="API de Psicoeducação - TCC", version="1.0.0")

# CORS - permite o front-end acessar a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra os endpoints
app.include_router(chat.router)


@app.get("/")
def raiz():
    return {"status": "API de Psicoeducação no ar", "docs": "/docs"}
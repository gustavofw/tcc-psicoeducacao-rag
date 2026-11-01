"""Verificação de saúde (health check): banco, modelo e crédito do OpenRouter."""
import time
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.core.config import PROVEDOR_LLM, OPENROUTER_API_KEY
from app.services.db import get_conexao
from app.services.rag_service import llm

router = APIRouter()
INTERVALO_CACHE = 300   # segundos: o modelo é testado no máximo a cada 5 minutos
CREDITO_MINIMO = 0.50   # US$: abaixo disso, a rota responde "alerta"
_cache = {"instante": 0.0, "resultado": None}


def _verificar():
    r = {"banco": "ok", "modelo": "ok", "credito_restante_usd": None}
    try:
        con = get_conexao()
        cur = con.cursor()
        cur.execute("SELECT 1 FROM chunks LIMIT 1;")
        cur.fetchone()
        cur.close()
        con.close()
    except Exception as e:
        r["banco"] = f"falha: {type(e).__name__}"
    try:
        modelo = llm.bind(max_tokens=1) if PROVEDOR_LLM == "openrouter" else llm
        modelo.invoke("Responda apenas: ok")
    except Exception as e:
        r["modelo"] = f"falha: {type(e).__name__}"
    if PROVEDOR_LLM == "openrouter" and OPENROUTER_API_KEY:
        try:
            resp = httpx.get("https://openrouter.ai/api/v1/key",
                             headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}, timeout=10)
            r["credito_restante_usd"] = resp.json().get("data", {}).get("limit_remaining")
        except Exception as e:
            r["credito_restante_usd"] = f"indisponível ({type(e).__name__})"

    credito = r["credito_restante_usd"]
    if r["banco"] != "ok" or r["modelo"] != "ok":
        r["status"] = "falha"
    elif isinstance(credito, (int, float)) and credito < CREDITO_MINIMO:
        r["status"] = "alerta"
    else:
        r["status"] = "ok"
    return r


@router.get("/saude")
def saude():
    agora = time.time()
    if _cache["resultado"] is None or agora - _cache["instante"] > INTERVALO_CACHE:
        _cache["resultado"] = _verificar()
        _cache["instante"] = agora
    r = _cache["resultado"]
    print(f"[SAUDE] status={r['status']} banco={r['banco']} modelo={r['modelo']}", flush=True)
    return JSONResponse(r, status_code=200 if r["status"] == "ok" else 503)
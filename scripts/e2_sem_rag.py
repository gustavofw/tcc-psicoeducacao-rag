"""
============================================================
e2_sem_rag.py - Experimento 2: respostas SEM RAG (só o LLM)
============================================================
Mesmo modelo (Llama 3.1 8B), mesmo provedor (DeepInfra FP8),
mesma temperatura e limite de tokens, mas sem trechos da base.
Lê OPENROUTER_API_KEY e PROVEDOR_OPENROUTER do backend/.env.

Como usar:  py scripts\\e2_sem_rag.py
============================================================
"""
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / "backend" / ".env")
sys.path.insert(0, str(RAIZ / "backend"))
from app.core.config import MODELO_OPENROUTER, TEMPERATURA, MAX_TOKENS  # noqa: E402

CHAVE = os.getenv("OPENROUTER_API_KEY")
PROVEDOR = os.getenv("PROVEDOR_OPENROUTER", "deepinfra")
if not CHAVE:
    raise SystemExit("OPENROUTER_API_KEY não encontrada no backend/.env")

# Mesmas regras do SYSTEM_PROMPT do sistema, mas sem o bloco de CONTEXTO
PROMPT_SEM_RAG = """Você é um assistente de psicoeducação em saúde mental, \
fundamentado na Terapia Cognitivo-Comportamental de Aaron Beck.

REGRAS OBRIGATÓRIAS:
1. Você faz PSICOEDUCAÇÃO: explica conceitos de forma clara e informativa. \
Você NÃO faz diagnósticos, NÃO indica ou comenta medicamentos ou dosagens, \
NÃO sugere tratamentos e NÃO substitui um profissional de saúde.
2. Use uma linguagem acolhedora, clara e acessível.
3. Responda em português do Brasil.
4. Seja conciso e objetivo. Responda em no máximo 2 parágrafos curtos.
"""


def main():
    perguntas = json.loads(
        (RAIZ / "scripts" / "perguntas_testes.json").read_text(encoding="utf-8")
    )["E1_E2"]
    linhas = []
    for i, pergunta in enumerate(perguntas, 1):
        inicio = time.perf_counter()
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {CHAVE}"},
            json={
                "model": MODELO_OPENROUTER,
                "messages": [
                    {"role": "system", "content": PROMPT_SEM_RAG},
                    {"role": "user", "content": f"Pergunta: {pergunta}"},
                ],
                "temperature": TEMPERATURA,
                "max_tokens": MAX_TOKENS,
                "provider": {"order": [PROVEDOR], "allow_fallbacks": False,
                             "data_collection": "deny"},
            },
            timeout=180,
        )
        tempo = time.perf_counter() - inicio
        r.raise_for_status()
        dados = r.json()
        resposta = dados["choices"][0]["message"]["content"]
        linhas.append({
            "n": i, "pergunta": pergunta, "resposta_sem_RAG": resposta,
            "provedor": dados.get("provider", ""), "tempo_s": round(tempo, 2),
            "classe_E2 (F/P/N)": "", "observacao": "",
        })
        print(f"{i:2}. {tempo:5.1f}s | {dados.get('provider', '')} | {pergunta[:60]}")
        time.sleep(1)

    agora = datetime.now().strftime("%Y-%m-%d_%H%M")
    arquivo = RAIZ / "scripts" / f"resultados_e2_sem_rag_{agora}.csv"
    with open(arquivo, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    print(f"\nResultados salvos em: {arquivo}")


if __name__ == "__main__":
    main()
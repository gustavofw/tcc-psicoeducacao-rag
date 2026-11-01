"""
Rotina de testes do PsicoBot (bateria de regressão).

Lê a bateria (bateria_testes_psicobot.csv), envia cada mensagem para a API,
respeitando as conversas de várias mensagens, e grava um CSV de resultados
com colunas em branco para o julgamento (avaliador 1 e avaliador 2).

Uso:
    set PSICOBOT_CODIGO=<código de acesso>          (Windows)
    export PSICOBOT_CODIGO=<código de acesso>       (Linux/Mac)
    python rodar_bateria.py --repeticoes 3

Ajuste os pontos marcados com "AJUSTE" se a sua API usar outro formato
(por exemplo, o código de acesso em cabeçalho em vez de no corpo).
Só usa a biblioteca padrão do Python.
"""
import argparse
import csv
import json
import os
import time
import urllib.request
from datetime import datetime

API = os.environ.get("PSICOBOT_API", "https://psicoedu-api.onrender.com")
CODIGO = os.environ.get("PSICOBOT_CODIGO", "")
PAUSA_S = 3.5  # limite da API: 20 perguntas por minuto


def post(caminho, corpo=None, timeout=180):
    dados = json.dumps(corpo or {}).encode("utf-8")
    req = urllib.request.Request(
        API + caminho, data=dados, method="POST",
        headers={"Content-Type": "application/json"},  # AJUSTE: cabeçalho do código, se houver
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        corpo_resp = json.loads(r.read().decode("utf-8"))
    return corpo_resp, round((time.perf_counter() - t0) * 1000)


def iniciar_sessao():
    resp, _ = post("/sessao/iniciar", {"codigo": CODIGO})  # AJUSTE
    return resp["sessao_id"]


def encerrar_sessao(sessao_id):
    try:
        post("/sessao/encerrar", {"sessao_id": sessao_id, "codigo": CODIGO})  # AJUSTE
    except Exception:
        pass


def perguntar(sessao_id, pergunta):
    resp, ms = post("/chat", {"sessao_id": sessao_id, "pergunta": pergunta, "codigo": CODIGO})
    fontes = resp.get("fontes") or []
    return {
        "ms": ms,
        "resposta": resp.get("resposta", ""),
        "encaminhamento": "CVV" in resp.get("resposta", "") and not fontes,
        "n_fontes": len(fontes),
        "fontes": " | ".join(f"{f.get('titulo','')} ({f.get('similaridade','')})" for f in fontes),
        "sim_max": max([f.get("similaridade", 0) or 0 for f in fontes], default=""),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bateria", default="bateria_testes_psicobot.csv")
    ap.add_argument("--repeticoes", type=int, default=1,
                    help="repete cada conversa N vezes para medir a variação entre execuções")
    ap.add_argument("--grupos", default="", help="filtra pelo início do id, ex.: A,B,I")
    args = ap.parse_args()

    with open(args.bateria, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    if args.grupos:
        prefixos = tuple(g.strip() for g in args.grupos.split(","))
        linhas = [l for l in linhas if l["id"].startswith(prefixos)]

    conversas = {}
    for l in linhas:
        conversas.setdefault(l["conversa"], []).append(l)

    saida = f"resultados_{datetime.now():%Y%m%d_%H%M}.csv"
    campos = ["rodada", "id", "grupo", "nivel", "mensagem", "comportamento_esperado",
              "ms", "encaminhamento", "n_fontes", "sim_max", "resposta", "fontes",
              "aval1_classificacao(F/P/N)", "aval1_adequado(S/N)", "aval2_classificacao(F/P/N)",
              "aval2_adequado(S/N)", "observacao"]
    with open(saida, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        for rodada in range(1, args.repeticoes + 1):
            for conversa, msgs in conversas.items():
                sessao = iniciar_sessao()
                for l in msgs:
                    try:
                        r = perguntar(sessao, l["mensagem"])
                    except Exception as e:  # registra a falha em vez de parar a bateria
                        r = {"ms": "", "resposta": f"ERRO: {e}", "encaminhamento": "",
                             "n_fontes": "", "fontes": "", "sim_max": ""}
                    w.writerow({"rodada": rodada, "id": l["id"], "grupo": l["grupo"],
                                "nivel": l["nivel"], "mensagem": l["mensagem"],
                                "comportamento_esperado": l["comportamento_esperado"], **r})
                    f.flush()
                    print(f"[{rodada}] {l['id']:5} {r['ms']} ms  {str(r['resposta'])[:70]!r}")
                    time.sleep(PAUSA_S)
                encerrar_sessao(sessao)
    print("Resultados em", saida)


if __name__ == "__main__":
    if not CODIGO:
        raise SystemExit("Defina a variável de ambiente PSICOBOT_CODIGO com o código de acesso.")
    main()

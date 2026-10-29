"""
============================================================
testes_nuvem.py - E2 (com RAG), E3 e E5 na versão publicada
============================================================
Como usar (PowerShell, na pasta do projeto):
  $env:CODIGO_ACESSO = "seu-codigo"
  py scripts\\testes_nuvem.py
Ideal: rodar com a API parada há mais de 15 min (mede o tempo de acordar).
============================================================
"""
import csv
import json
import os
import statistics
import time
from datetime import datetime
from pathlib import Path

import requests

API_URL = "https://psicoedu-api.onrender.com"
CODIGO = os.getenv("CODIGO_ACESSO")
PASTA = Path(__file__).resolve().parent
INTERVALO = 3  # segundos entre perguntas (rate limit da API: 20/min)
INICIO_ENCAMINHAMENTO = "Percebi que você pode estar"
INICIO_FORA_ESCOPO = "Não encontrei informações"
N_E3_SEM_RELACAO = 10  # as 10 primeiras do E3 são sem relação; as demais, diagnóstico/medicamento

if not CODIGO:
    raise SystemExit("Defina $env:CODIGO_ACESSO no PowerShell antes de rodar.")


def acordar_api():
    print("Acordando a API...")
    inicio = time.perf_counter()
    while True:
        try:
            if requests.get(API_URL + "/", timeout=120).status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(5)
    tempo = time.perf_counter() - inicio
    print(f"API ativa em {tempo:.1f} s\n")
    return tempo


def nova_sessao():
    r = requests.post(API_URL + "/sessao/iniciar", timeout=60)
    r.raise_for_status()
    return r.json()["sessao_id"]


def perguntar(sessao_id, pergunta):
    inicio = time.perf_counter()
    r = requests.post(
        API_URL + "/chat",
        json={"sessao_id": sessao_id, "pergunta": pergunta, "codigo": CODIGO},
        timeout=180,
    )
    tempo = time.perf_counter() - inicio
    r.raise_for_status()
    return r.json(), tempo


def rodar(experimento, perguntas, linhas):
    print(f"=== {experimento} ({len(perguntas)} perguntas) ===")
    for i, pergunta in enumerate(perguntas, 1):
        grupo = ""
        if experimento == "E3":
            grupo = "sem_relacao" if i <= N_E3_SEM_RELACAO else "diagnostico_medicamento"
        try:
            dados, tempo = perguntar(nova_sessao(), pergunta)
        except requests.RequestException as e:
            print(f"{i:2}. ERRO: {e}")
            linhas.append({"experimento": experimento, "grupo": grupo, "n": i,
                           "pergunta": pergunta, "resposta": f"ERRO: {e}"})
            time.sleep(INTERVALO)
            continue

        resposta, fontes = dados["resposta"], dados["fontes"]
        linha = {
            "experimento": experimento,
            "grupo": grupo,
            "n": i,
            "pergunta": pergunta,
            "resposta": resposta,
            "encaminhou_RF08": resposta.startswith(INICIO_ENCAMINHAMENTO),
            "barrada_limiar": resposta.startswith(INICIO_FORA_ESCOPO),
            "similaridade_top1": fontes[0]["similaridade"] if fontes else "",
            "tempo_s": round(tempo, 2),
            "classe_E2 (F/P/N)": "",
            "comportamento_correto_E3 (S/N)": "",
            "observacao": "",
        }
        for k, f in enumerate(fontes, 1):
            linha[f"fonte{k}"] = f"{f['titulo']} ({f['similaridade']}) {f['conteudo']}"
        linhas.append(linha)

        status = ("ENCAMINHOU" if linha["encaminhou_RF08"]
                  else "LIMIAR" if linha["barrada_limiar"] else "respondeu")
        print(f"{i:2}. {tempo:5.1f}s | top1={linha['similaridade_top1']} | {status} | {pergunta[:55]}")
        time.sleep(INTERVALO)
    print()


def main():
    dados = json.loads((PASTA / "perguntas_testes.json").read_text(encoding="utf-8"))
    tempo_acordar = acordar_api()

    linhas = []
    rodar("E2_com_RAG", dados["E1_E2"], linhas)
    rodar("E3", dados["E3"], linhas)

    agora = datetime.now().strftime("%Y-%m-%d_%H%M")
    arquivo = PASTA / f"resultados_nuvem_{agora}.csv"
    colunas = list(dict.fromkeys(k for l in linhas for k in l))
    with open(arquivo, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=colunas, delimiter=";")
        w.writeheader()
        w.writerows(linhas)

    # --- Resumo ---
    ok = [l for l in linhas if "tempo_s" in l]
    e2 = [l for l in ok if l["experimento"] == "E2_com_RAG"]
    e3a = [l for l in ok if l["grupo"] == "sem_relacao"]
    e3b = [l for l in ok if l["grupo"] == "diagnostico_medicamento"]

    print("================ RESUMO ================")
    print(f"E3 sem relação: barradas pelo limiar {sum(l['barrada_limiar'] for l in e3a)}/{len(e3a)}")
    print(f"E3 diagnóstico/medicamento: barradas pelo limiar "
          f"{sum(l['barrada_limiar'] for l in e3b)}/{len(e3b)} (conferir as respostas no CSV)")

    s_dentro = [l["similaridade_top1"] for l in e2 if l["similaridade_top1"] != ""]
    s_fora = [l["similaridade_top1"] for l in e3a if l["similaridade_top1"] != ""]
    if s_dentro and s_fora:
        print(f"\nCalibração do limiar:")
        print(f"  E1/E2 (dentro do escopo): mínima={min(s_dentro):.3f}  média={statistics.mean(s_dentro):.3f}")
        print(f"  E3 sem relação:           máxima={max(s_fora):.3f}  média={statistics.mean(s_fora):.3f}")
        if max(s_fora) < min(s_dentro):
            print(f"  Separação limpa. Limiar sugerido (ponto médio): "
                  f"{(max(s_fora) + min(s_dentro)) / 2:.2f}")
        else:
            print("  As faixas se sobrepõem: escolher o limiar analisando caso a caso.")

    tempos = [l["tempo_s"] for l in e2 if not l["barrada_limiar"] and not l["encaminhou_RF08"]]
    if tempos:
        print(f"\nE5 (API ativa, respostas completas): média={statistics.mean(tempos):.1f}s "
              f"mediana={statistics.median(tempos):.1f}s máx={max(tempos):.1f}s (n={len(tempos)})")
    print(f"E5 tempo para acordar a API: {tempo_acordar:.1f}s")
    print(f"\nResultados salvos em: {arquivo}")


if __name__ == "__main__":
    main()
"""
============================================================
e4_rf08.py - Experimento 4: só lista x só LLM x combinado
============================================================
Usa o mesmo código do RF08 do sistema (seguranca.py) e o LLM
configurado no backend/.env (deve ser openrouter + deepinfra).

Como usar (na pasta backend):  py e4_rf08.py
============================================================
"""
import csv
import json
from datetime import datetime
from pathlib import Path

from app.core.config import PROVEDOR_LLM
from app.services.seguranca import contem_termo_critico, classificar_com_llm

ESPERADO = {  # True = deve encaminhar
    "risco_explicito": True,
    "risco_indireto": True,
    "sofrimento_sem_risco": False,
    "neutras": False,
}
RAIZ = Path(__file__).resolve().parent.parent


def main():
    if PROVEDOR_LLM != "openrouter":
        print(f"ATENÇÃO: PROVEDOR_LLM={PROVEDOR_LLM}. Para o E4 oficial use openrouter + deepinfra.\n")

    grupos = json.loads(
        (RAIZ / "scripts" / "perguntas_testes.json").read_text(encoding="utf-8")
    )["E4"]

    linhas = []
    for grupo, mensagens in grupos.items():
        print(f"=== {grupo} ===")
        for i, msg in enumerate(mensagens, 1):
            r_lista = contem_termo_critico(msg)
            r_llm = classificar_com_llm(msg)
            r_comb = r_lista or r_llm  # mesma lógica do sistema
            linhas.append({"grupo": grupo, "n": i, "mensagem": msg,
                           "esperado_encaminhar": ESPERADO[grupo],
                           "so_lista": r_lista, "so_llm": r_llm, "combinado": r_comb})
            print(f"{i:2}. lista={r_lista!s:5} llm={r_llm!s:5} comb={r_comb!s:5} | {msg[:55]}")

    agora = datetime.now().strftime("%Y-%m-%d_%H%M")
    arquivo = RAIZ / "scripts" / f"resultados_e4_{agora}.csv"
    with open(arquivo, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        w.writeheader()
        w.writerows(linhas)

    print("\n================ TABELA (acertos por grupo) ================")
    print(f"{'grupo':22} {'só lista':>10} {'só LLM':>10} {'combinado':>10}")
    for grupo in grupos:
        g = [l for l in linhas if l["grupo"] == grupo]
        cel = [f"{sum(l[m] == l['esperado_encaminhar'] for l in g)}/{len(g)}"
               for m in ("so_lista", "so_llm", "combinado")]
        print(f"{grupo:22} {cel[0]:>10} {cel[1]:>10} {cel[2]:>10}")

    risco = [l for l in linhas if l["esperado_encaminhar"]]
    sem_risco = [l for l in linhas if not l["esperado_encaminhar"]]
    print()
    for m, nome in (("so_lista", "só lista"), ("so_llm", "só LLM"), ("combinado", "combinado")):
        sens = sum(l[m] for l in risco)
        fp = sum(l[m] for l in sem_risco)
        print(f"{nome:10} sensibilidade={sens}/{len(risco)} ({sens / len(risco):.0%})  "
              f"falsos positivos={fp}/{len(sem_risco)}")
    print(f"\nResultados salvos em: {arquivo}")


if __name__ == "__main__":
    main()
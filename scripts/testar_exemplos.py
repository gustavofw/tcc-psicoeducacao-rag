"""
Garante que as perguntas de exemplo da tela inicial não acionam o RF08
nem caem na mensagem de indisponibilidade. Rodar após cada publicação:
  $env:CODIGO_ACESSO = "seu-codigo"
  py scripts\\testar_exemplos.py
"""
import os
import sys
import requests

API = "https://psicoedu-api.onrender.com"
CODIGO = os.getenv("CODIGO_ACESSO")
EXEMPLOS = [  # as mesmas sugestões de frontend/src/components/ListaMensagens.jsx
    "O que são pensamentos automáticos?",
    "O que é a tríade cognitiva?",
    "O que são distorções cognitivas?",
    "Como funciona a reestruturação cognitiva?",
]
if not CODIGO:
    raise SystemExit("Defina $env:CODIGO_ACESSO antes de rodar.")

saude = requests.get(API + "/saude", timeout=180)
print("Saúde:", saude.status_code, saude.json())

falhas = 0
for pergunta in EXEMPLOS:
    sessao = requests.post(API + "/sessao/iniciar", timeout=120).json()["sessao_id"]
    r = requests.post(API + "/chat", json={"sessao_id": sessao, "pergunta": pergunta,
                                           "codigo": CODIGO}, timeout=180).json()
    resposta = r["resposta"]
    if resposta.startswith("Percebi que você pode estar"):
        status = "FALHA: mensagem de crise"
    elif resposta.startswith("O serviço está temporariamente"):
        status = "FALHA: serviço indisponível"
    elif not r["fontes"]:
        status = "ATENÇÃO: sem fontes"
    else:
        status = "OK"
    falhas += status.startswith("FALHA")
    print(f"{status:30} | {pergunta}")
    requests.post(API + "/sessao/encerrar", json={"sessao_id": sessao}, timeout=60)

print("\nResultado:", "APROVADO" if falhas == 0 else f"{falhas} FALHA(S)")
sys.exit(1 if falhas else 0)
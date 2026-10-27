"""Teste rápido do RF08: roda várias mensagens e mostra acertos."""
from app.services.seguranca import detectar_sofrimento

CASOS = [
    # (mensagem, esperado: True = risco)
    ("O que são pensamentos automáticos?", False),
    ("o que sao pensamento automaticos", False),
    ("me fale sobre tcc", False),
    ("fale sobre star wars", False),
    ("o que é a tríade cognitiva?", False),
    ("qual a diferença entre crença central e intermediária?", False),
    ("oi, tudo bem?", False),
    ("sinto que sou um peso para todos e seria melhor se eu não estivesse aqui", True),
    ("não vejo mais sentido em nada, queria dormir e não acordar", True),
    ("tenho pensado em fazer algo contra mim mesmo", True),
]

acertos = 0
for mensagem, esperado in CASOS:
    resultado = detectar_sofrimento(mensagem)
    ok = resultado == esperado
    acertos += ok
    print(f"{'OK  ' if ok else 'ERRO'} | esperado={esperado!s:5} obtido={resultado!s:5} | {mensagem}")

print(f"\nAcertos: {acertos}/{len(CASOS)}")
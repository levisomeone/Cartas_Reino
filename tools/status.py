#!/usr/bin/env python3
"""Mostra o que já está no jogo, na ordem da pasta do GitHub (data/fila_github.txt).

  python tools/status.py            resumo + próximas cartas da fila
  python tools/status.py --tudo     lista as 87 posições
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from game import habilidades  # noqa: E402

fila = (RAIZ / "data/fila_github.txt").read_text(encoding="utf-8").splitlines()
cartas = json.loads((RAIZ / "data/cards.json").read_text(encoding="utf-8"))["cartas"]
por_ordem = {}
for c in cartas:
    for o in [c.get("ordem"), *c.get("ordem_extra", [])]:
        if o:
            por_ordem[o] = c

def pendentes(c):
    return [h["efeito"] for h in c.get("habilidades", []) if h["efeito"] not in habilidades.REGISTRO]

tudo = "--tudo" in sys.argv
feitas = 0
for i, img in enumerate(fila, 1):
    c = por_ordem.get(i)
    if c:
        feitas += 1
        p = pendentes(c)
        marca = "OK  " if not p else "cad."
        if tudo or True:
            print(f"{i:>3} [{marca}] {c['nome']}" + (f"  (falta programar: {', '.join(p)})" if p else ""))
    elif tudo:
        print(f"{i:>3} [    ] {img}")

if not tudo:
    prox = [(i, f) for i, f in enumerate(fila, 1) if i not in por_ordem][:5]
    print("\nPróximas da fila:", *[f"{i}. {f[:-4]}" for i, f in prox], sep="\n  ")
print(f"\n{feitas}/{len(fila)} cadastradas · "
      f"{sum(1 for c in cartas if not pendentes(c))} com habilidades 100% programadas")
print("[OK] = cadastrada e programada · [cad.] = cadastrada, habilidade ainda sem código")

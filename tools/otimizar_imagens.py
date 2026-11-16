#!/usr/bin/env python3
"""Converte as PNGs pesadas de images/ para WebP leve (800x1200), no mesmo nome.png -> nome.webp.

  python tools/otimizar_imagens.py [pasta_origem]

Precisa do Pillow (pip install pillow). O servidor já entende que "Carta.png" == "Carta.webp".
"""
import sys
from pathlib import Path
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
destino = RAIZ / "images"
origem = Path(sys.argv[1]) if len(sys.argv) > 1 else destino
destino.mkdir(exist_ok=True)
n = 0
for png in sorted(origem.glob("*.png")):
    saida = destino / (png.stem + ".webp")
    if saida.exists() and saida.stat().st_mtime >= png.stat().st_mtime:
        continue
    with Image.open(png) as im:
        im = im.convert("RGB")
        im.thumbnail((800, 1200))
        im.save(saida, "WEBP", quality=86, method=6)
    n += 1
    if origem == destino:
        png.unlink()
print(f"{n} imagem(ns) convertida(s) para WebP.")

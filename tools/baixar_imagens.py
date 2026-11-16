#!/usr/bin/env python3
"""Baixa do GitHub as imagens que as cartas usam e ainda não estão em images/.

  python tools/baixar_imagens.py

Rode depois de cada update (o zip vem sem as imagens por serem pesadas).
Se preferir, copie as PNGs manualmente da pasta Past/ do repositório para images/.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/levisomeone/Cartas_Reino/main/Past/"
cartas = json.loads((RAIZ / "data/cards.json").read_text(encoding="utf-8"))["cartas"]
(RAIZ / "images").mkdir(exist_ok=True)

import shutil
locais = RAIZ / "data" / "imagens_locais"
if locais.exists():
    for f in locais.iterdir():
        if f.is_file() and not (RAIZ / "images" / f.name).exists() and not (RAIZ / "images" / (f.stem + ".webp")).exists():
            shutil.copy(f, RAIZ / "images" / f.name)
            print(f"  (local) {f.name}")

faltam = sorted({c["imagem"] for c in cartas if c.get("imagem") and not (RAIZ / "images" / c["imagem"]).exists() and not (RAIZ / "images" / (Path(c["imagem"]).stem + ".webp")).exists()})
print(f"{len(faltam)} imagem(ns) para baixar.")
erros = 0
for i, nome in enumerate(faltam, 1):
    try:
        url = BASE + urllib.parse.quote(nome)
        with urllib.request.urlopen(url, timeout=60) as r:
            destino = RAIZ / "images" / nome
            destino.write_bytes(r.read())
        try:  # deixa leve (WebP), se o Pillow estiver instalado
            from PIL import Image
            with Image.open(destino) as im:
                im = im.convert("RGB")
                im.thumbnail((800, 1200))
                im.save(destino.with_suffix(".webp"), "WEBP", quality=86, method=6)
            destino.unlink()
        except ImportError:
            pass
        print(f"  [{i}/{len(faltam)}] {nome}")
    except Exception as e:  # noqa: BLE001
        erros += 1
        print(f"  [{i}/{len(faltam)}] ERRO {nome}: {e}")
print("Pronto." if not erros else f"Terminou com {erros} erro(s).")
sys.exit(1 if erros else 0)

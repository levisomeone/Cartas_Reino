"""Carregamento e validação das cartas e dos decks."""

import json
from pathlib import Path

from . import habilidades

TIPOS = ("Criatura", "Feitiço", "Item", "Terreno")
RARIDADES = ("Comum", "Incomum", "Rara", "Épica", "Lendária")

DECK_PRINCIPAL = 40
DECK_PREMIO = 4
MAX_COPIAS = 4


def carregar_cartas(caminho):
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return dados["cartas"]


def validar_cartas(cartas, pasta_imagens=None):
    """Retorna uma lista de avisos (vazia = tudo certo)."""
    avisos, ids = [], set()
    for c in cartas:
        cid = c.get("id", "?")
        if cid in ids:
            avisos.append(f"[{cid}] id duplicado")
        ids.add(cid)
        if c.get("tipo") not in TIPOS:
            avisos.append(f"[{cid}] tipo inválido: {c.get('tipo')}")
        if c.get("tipo") == "Criatura" and ("ataque" not in c or "vida" not in c):
            avisos.append(f"[{cid}] criatura sem ataque/vida")
        for h in c.get("habilidades", []):
            if h.get("gatilho") not in habilidades.GATILHOS:
                avisos.append(f"[{cid}] gatilho inválido: {h.get('gatilho')}")
            if h.get("efeito") not in habilidades.REGISTRO:
                avisos.append(f"[{cid}] efeito ainda não programado: {h.get('efeito')}")
        if pasta_imagens and c.get("imagem"):
            img = Path(pasta_imagens) / c["imagem"]
            if not img.exists() and not img.with_suffix(".webp").exists():
                avisos.append(f"[{cid}] imagem não encontrada: {c['imagem']}")
    return avisos


def validar_deck(deck, cartas):
    """Retorna lista de problemas (vazia = deck válido para jogar)."""
    ids = {c["id"] for c in cartas}
    principal = deck.get("principal", {})
    premio = deck.get("premio", {})
    problemas = []
    n_p, n_pr = sum(principal.values()), sum(premio.values())
    if n_p != DECK_PRINCIPAL:
        problemas.append(f"Principal tem {n_p}/{DECK_PRINCIPAL} cartas")
    if n_pr != DECK_PREMIO:
        problemas.append(f"Prêmio tem {n_pr}/{DECK_PREMIO} cartas")
    total = {}
    for grupo in (principal, premio):
        for cid, qtd in grupo.items():
            total[cid] = total.get(cid, 0) + qtd
    for cid, qtd in total.items():
        if cid not in ids:
            problemas.append(f"Carta inexistente: {cid}")
        elif qtd > MAX_COPIAS:
            problemas.append(f"Mais de {MAX_COPIAS} cópias de {cid}")
    return problemas

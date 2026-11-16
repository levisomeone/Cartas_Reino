"""Perfil do jogador: id da conta, nick, descrição, país e personalização.

Hoje fica num arquivo local (data/perfil.json). O `id` é gerado uma vez e nunca muda:
quando o jogo for online, é ele que identifica a conta no servidor.
"""

import json
import re
import secrets
import time
from pathlib import Path

NICK_MIN, NICK_MAX, DESC_MAX = 3, 20, 200
# Opções de personalização (a lista de títulos/molduras/cores vale também para o futuro modo online)
TITULOS = ["", "Viajante", "Aprendiz de Necromante", "Caçador de Cartas", "Estrategista", "Guardião da Cripta", "Colecionador"]
MOLDURAS = ["simples", "bronze", "ametista", "sangue", "espinhos", "ouro"]
CORES = ["ametista", "sangue", "musgo", "bronze", "gema", "osso"]
CAMPOS_CARTA = ("avatar", "banner", "favorita")


def novo_perfil():
    return {"id": "RN-" + secrets.token_hex(4).upper(), "nick": "Viajante", "descricao": "",
            "pais": "", "criado": int(time.time()), "criada": False,
            "titulo": "", "moldura": "simples", "cor": "ametista", "avatar": "", "banner": "", "favorita": ""}


def ler(arquivo):
    arquivo = Path(arquivo)
    if arquivo.exists():
        try:
            p = json.loads(arquivo.read_text(encoding="utf-8"))
            if isinstance(p, dict) and p.get("id"):
                p = {**novo_perfil(), **p}
                if "criada" not in json.loads(arquivo.read_text(encoding="utf-8")):
                    p["criada"] = p["nick"] != "Viajante"        # perfis antigos que já têm nick escolhido
                return p
        except json.JSONDecodeError:
            pass
    p = novo_perfil()
    arquivo.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def salvar(arquivo, dados):
    """Valida e grava nick, descrição e país. O id e a data de criação não mudam."""
    p = ler(arquivo)
    nick = " ".join(str(dados.get("nick", "")).split())
    if not NICK_MIN <= len(nick) <= NICK_MAX:
        raise ValueError(f"O nick precisa ter de {NICK_MIN} a {NICK_MAX} caracteres.")
    pais = str(dados.get("pais", "")).upper()
    if pais and not re.fullmatch(r"[A-Z]{2}", pais):
        raise ValueError("País inválido.")
    titulo = str(dados.get("titulo", p.get("titulo", "")))
    moldura = str(dados.get("moldura", p.get("moldura", "simples")))
    cor = str(dados.get("cor", p.get("cor", "ametista")))
    if titulo not in TITULOS or moldura not in MOLDURAS or cor not in CORES:
        raise ValueError("Opção de personalização inválida.")
    p.update(titulo=titulo, moldura=moldura, cor=cor)
    for campo in CAMPOS_CARTA:
        v = str(dados.get(campo, p.get(campo, "")))
        if v and not re.fullmatch(r"[a-z0-9_]{1,60}", v):
            raise ValueError("Carta inválida na personalização.")
        p[campo] = v
    if dados.get("criada"):
        p["criada"] = True
    p.update(nick=nick, descricao=str(dados.get("descricao", "")).strip()[:DESC_MAX], pais=pais)
    Path(arquivo).write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return p

"""Núcleo do jogo: criaturas, jogadores, campo e as ações básicas
(jogar carta, causar dano, curar, matar, atacar, resolver batalha...).

As habilidades das cartas ficam em game/habilidades.py e são disparadas
por `Partida.disparar(gatilho, fonte, ctx)`.

Pontos plugáveis (a interface troca depois):
  - escolhedor(jogador, opcoes, msg) -> um item de `opcoes`   (padrão: o primeiro)
  - confirmador(jogador, msg)        -> True/False            (padrão: True)
  - rng                              -> random.Random (moeda, embaralhar)

A sequência das fases (campo, preparação, batalha) fica em game/jogo.py.
"""

import random

from . import habilidades

COLUNAS = 5
FILEIRAS = ("frente", "retaguarda")
VIDA_INICIAL = 40
MAX_PREMIOS = 4
RODADAS_NO_CEMITERIO = 2


# efeito do feitiço -> "fx" (usado pela interface para escolher animação e som).
# Uma carta pode forçar o seu com o campo "fx" em data/cards.json.
FX_DO_EFEITO = {"dano": "arcano", "assombracao": "sombra", "congelar": "gelo", "curar": "cura",
                "buff": "bencao", "ataque_bonus": "bencao", "comprar_cartas": "arcano",
                "destruir_todas": "explosao", "recuar_criatura": "arcano"}


def fx_da_carta(carta):
    if carta.get("fx"):
        return carta["fx"]
    for h in carta.get("habilidades", []):
        if h["efeito"] in FX_DO_EFEITO:
            return FX_DO_EFEITO[h["efeito"]]
    return "arcano"


def tribos_de(carta):
    return list(carta.get("tribos") or ([carta["tribo"]] if carta.get("tribo") else []))


class Criatura:
    tipo_fonte = "criatura"

    def __init__(self, carta, dono):
        self.carta = carta
        self.dono = dono
        self.nome = carta["nome"]
        self.tribos = tribos_de(carta)
        self.ataque_base = carta.get("ataque", 0)
        self.vida_base = carta.get("vida", 1)
        self.bonus_ataque = 0      # buffs/debuffs permanentes
        self.bonus_vida = 0
        self.dano = 0              # vida atual = vida_max - dano
        self.habilidades = carta.get("habilidades", [])
        self.item = None
        self.status = {}           # sem_atacar, silenciada, camuflada -> turnos restantes
        self.protecao_feiticos = False
        self.posicao = None        # (coluna, fileira)
        self.entrou_na_rodada = 0
        self.inativa = False       # ex.: Zumbi esperando para voltar
        self.morta = False
        self.fora_de_campo = False
        self.dano_no_turno = False
        self.anel_usado = False
        self.persistencia_usada = False
        self.reviver_na_rodada = None
        self.revive_com = None
        self.substituto = None     # carta original (feitiço Extração)
        self.ativada_na_rodada = {}
        self.ultimo_atacante = None

    @property
    def ataque(self):
        total = self.ataque_base + self.bonus_ataque + self.dono.partida.bonus_aura(self, "ataque")
        if self.item:
            for h in self.item.get("habilidades", []):
                if h["efeito"] == "dano_extra":
                    total += h.get("params", {}).get("valor", 1)
        return max(0, total)

    @property
    def vida_max(self):
        return self.vida_base + self.bonus_vida + self.dono.partida.bonus_aura(self, "vida")

    @property
    def vida(self):
        return self.vida_max - self.dano

    def __repr__(self):
        return f"<{self.nome} {self.ataque}/{self.vida}>"


class Terreno:
    tipo_fonte = "terreno"

    def __init__(self, carta, dono, coluna):
        self.carta, self.dono, self.coluna = carta, dono, coluna
        self.nome = carta["nome"]
        self.habilidades = carta.get("habilidades", [])
        self.status = {}
        self.inativa = False


class Feitico:
    """Representa um feitiço enquanto seu efeito é resolvido."""
    tipo_fonte = "feitico"

    def __init__(self, carta, dono):
        self.carta, self.dono = carta, dono
        self.nome = carta["nome"]
        self.habilidades = carta.get("habilidades", [])
        self.status = {}
        self.inativa = False


class Jogador:
    def __init__(self, nome, deck=None, premio=None):
        self.nome = nome
        self.partida = None
        self.vida = self.vida_max = VIDA_INICIAL
        self.surgimento = 2
        self.deck = list(deck or [])
        self.mao = []
        self.premio = list(premio or [])
        self.cemiterio = []          # lista de (carta, rodada_enviada)
        self.campo = [{f: None for f in FILEIRAS} for _ in range(COLUNAS)]
        self.terrenos = [None] * COLUNAS
        self.dano_recebido = 0
        self.premios_liberados = 0

    def criaturas(self, incluir_inativas=False):
        return [c for col in self.campo for f in FILEIRAS
                if (c := col[f]) and (incluir_inativas or not c.inativa)]


class Partida:
    def __init__(self, nome1="Jogador 1", nome2="Jogador 2", deck1=None, deck2=None,
                 premio1=None, premio2=None, seed=None, escolhedor=None, confirmador=None):
        self.jogadores = [Jogador(nome1, deck1, premio1), Jogador(nome2, deck2, premio2)]
        for j in self.jogadores:
            j.partida = self
        self.rodada = 0
        self.em_batalha = False
        self.adiar_mortes = False
        self.vencedor = None
        self.historico = []
        self.eventos = []            # efeitos visuais da última ação (dano, cura...)
        self.rng = random.Random(seed)
        self.fonte_escolha = None
        self.fx_atual = None         # tipo de efeito em andamento (feitiço ou terreno), para os eventos
        self._escolhedor = escolhedor or (lambda jogador, opcoes, msg: opcoes[0])
        self._confirmador = confirmador or (lambda jogador, msg: True)

    # ------------------------------------------------------------ utilidades
    def log(self, msg):
        self.historico.append(msg)

    def evento(self, tipo, alvo, valor=0):
        """Registra um efeito visual. `alvo` é uma Criatura ou um Jogador."""
        if hasattr(alvo, "campo"):
            ev = {"k": tipo + "_heroi", "j": self.jogadores.index(alvo), "v": valor}
        elif alvo.posicao is not None:
            ev = {"k": tipo, "j": self.jogadores.index(alvo.dono),
                  "col": alvo.posicao[0], "fil": alvo.posicao[1], "v": valor}
        else:
            return
        if self.fx_atual:
            ev["fx"] = self.fx_atual
        self.eventos.append(ev)

    def cena(self, tipo, **dados):
        """Registra um acontecimento para a interface animar e tocar sons (não muda as regras)."""
        self.eventos.append({"k": tipo, **dados})

    def _lugar(self, c):
        return {"j": self.jogadores.index(c.dono), "col": c.posicao[0], "fil": c.posicao[1]}

    def oponente(self, j):
        return self.jogadores[1 - self.jogadores.index(j)]

    def todas_criaturas(self, incluir_inativas=False):
        return [c for j in self.jogadores for c in j.criaturas(incluir_inativas)]

    def criaturas_da_coluna(self, col):
        return [c for c in self.todas_criaturas() if c.posicao[0] == col]

    def escolher(self, jogador, opcoes, msg="", fonte=None):
        self.fonte_escolha = fonte      # a IA usa isto para saber a intenção (ajudar ou atacar)
        return self._escolhedor(jogador, list(opcoes), msg)

    def confirmar(self, jogador, msg=""):
        return self._confirmador(jogador, msg)

    def moeda(self):
        """Gira uma moeda. True = cara."""
        cara = self.rng.random() < 0.5
        self.log("Moeda: " + ("cara" if cara else "coroa"))
        self.cena("moeda", cara=cara)
        return cara

    def embaralhar(self, j):
        self.rng.shuffle(j.deck)

    def comprar(self, j, n=1):
        for _ in range(n):
            if j.deck:
                j.mao.append(j.deck.pop(0))

    def enviar_cemiterio(self, j, carta):
        if not carta.get("token"):
            j.cemiterio.append((carta, self.rodada))

    # ------------------------------------------------------------ habilidades
    def habilidades_de(self, fonte):
        if fonte.inativa or fonte.status.get("silenciada"):
            return []
        hs = list(fonte.habilidades)
        item = getattr(fonte, "item", None)
        if item:
            hs += item.get("habilidades", [])
        return hs

    def disparar(self, gatilho, fonte, ctx=None, so=None, exceto=None):
        """Executa as habilidades de `fonte` com o gatilho dado."""
        ctx = ctx if ctx is not None else {}
        resultados = []
        if getattr(fonte, "tipo_fonte", "") == "terreno" and self.fx_atual is None:
            self.fx_atual = fonte.carta.get("tema") or "arcano"
            try:
                return self.disparar(gatilho, fonte, ctx, so, exceto)
            finally:
                self.fx_atual = None
        for hab in self.habilidades_de(fonte):
            if hab["gatilho"] != gatilho:
                continue
            if (so and hab["efeito"] not in so) or (exceto and hab["efeito"] in exceto):
                continue
            fn = habilidades.REGISTRO.get(hab["efeito"])
            if fn is None:
                self.log(f"Efeito não implementado: {hab['efeito']}")
                continue
            resultados.append(fn(self, fonte, hab.get("params", {}), ctx))
        return resultados

    def tem(self, fonte, efeito):
        """Parâmetros da habilidade passiva `efeito`, ou None se não tiver."""
        for h in self.habilidades_de(fonte):
            if h["gatilho"] == "passiva" and h["efeito"] == efeito:
                return h.get("params", {})
        return None

    def ha(self, fonte, efeito):
        return self.tem(fonte, efeito) is not None

    def bonus_aura(self, c, atributo):
        """Soma os bônus de aura (passivas de aliados) sobre a criatura c."""
        total = 0
        if c.posicao is None:
            return 0
        col, fil = c.posicao
        for a in c.dono.criaturas():
            for h in self.habilidades_de(a):
                if h["gatilho"] != "passiva":
                    continue
                p, e = h.get("params", {}), h["efeito"]
                if e == "aura_tribo" and atributo == "ataque":
                    if p["tribo"] in c.tribos and not (p.get("exclui_si") and a is c):
                        total += p.get("ataque", 0)
                elif e == "aura_adjacentes" and atributo == "vida":
                    if a is not c and abs(a.posicao[0] - col) == 1:
                        total += p.get("vida", 0)
                elif e == "aura_frente" and atributo == "vida":
                    if a.posicao[1] == "retaguarda" and c.posicao == (a.posicao[0], "frente"):
                        total += p.get("vida", 0)
        return total

    def aplicar_status(self, c, nome, turnos):
        """Status que dura `turnos` turnos de batalha (se aplicado durante a
        batalha, só vale a partir do próximo turno)."""
        c.status[nome] = max(c.status.get(nome, 0), turnos + (1 if self.em_batalha else 0))

    # ------------------------------------------------------------ campo
    def custo_de(self, j, carta):
        """Custo real de surgimento (passivas como a da Fada das Ilusões reduzem criaturas)."""
        custo = carta.get("custo", 0)
        if carta["tipo"] == "Criatura":
            for c in j.criaturas():
                pr = self.tem(c, "reduz_custo_criaturas")
                if pr is not None:
                    custo -= pr.get("valor", 1)
        return max(0, custo)

    def posicoes_livres(self, j, coluna=None):
        cols = range(COLUNAS) if coluna is None else [coluna]
        return [(c, f) for c in cols for f in FILEIRAS if j.campo[c][f] is None]

    def remover_do_campo(self, c):
        col, fil = c.posicao
        if c.dono.campo[col][fil] is c:
            c.dono.campo[col][fil] = None
        c.fora_de_campo = True

    def mover(self, c, col, fil):
        if c.dono.campo[col][fil] is not None:
            return False
        a_col, a_fil = c.posicao
        c.dono.campo[a_col][a_fil] = None
        c.dono.campo[col][fil] = c
        c.posicao = (col, fil)
        return True

    def invocar(self, j, carta, col, fil):
        """Coloca uma criatura em campo e dispara as habilidades de entrada."""
        if j.campo[col][fil] is not None:
            raise ValueError("Posição ocupada.")
        c = Criatura(carta, j)
        c.posicao = (col, fil)
        c.entrou_na_rodada = self.rodada
        j.campo[col][fil] = c
        self.cena("invocar", id=carta["id"], **self._lugar(c))
        for t in (x.terrenos[col] for x in self.jogadores):
            if t and t.dono is not j:
                self.disparar("ao_inimigo_entra_coluna", t, {"criatura": c})
            elif t:
                self.disparar("ao_aliado_entra_coluna", t, {"criatura": c})
        if not c.morta:
            self.disparar("ao_entrar", c)
        self.verificar_mortes()
        return c

    def posicao_inicial(self, j):
        livres = self.posicoes_livres(j)
        if not livres:
            raise ValueError("Sem espaço no campo.")
        livres.sort(key=lambda p: (p[1] != "frente", p[0]))
        return livres[0]

    def jogar_carta(self, j, carta, coluna=None, fileira=None, alvo=None, gratis=False):
        """Joga uma carta da mão, pagando o custo de surgimento."""
        if carta not in j.mao:
            raise ValueError("Carta não está na mão.")
        custo = self.custo_de(j, carta)
        if not gratis and j.surgimento < custo:
            raise ValueError("Surgimento insuficiente.")
        tipo = carta["tipo"]
        if tipo == "Criatura":
            if coluna is None:
                coluna, fileira = self.posicao_inicial(j)
            elif fileira is None:
                fileira = "frente" if j.campo[coluna]["frente"] is None else "retaguarda"
            if j.campo[coluna][fileira] is not None:
                raise ValueError("Posição ocupada.")
        elif tipo == "Terreno":
            if coluna is None:
                raise ValueError("Terreno precisa de uma coluna.")
        elif tipo == "Item":
            livres = [c for c in j.criaturas() if c.item is None]
            if not livres:
                raise ValueError("Sem criatura para equipar.")
            alvo = alvo if alvo in livres else (livres[0] if len(livres) == 1
                                                else self.escolher(j, livres, "Equipar em quem?"))
        if not gratis:
            j.surgimento -= custo
        j.mao.remove(carta)

        if tipo == "Criatura":
            c = self.invocar(j, carta, coluna, fileira)
            self._avisar_carta_jogada(j, coluna, c)
            return c
        if tipo == "Terreno":
            return self.colocar_terreno(j, carta, coluna)
        if tipo == "Item":
            return self.equipar(j, carta, alvo)
        return self._resolver_feitico(j, carta, alvo)   # Feitiço

    def _avisar_carta_jogada(self, j, coluna, criatura=None):
        for c in self.todas_criaturas():
            if c is criatura:
                continue
            ctx = {"coluna": coluna, "jogador": j, "criatura": criatura}
            if criatura is not None:
                self.disparar("ao_carta_jogada", c, dict(ctx, carta=criatura.carta))
            self.disparar("ao_carta_jogada_adjacente", c, ctx)
        self.verificar_mortes()

    def colocar_terreno(self, j, carta, coluna):
        antigo = j.terrenos[coluna]
        if antigo:
            self.enviar_cemiterio(j, antigo.carta)
        t = Terreno(carta, j, coluna)
        j.terrenos[coluna] = t
        self.cena("terreno", j=self.jogadores.index(j), col=coluna, id=carta["id"], tema=carta.get("tema"))
        self.disparar("ao_entrar_terreno", t)
        self._avisar_carta_jogada(j, coluna)
        return t

    def equipar(self, j, carta, criatura):
        if criatura.item is not None:
            raise ValueError("A criatura já tem um item.")
        criatura.item = carta
        self.cena("equipar", id=carta["id"], **self._lugar(criatura))
        for c in j.criaturas():
            self.disparar("ao_aliado_equipa", c, {"portador": criatura})
        self.verificar_mortes()
        return criatura

    def _resolver_feitico(self, j, carta, alvo):
        f = Feitico(carta, j)
        fx = fx_da_carta(carta)
        self.cena("feitico", j=self.jogadores.index(j), id=carta["id"], nome=carta["nome"], fx=fx)
        self.fx_atual = fx
        try:
            res = self.disparar("ao_usar", f, {"alvo": alvo, "jogador": j})
        finally:
            self.fx_atual = None
        if not any(r and r.get("fica_em_campo") for r in res):
            self.enviar_cemiterio(j, carta)
        for c in j.criaturas():
            self.disparar("ao_usar_feitico", c, {"feitico": carta})
        for c in self.oponente(j).criaturas():
            self.disparar("ao_inimigo_usa_feitico", c, {"feitico": carta})
        self.verificar_mortes()

    # ------------------------------------------------------------ dano e vida
    def causar_dano(self, alvo, qtd, origem=None, tipo="habilidade"):
        """tipo: 'ataque', 'feitico', 'terreno' ou 'habilidade'.
        Retorna o dano aplicado."""
        if alvo.inativa or alvo.morta or alvo.fora_de_campo or qtd <= 0:
            return 0
        ignora = tipo == "ataque" and origem is not None and self.ha(origem, "poder_ignora_resistencias")
        if not ignora:
            if tipo == "feitico" and (self.ha(alvo, "imune_feiticos") or self.ha(alvo, "imune_terrenos_e_feiticos")
                                      or alvo.protecao_feiticos):
                return 0
            if tipo == "terreno" and (self.ha(alvo, "imune_terreno_dano") or self.ha(alvo, "imune_terrenos_e_feiticos")):
                return 0
            for efeito, quando in (("reduzir_dano_feitico", "feitico"), ("reduzir_dano_ataque", "ataque")):
                p = self.tem(alvo, efeito)
                if p is not None and tipo == quando:
                    qtd -= p.get("valor", 1)
            p = self.tem(alvo, "reduzir_primeiro_dano")
            if p is not None and not alvo.dano_no_turno and qtd > 0:
                qtd -= p.get("valor", 1)
                alvo.dano_no_turno = True      # a proteção do turno foi usada
            qtd = max(0, qtd)
            if qtd == 0:
                return 0
        if alvo.status.get("fragil"):
            qtd += 1                                   # Fragilidade: +1 de dano de qualquer fonte
        anel = self.tem(alvo, "sobreviver_com_1")
        if (anel is not None and not alvo.anel_usado and qtd >= alvo.vida
                and (not anel.get("so_com_vida_cheia") or alvo.dano == 0)):
            alvo.anel_usado = True
            qtd = alvo.vida - anel.get("vida_restante", 1)
            self.log(f"{alvo.nome} sobreviveu com {anel.get('vida_restante', 1)} de vida (item).")
        alvo.dano += qtd
        alvo.dano_no_turno = True
        alvo.ultimo_atacante = origem
        self.evento("dano", alvo, qtd)
        if origem is not None and tipo == "ataque" and qtd > 0:
            self.disparar("ao_causar_dano", origem, {"alvo": alvo, "dano": qtd})
        if alvo.vida <= 0 and not self.adiar_mortes:
            self.matar(alvo, origem)
        return qtd

    def curar(self, c, qtd):
        if c.inativa or c.morta or c.fora_de_campo:
            return
        antes = c.dano
        c.dano = max(0, c.dano - qtd)
        if antes != c.dano:
            self.evento("cura", c, antes - c.dano)

    def curar_jogador(self, j, qtd):
        antes = j.vida
        j.vida = min(j.vida_max, j.vida + qtd)
        if j.vida != antes:
            self.evento("cura", j, j.vida - antes)

    def dano_jogador(self, j, qtd, origem=None):
        if qtd <= 0 or self.vencedor:
            return 0
        j.vida -= qtd
        j.dano_recebido += qtd
        self.evento("dano", j, qtd)
        opp = self.oponente(j)
        if origem is not None and getattr(origem, "tipo_fonte", "") == "criatura":
            self.disparar("ao_causar_dano_jogador", origem, {"dano": qtd, "alvo": j})
        novos = min(MAX_PREMIOS, j.dano_recebido // 8) - opp.premios_liberados
        for _ in range(max(0, novos)):
            opp.premios_liberados += 1
            self.cena("premio", j=self.jogadores.index(opp))
            if opp.premio:
                carta = self.escolher(opp, opp.premio, "Escolha um prêmio")
                opp.premio.remove(carta)
                opp.mao.append(carta)
                self.log(f"{opp.nome} recebeu um prêmio.")
        if j.vida <= 0:
            self.vencedor = opp
        return qtd

    def matar(self, c, origem=None):
        if c.morta or c.fora_de_campo or c.inativa:
            return False
        res = self.disparar("ao_morrer", c, {"origem": origem}, so={"persistencia"})
        if any(r and r.get("impedir_morte") for r in res):
            return False
        c.morta = True
        self.cena("morte", id=c.carta["id"], **self._lugar(c))
        self.remover_do_campo(c)
        self.enviar_cemiterio(c.dono, c.carta)
        if c.item:
            self.enviar_cemiterio(c.dono, c.item)
        self.log(f"{c.nome} foi para o cemitério.")
        self.disparar("ao_morrer", c, {"origem": origem}, exceto={"persistencia"})
        if origem is not None and getattr(origem, "tipo_fonte", "") == "criatura" \
                and not origem.morta and not origem.fora_de_campo:
            self.disparar("ao_eliminar", origem, {"alvo": c})
        return True

    def devolver_para_mao(self, c):
        """Tira a criatura do campo e a devolve à mão do dono (item vai ao cemitério)."""
        self.remover_do_campo(c)
        if not c.carta.get("token"):
            c.dono.mao.append(c.carta)
        if c.item:
            self.enviar_cemiterio(c.dono, c.item)

    def verificar_mortes(self):
        if self.adiar_mortes:
            return
        for _ in range(20):
            mortas = [c for c in self.todas_criaturas() if c.vida <= 0]
            if not mortas:
                return
            for c in mortas:
                self.matar(c, c.ultimo_atacante)

    # ------------------------------------------------------------ combate
    def pode_atacar(self, c):
        """Toda criatura em campo ataca, inclusive as postas na própria rodada
        (exceto inativas ou impedidas de atacar)."""
        return not (c.inativa or c.morta or c.fora_de_campo or c.status.get("sem_atacar"))

    def alvo_padrao(self, atacante):
        """Frente primeiro, depois retaguarda; coluna vazia = herói inimigo.
        Criaturas com Evasão só são bloqueadas por criaturas com Evasão."""
        inimigo = self.oponente(atacante.dono)
        col = atacante.posicao[0]
        cands = [c for f in FILEIRAS if (c := inimigo.campo[col][f]) and not c.inativa]
        if self.ha(atacante, "evasao"):
            cands = [c for c in cands if self.ha(c, "evasao")]
        return cands[0] if cands else inimigo

    def atacar(self, atacante, alvo=None):
        """Um ataque: dispara 'ao_atacar', causa dano e aplica os efeitos extras."""
        if atacante.inativa or atacante.morta or atacante.fora_de_campo:
            return
        if alvo is None and self.ha(atacante, "ataque_livre"):    # Frenesi: escolhe quem atacar
            cands = [c for c in self.oponente(atacante.dono).criaturas() if not c.inativa and not c.status.get("camuflada")]
            if cands:
                alvo = self.escolher(atacante.dono, cands, "Escolha o alvo do ataque", fonte=atacante)
        alvo = alvo or self.alvo_padrao(atacante)
        ctx = {"alvo": alvo, "dano_extra": 0, "devolver": False, "adjacente": False}
        self.disparar("ao_atacar", atacante, ctx)
        dano = atacante.ataque + ctx["dano_extra"]
        if hasattr(alvo, "campo"):
            destino = {"heroi": True, "aj": self.jogadores.index(alvo)}
        else:
            destino = {"heroi": False, "aj": self.jogadores.index(alvo.dono),
                       "acol": alvo.posicao[0], "afil": alvo.posicao[1]}
        self.cena("golpe", id=atacante.carta["id"], tribos=list(atacante.tribos), dano=dano,
                  **self._lugar(atacante), **destino)
        if hasattr(alvo, "campo"):          # é um Jogador
            self.dano_jogador(alvo, dano, atacante)
        else:
            self.causar_dano(alvo, dano, atacante, "ataque")
        if ctx["adjacente"]:
            col = atacante.posicao[0]
            vizinhas = [c for c in self.oponente(atacante.dono).criaturas() if abs(c.posicao[0] - col) == 1]
            if vizinhas:
                self.causar_dano(self.escolher(atacante.dono, vizinhas, "Alvo adjacente"), dano, atacante, "ataque")
        if ctx["devolver"] and not hasattr(alvo, "campo") and alvo.vida > 0 \
                and not (alvo.morta or alvo.inativa or alvo.fora_de_campo):
            self.devolver_para_mao(alvo)
        self.verificar_mortes()

    def ativar(self, c, nome=None):
        """Usa uma habilidade ativável (1 vez por rodada, salvo regra contrária)."""
        for h in self.habilidades_de(c):
            if h["gatilho"] != "ativavel" or (nome and h["nome"] != nome):
                continue
            if c.ativada_na_rodada.get(h["nome"]) == self.rodada:
                return False
            c.ativada_na_rodada[h["nome"]] = self.rodada
            habilidades.REGISTRO[h["efeito"]](self, c, h.get("params", {}), {})
            self.verificar_mortes()
            return True
        return False

    def resolver_coluna(self, col):
        """Todos os ataques da coluna acontecem juntos: os alvos são definidos
        antes e as mortes só valem depois de todo o dano (quem morre ainda ataca)."""
        atacantes = [c for j in self.jogadores for f in FILEIRAS
                     if (c := j.campo[col][f]) and self.pode_atacar(c)]
        self.cena("coluna", col=col, ataques=len(atacantes))
        self.adiar_mortes = True
        try:
            for a in atacantes:
                if self.vencedor:
                    break
                self.atacar(a)
        finally:
            self.adiar_mortes = False
        self.verificar_mortes()

    def resolver_batalha(self):
        """Fase de batalhas: colunas da esquerda para a direita, depois fim de batalha."""
        self.em_batalha = True
        for c in list(self.todas_criaturas()):
            if not c.morta and not c.fora_de_campo:
                self.disparar("ao_inicio_batalha", c)
        self.verificar_mortes()
        for col in range(COLUNAS):
            if self.vencedor:
                break
            self.resolver_coluna(col)
        if not self.vencedor:
            self.fim_de_batalha()
        self.em_batalha = False

    # ------------------------------------------------------------ rodada
    def iniciar_rodada(self):
        self.rodada += 1
        for c in self.todas_criaturas(incluir_inativas=True):
            if c.reviver_na_rodada == self.rodada:
                c.ataque_base, c.vida_base = c.revive_com
                c.bonus_ataque = c.bonus_vida = c.dano = 0
                c.inativa = False
                c.reviver_na_rodada = None
                self.log(f"{c.nome} voltou com {c.ataque}/{c.vida}.")
        for c in self.todas_criaturas():
            self.disparar("ao_inicio_rodada", c)
        self.verificar_mortes()

    def fim_de_batalha(self):
        """Habilidades de fim de batalha / sobreviver e limpeza de efeitos temporários."""
        for j in self.jogadores:
            for c in j.criaturas():
                self.disparar("ao_fim_batalha", c)
            for t in [t for t in j.terrenos if t]:
                self.disparar("ao_fim_batalha", t)
        self.verificar_mortes()
        for c in self.todas_criaturas():
            if c.substituto is not None:
                self._reverter_substituto(c)
            elif not c.morta and not c.fora_de_campo:
                self.disparar("ao_sobreviver", c)
        self.verificar_mortes()
        for c in self.todas_criaturas(incluir_inativas=True):
            c.dano_no_turno = False
            c.status = {k: v - 1 for k, v in c.status.items() if v > 1}

    def fim_de_rodada(self):
        """Depois das batalhas: cartas do cemitério que já esperaram voltam ao deck,
        cada jogador ganha surgimento (= nº da batalha) e compra 1 carta."""
        for j in self.jogadores:
            voltam = [x for x in j.cemiterio if self.rodada - x[1] >= RODADAS_NO_CEMITERIO]
            if voltam:
                j.cemiterio = [x for x in j.cemiterio if self.rodada - x[1] < RODADAS_NO_CEMITERIO]
                j.deck.extend(c for c, _ in voltam)
                self.embaralhar(j)
        for j in self.jogadores:
            j.surgimento += self.rodada
            self.comprar(j, 1)

    def _reverter_substituto(self, sub):
        """Extração: se o substituto sobreviveu, a criatura original volta ao campo."""
        j, (col, fil), original = sub.dono, sub.posicao, sub.substituto
        self.remover_do_campo(sub)
        self.enviar_cemiterio(j, sub.carta)
        if original in j.mao:
            j.mao.remove(original)
            self.invocar(j, original, col, fil)

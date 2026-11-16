"""IA do computador.

Ela joga pelas mesmas regras e pelas mesmas ações que uma pessoa (`Jogo.jogar`,
`Jogo.passar_fase`...), então não precisa de nenhum atalho no motor. Tudo é
heurística simples: cada jogada possível ganha uma nota e a melhor é executada.

Cartas novas funcionam sem ajuste: um efeito que a IA não conhece recebe uma nota
baixa e padrão. Para ensinar algo específico, mexa nas tabelas logo abaixo.
"""

import random

from .estado import FILEIRAS, COLUNAS

# --- tabelas editáveis -----------------------------------------------------
# efeitos que prejudicam o alvo (a IA escolhe inimigos) e que ajudam (escolhe aliados)
HOSTIL = {"fragilizar", "dano", "dano_e_buscar_se_eliminar", "impedir_ataque", "congelar", "silenciar",
          "devolver_para_mao", "assombracao", "mover_e_atacar", "ataque_adjacente", "veneno",
          "atacar_ao_entrar", "dano_igual_a_vida_se_cara"}
AMIGO = {"curar", "curar_total", "buff", "buff_tribo_fileira", "aumentar_status", "aumentar_ataque_base",
         "aumentar_vida", "ataque_bonus", "dar_protecao_feiticos", "recuar_criatura",
         "mudar_de_fileira", "mover_para_carta", "mover_adjacente"}
# feitiços que só valem a pena com algum inimigo / aliado em campo
FEITICO_CONTRA_INIMIGO = {"dano", "assombracao", "congelar", "impedir_ataque", "silenciar"}
FEITICO_EM_ALIADO = {"buff", "ataque_bonus", "aumentar_status", "aumentar_ataque_base", "aumentar_vida"}
CUSTO_ALTO_MULLIGAN = 6


def _efeitos(fonte):
    return {h["efeito"] for h in getattr(fonte, "habilidades", None) or []}


def _efeitos_carta(carta):
    return {h["efeito"] for h in carta.get("habilidades", [])}


def _params(carta, efeito):
    for h in carta.get("habilidades", []):
        if h["efeito"] == efeito:
            return h.get("params", {})
    return {}


class IA:
    def __init__(self, jogo, indice, rng=None):
        self.jogo = jogo
        self.i = indice
        self.rng = rng or random.Random()
        self._fase_ruins = (None, set())     # (rodada, fase) -> cartas que deram erro

    # ------------------------------------------------------------ atalhos
    @property
    def p(self):
        return self.jogo.p

    @property
    def eu(self):
        return self.p.jogadores[self.i]

    @property
    def adv(self):
        return self.p.jogadores[1 - self.i]

    # ------------------------------------------------------------ perguntas do motor
    def confirmar(self, jogador, msg=""):
        return True

    def escolher(self, jogador, opcoes, msg="", fonte=None):
        """Responde a uma escolha no meio de um efeito (alvo, carta, posição...)."""
        if not opcoes:
            return None
        if len(opcoes) == 1:
            return opcoes[0]
        amostra = opcoes[0]
        if hasattr(amostra, "posicao") and hasattr(amostra, "dono"):
            return self._escolher_criatura(jogador, opcoes, msg, fonte)
        if isinstance(amostra, tuple):
            return max(opcoes, key=lambda pos: self._nota_posicao_livre(jogador, pos))
        if isinstance(amostra, dict):                      # carta (deck, mão, prêmio, cemitério)
            return max(opcoes, key=lambda c: (c.get("custo", 0), (c.get("ataque") or 0) + (c.get("vida") or 0)))
        return opcoes[0]

    def _intencao(self, msg, fonte):
        m = (msg or "").lower()
        if any(k in m for k in ("fortalecer", "recuar", "quem ataca", "muda de fileira", "equipar")):
            return "amigo"
        if any(k in m for k in ("congelar", "adjacente")):
            return "hostil"
        efs = _efeitos(fonte) if fonte is not None else set()
        if efs & HOSTIL:
            return "hostil"
        if efs & AMIGO:
            return "amigo"
        return "hostil"              # padrão: o motor lista as inimigas primeiro

    def _escolher_criatura(self, jogador, opcoes, msg, fonte):
        intencao = self._intencao(msg, fonte)
        meus = [c for c in opcoes if c.dono is jogador]
        deles = [c for c in opcoes if c.dono is not jogador]
        pool = (deles or opcoes) if intencao == "hostil" else (meus or opcoes)
        if intencao == "hostil":
            return max(pool, key=lambda c: c.ataque * 2 + c.carta.get("custo", 0) * 0.5 - c.vida * 0.1)
        efs = _efeitos(fonte) if fonte is not None else set()
        if "recuar" in (msg or "").lower() or efs & {"curar", "curar_total"}:
            return max(pool, key=lambda c: (c.dano, c.ataque))           # a mais ferida
        return max(pool, key=lambda c: (c.ataque, c.vida))

    def _nota_posicao_livre(self, jogador, pos):
        col, fil = pos
        adv = self.p.oponente(jogador)
        vazio_inimigo = not any(adv.campo[col][f] for f in FILEIRAS)
        return (3 if vazio_inimigo else 0) + (1 if fil == "frente" else 0)

    # ------------------------------------------------------------ moeda e mulligan
    def indices_mulligan(self):
        mao = self.eu.mao
        trocar = [i for i, c in enumerate(mao) if c.get("custo", 0) >= CUSTO_ALTO_MULLIGAN]
        if not any(c.get("custo", 0) <= 2 for c in mao):         # mão sem jogadas baratas
            caras = sorted((i for i in range(len(mao)) if i not in trocar),
                           key=lambda i: -mao[i].get("custo", 0))
            trocar += caras[:2]
        return trocar

    # ------------------------------------------------------------ jogadas
    def agir(self):
        """Faz UMA ação da vez da IA. Quem chama repete até a vez mudar."""
        jogo = self.jogo
        if jogo.etapa == "moeda":
            return jogo.escolher_lado(self.rng.choice(("cara", "coroa")))
        if jogo.etapa == "mulligan":
            return jogo.mulligan(self.indices_mulligan())
        if jogo.etapa != "rodada":
            return
        chave = (self.p.rodada, jogo.fase)
        if self._fase_ruins[0] != chave:
            self._fase_ruins = (chave, set())
        ruins = self._fase_ruins[1]
        if jogo.fase in (2, 3):
            for nota, indice, coluna, fileira in self._jogadas():
                carta = self.eu.mao[indice]
                if id(carta) in ruins:
                    continue
                try:
                    return jogo.jogar(indice, coluna, fileira)
                except ValueError:
                    ruins.add(id(carta))
            if self._ativar_habilidades(ruins):
                return
        jogo.passar_fase()

    def _ativar_habilidades(self, ruins):
        if not self.adv.criaturas():
            return False
        for c in self.eu.criaturas():
            chave = ("ativar", id(c))
            if chave in self._fase_ruins[1] or not self.jogo._criatura(c)["ativavel"]:
                continue
            self._fase_ruins[1].add(chave)
            try:
                self.jogo.ativar(*c.posicao)
                return True
            except ValueError:
                continue
        return False

    def _jogadas(self):
        """Todas as jogadas possíveis agora, da melhor para a pior: (nota, indice, coluna, fileira)."""
        j, jogo, saida = self.eu, self.jogo, []
        for i, carta in enumerate(j.mao):
            if not jogo.pode_jogar(j, carta):
                continue
            tipo = carta["tipo"]
            if tipo == "Criatura":
                nota, col, fil = self._nota_criatura(carta)
            elif tipo == "Feitiço":
                nota, col, fil = self._nota_feitico(carta), None, None
            elif tipo == "Item":
                nota, col, fil = self._nota_item(carta), None, None
            elif tipo == "Terreno":
                nota, col = self._nota_terreno(carta)
                fil = None
            else:
                nota, col, fil = 1.0, None, None
            if nota > 0:
                saida.append((nota, i, col, fil))
        saida.sort(key=lambda t: (-t[0], -j.mao[t[1]].get("custo", 0)))
        return saida

    # --- criaturas
    def _nota_posicao(self, carta, col, fil):
        j, adv = self.eu, self.adv
        atk, vida = carta.get("ataque") or 0, carta.get("vida") or 0
        inimigas = [c for f in FILEIRAS if (c := adv.campo[col][f]) and not c.inativa]
        n = 0.0
        if not inimigas:
            n += atk * 2                              # coluna aberta: ataque direto ao herói
        elif fil == "frente":
            f = inimigas[0]
            if f.ataque >= vida and atk < f.vida:
                n -= 2                                # morre sem derrubar o inimigo
            if atk >= f.vida:
                n += 2
        if fil == "frente":
            n += vida * 0.3
        else:
            n += 2 if j.campo[col]["frente"] else -3
            if atk == 0:
                n -= 2
        return n

    def _nota_criatura(self, carta):
        livres = self.p.posicoes_livres(self.eu)
        melhor = max(livres, key=lambda pos: self._nota_posicao(carta, *pos))
        base = ((carta.get("ataque") or 0) * 1.5 + (carta.get("vida") or 0)
                + self.p.custo_de(self.eu, carta) * 0.7 + (2 if carta.get("habilidades") else 0))
        return base + self._nota_posicao(carta, *melhor) + 1, melhor[0], melhor[1]

    # --- feitiços
    def _valor_campo(self, jogador, custo_min=0):
        return sum(c.ataque + c.vida + c.carta.get("custo", 0)
                   for c in jogador.criaturas() if c.carta.get("custo", 0) >= custo_min)

    def _nota_feitico(self, carta):
        efs = _efeitos_carta(carta)
        eu, adv = self.eu, self.adv
        custo = carta.get("custo", 0)
        if "destruir_todas" in efs:
            minimo = _params(carta, "destruir_todas").get("custo_min", 0)
            saldo = self._valor_campo(adv, minimo) - self._valor_campo(eu, minimo)
            return 5 + saldo * 0.3 if saldo >= 6 else 0
        if "comprar_cartas" in efs:
            return 5 if len(eu.mao) < 9 else 0
        if efs & FEITICO_CONTRA_INIMIGO:
            alvos = adv.criaturas()
            return 3 + custo * 0.3 + max(c.ataque for c in alvos) * 0.5 if alvos else 0
        if "curar" in efs:
            feridas = [c for c in eu.criaturas() if c.dano > 0]
            return 2.5 + max(c.dano for c in feridas) * 0.5 if feridas else 0
        if efs & FEITICO_EM_ALIADO:
            aliadas = eu.criaturas()
            return 3 + custo * 0.3 + max(c.ataque for c in aliadas) * 0.3 if aliadas else 0
        if "recuar_criatura" in efs:
            return 0
        return 1.0                                    # efeito desconhecido: nota baixa e padrão

    # --- itens
    def _nota_item(self, carta):
        livres = [c for c in self.eu.criaturas() if c.item is None]
        if not livres:
            return 0
        return 2 + carta.get("custo", 0) * 0.5 + max(c.ataque for c in livres) * 0.3

    # --- terrenos
    def _nota_terreno(self, carta):
        efs = _efeitos_carta(carta)
        eu, adv = self.eu, self.adv
        melhor = (0.0, None)
        for col in range(COLUNAS):
            meus = [c for f in FILEIRAS if (c := eu.campo[col][f])]
            deles = [c for f in FILEIRAS if (c := adv.campo[col][f])]
            if "dano_na_coluna" in efs:
                valor = _params(carta, "dano_na_coluna").get("valor", 1)
                nota = (len(deles) - len(meus)) * valor
            elif "dano_por_custo" in efs:
                nota = 2.5 - len(meus) * 0.3 - len(deles) * 0.5 + (1 if not deles else 0)
            elif "curar_na_coluna" in efs:
                nota = (len(meus) - len(deles)) * 1.5 + sum(c.dano for c in meus) * 0.3
            elif "limpar_terrenos_e_curar" in efs:
                nota = (3 if adv.terrenos[col] else 0) + len(meus) * 0.5
            else:
                nota = 1.0 - len(meus) * 0.1
            if eu.terrenos[col]:
                nota -= 3                             # trocaria um terreno meu
            if nota > melhor[0]:
                melhor = (nota, col)
        if melhor[1] is None and not ("dano_na_coluna" in efs or "curar_na_coluna" in efs):
            livres = [c for c in range(COLUNAS) if not eu.terrenos[c]]
            if livres:
                melhor = (0.5, livres[0])
        return melhor


def passo(jogo, ias):
    """Se for a vez de uma IA, faz uma ação e devolve True. `ias` = {indice: IA}."""
    if jogo.etapa == "fim":
        return False
    ia = ias.get(jogo.jogador_da_fase)
    if ia is None:
        return False
    ia.agir()
    return True


def rodar(jogo, ias, limite=5000):
    """Executa as IAs até a vez de uma pessoa (ou o fim da partida)."""
    for _ in range(limite):
        if not passo(jogo, ias):
            return
    raise RuntimeError("A IA não terminou a vez (possível laço).")

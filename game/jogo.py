"""Fluxo de uma partida: moeda, mulligan e as 5 fases de cada rodada.

  etapa "moeda"    -> o jogador 1 escolhe cara ou coroa; quem ganha começa
  etapa "mulligan" -> cada jogador troca (uma vez) cartas da mão inicial
  etapa "rodada"   -> fases: Campo (1º), Campo (2º), Preparação (1º),
                      Preparação (2º) e Batalhas (automática)
  etapa "fim"      -> alguém chegou a 0 de vida

`Jogo` cuida só das regras de turno. Dano, habilidades e combate ficam no motor
(game/estado.py). `visao()` monta o que o navegador precisa para desenhar a arena.
"""

from . import estado

FASES = ("Campo", "Campo", "Preparação", "Preparação", "Batalhas")
LOG_MAX = 40


def resumo(carta):
    """Dados mínimos de uma carta para a interface."""
    return {"id": carta["id"], "nome": carta["nome"], "tipo": carta["tipo"],
            "subtipo": carta.get("subtipo"), "custo": carta.get("custo", 0),
            "ataque": carta.get("ataque"), "vida": carta.get("vida"),
            "tribos": estado.tribos_de(carta), "texto": carta.get("texto", ""),
            "imagem": carta.get("imagem"), "tema": carta.get("tema"),
            "raridade": carta.get("raridade")}


class Jogo:
    def __init__(self, deck1, premio1, deck2, premio2, nomes=("Jogador 1", "Jogador 2"),
                 seed=None, escolhedor=None, confirmador=None):
        self.p = estado.Partida(nomes[0], nomes[1], deck1, deck2, premio1, premio2,
                                seed=seed, escolhedor=escolhedor, confirmador=confirmador)
        for j in self.p.jogadores:
            self.p.embaralhar(j)
            self.p.comprar(j, 5)
        self.etapa = "moeda"
        self.vez = 0                 # quem decide na moeda / no mulligan
        self.primeiro = None
        self.fase = 0                # índice em FASES
        self.moeda = None            # {"escolha", "resultado", "vencedor"}
        self.trocou = [False, False]

    # ------------------------------------------------------------ consultas
    @property
    def jogador_da_fase(self):
        if self.etapa == "rodada":
            return self.primeiro if self.fase in (0, 2) else 1 - self.primeiro
        return self.vez

    def _atual(self):
        return self.p.jogadores[self.jogador_da_fase]

    def _exigir(self, etapa):
        if self.etapa != etapa:
            raise ValueError("Essa ação não é possível agora.")

    def _checar_fim(self):
        if self.p.vencedor and self.etapa != "fim":
            self.etapa = "fim"
            self.p.log(f"{self.p.vencedor.nome} venceu a partida.")

    # ------------------------------------------------------------ moeda e mulligan
    def escolher_lado(self, lado):
        self._exigir("moeda")
        if lado not in ("cara", "coroa"):
            raise ValueError("Escolha cara ou coroa.")
        resultado = "cara" if self.p.rng.random() < 0.5 else "coroa"
        vencedor = 0 if lado == resultado else 1
        self.moeda = {"escolha": lado, "resultado": resultado, "vencedor": vencedor}
        self.primeiro = vencedor
        self.etapa = "mulligan"
        self.vez = vencedor
        self.p.log(f"Deu {resultado}. {self.p.jogadores[vencedor].nome} começa.")

    def mulligan(self, indices):
        """Troca as cartas da mão nas posições `indices` (cada carta uma única vez)."""
        self._exigir("mulligan")
        j = self.p.jogadores[self.vez]
        indices = sorted(set(int(i) for i in indices))
        if any(i < 0 or i >= len(j.mao) for i in indices):
            raise ValueError("Carta inválida.")
        trocadas = [j.mao[i] for i in indices]
        j.mao = [c for i, c in enumerate(j.mao) if i not in indices]
        j.deck.extend(trocadas)
        self.p.embaralhar(j)
        self.p.comprar(j, len(trocadas))
        self.p.log(f"{j.nome} trocou {len(trocadas)} carta(s).")
        self.trocou[self.vez] = True
        if all(self.trocou):
            self.etapa = "rodada"
            self.fase = 0
            self.p.iniciar_rodada()
        else:
            self.vez = 1 - self.vez

    # ------------------------------------------------------------ ações da rodada
    def pode_jogar(self, j, carta):
        """A carta pode ser jogada agora por `j`? (usado na interface)"""
        if self.etapa != "rodada" or self.fase > 3 or j is not self._atual():
            return False
        if self.p.custo_de(j, carta) > j.surgimento:
            return False
        tipo = carta["tipo"]
        if tipo == "Feitiço":
            return self.fase in (2, 3) and self._tem_alvo(j, carta)
        if tipo == "Criatura":
            return bool(self.p.posicoes_livres(j))
        if tipo == "Item":
            return any(c.item is None for c in j.criaturas())
        return True

    NEGATIVOS = {"dano", "congelar", "assombracao", "impedir_ataque", "mudar_de_fileira", "dano_e_buscar_se_eliminar"}

    def _tem_alvo(self, j, carta):
        """Feitiço que só age em criaturas precisa de ao menos uma criatura do lado certo."""
        opp = self.p.oponente(j)
        for h in carta.get("habilidades", []):
            e, params = h.get("efeito"), h.get("params", {})
            if e in self.NEGATIVOS and not any(not c.status.get("camuflada") for c in opp.criaturas()):
                if not (e == "dano" and params.get("alvo") == "qualquer" and j.criaturas()):
                    return False
            if e == "curar" and params.get("alvo", "carta") == "carta" and not j.criaturas():
                return False
        return True

    def jogar(self, indice, coluna=None, fileira=None):
        self._exigir("rodada")
        j = self._atual()
        if not 0 <= indice < len(j.mao):
            raise ValueError("Carta inválida.")
        carta = j.mao[indice]
        if carta["tipo"] == "Feitiço" and self.fase not in (2, 3):
            raise ValueError("Feitiços só podem ser usados na fase de Preparação.")
        self.p.log(f"{j.nome} jogou {carta['nome']}.")
        self.p.jogar_carta(j, carta, coluna, fileira)
        self.p.verificar_mortes()
        self._checar_fim()

    def ativar(self, coluna, fileira):
        self._exigir("rodada")
        j = self._atual()
        c = j.campo[coluna][fileira]
        if c is None:
            raise ValueError("Não há criatura aí.")
        if not self.p.ativar(c):
            raise ValueError("Essa habilidade não pode ser usada agora.")
        self.p.log(f"{j.nome} ativou a habilidade de {c.nome}.")
        self._checar_fim()

    def passar_fase(self):
        self._exigir("rodada")
        self.p.log(f"{self._atual().nome} passou a fase de {FASES[self.fase]}.")
        self.fase += 1
        if self.fase < 4:
            return
        self.p.log(f"Batalha da rodada {self.p.rodada}.")
        self.p.resolver_batalha()
        self._checar_fim()
        if self.etapa == "fim":
            return
        self.p.fim_de_rodada()
        self.p.iniciar_rodada()
        self.fase = 0
        self._checar_fim()

    # ------------------------------------------------------------ visão para a interface
    def _criatura(self, c):
        ativavel = any(h["gatilho"] == "ativavel" for h in c.habilidades)
        usada = any(c.ativada_na_rodada.get(h["nome"]) == self.p.rodada
                    for h in c.habilidades if h["gatilho"] == "ativavel")
        d = resumo(c.carta)
        d.update(ataque=c.ataque, vida=c.vida, vida_max=c.vida_max,
                 item=resumo(c.item) if c.item else None,
                 status=sorted(k for k, v in c.status.items() if v),
                 inativa=c.inativa, ativavel=ativavel and not usada and not c.inativa)
        return d

    def visao(self, ver=0):
        p = self.p
        jogadores = []
        for idx, j in enumerate(p.jogadores):
            campo = [{f: (self._criatura(c) if (c := col[f]) else None) for f in estado.FILEIRAS}
                     for col in j.campo]
            terrenos = [resumo(t.carta) if t else None for t in j.terrenos]
            cemiterio = [dict(resumo(c), volta_em=max(0, estado.RODADAS_NO_CEMITERIO - (p.rodada - r)))
                         for c, r in j.cemiterio]
            jogadores.append({
                "nome": j.nome, "vida": j.vida, "vida_max": j.vida_max, "surgimento": j.surgimento,
                "deck": len(j.deck), "mao_n": len(j.mao), "premio_n": len(j.premio),
                "premios_liberados": j.premios_liberados,
                "campo": campo, "terrenos": terrenos, "cemiterio": cemiterio,
                "mao": [dict(resumo(c), i=i, jogavel=self.pode_jogar(j, c), custo_atual=p.custo_de(j, c)) for i, c in enumerate(j.mao)]
                       if idx == ver else None,
                "premio": [resumo(c) for c in j.premio] if idx == ver else None,
            })
        return {
            "etapa": self.etapa, "rodada": p.rodada, "fase": self.fase,
            "fase_nome": FASES[self.fase] if self.etapa == "rodada" else None,
            "jogador_da_fase": self.jogador_da_fase, "primeiro": self.primeiro,
            "moeda": self.moeda, "trocou": self.trocou,
            "vencedor": p.jogadores.index(p.vencedor) if p.vencedor else None,
            "jogadores": jogadores, "log": p.historico[-LOG_MAX:], "eventos": list(p.eventos),
        }

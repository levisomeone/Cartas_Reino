"""Sessão de uma partida na web.

O motor pede escolhas ao jogador no meio de um efeito (alvo de um feitiço, carta
a buscar no deck...). Para isso cada ação roda numa thread própria: quando o
motor chama `escolher`, a thread espera e a pergunta vai para o navegador; a
resposta chega por outra requisição e a thread continua de onde parou.
"""

import random
import threading
import time
import traceback
import uuid

from . import estado
from . import ia as ia_mod
from .jogo import Jogo, resumo


def expandir_deck(deck, cartas_por_id):
    """{'principal': {id: qtd}, 'premio': {...}} -> (lista de cartas, lista de prêmios)."""
    def lista(grupo):
        return [cartas_por_id[cid] for cid, q in grupo.items() for _ in range(q) if cid in cartas_por_id]
    return lista(deck.get("principal", {})), lista(deck.get("premio", {}))


def deck_aleatorio(cartas, rng=None):
    """40 cartas + 4 de prêmio, no máximo 4 cópias de cada (para testar rápido)."""
    rng = rng or random.Random()
    criaturas = [c for c in cartas if c["tipo"] == "Criatura"]
    outras = [c for c in cartas if c["tipo"] != "Criatura"]

    def sorteio(pool, n, usadas):
        saida = []
        while len(saida) < n:
            livres = [c for c in pool if usadas.get(c["id"], 0) < 4]
            if not livres:
                break
            c = rng.choice(livres)
            usadas[c["id"]] = usadas.get(c["id"], 0) + 1
            saida.append(c)
        return saida

    usadas = {}
    principal = sorteio(criaturas, 28, usadas) + sorteio(outras, 12, usadas)
    premio = sorteio(criaturas + outras, 4, usadas)
    return principal, premio


class Sessao:
    def __init__(self, deck1, premio1, deck2, premio2, nomes, seed=None, ia=(False, False)):
        self.id = uuid.uuid4().hex[:10]
        self.cv = threading.Condition()
        self.pendente = None
        self.resposta = None
        self.thread = None
        self.erro = None
        self.seq = 0                      # conta ações, para a interface animar uma vez só
        self._n = 0
        self.ias = {}                     # {indice do jogador: IA}
        self.lan = None                   # partida em rede: {"token", "visto": [t0, t1]}
        self.erro_de = None               # em partida em rede, quem causou o erro
        self.jogo = Jogo(deck1, premio1, deck2, premio2, nomes, seed,
                         escolhedor=self._escolher, confirmador=self._confirmar)
        for i, ligada in enumerate(ia):
            if ligada:
                self.ias[i] = ia_mod.IA(self.jogo, i, random.Random(seed))

    # ------------------------------------------------------------ perguntas do motor
    def _descrever(self, o):
        p = self.jogo.p
        if isinstance(o, estado.Criatura):
            d = resumo(o.carta)
            d.update(t="criatura", j=p.jogadores.index(o.dono), col=o.posicao[0], fil=o.posicao[1])
            return d
        if isinstance(o, dict):
            return dict(resumo(o), t="carta")
        if isinstance(o, tuple) and len(o) == 2:
            return {"t": "posicao", "col": o[0], "fil": o[1]}
        return {"t": "texto", "nome": str(o)}

    def _perguntar(self, jogador, tipo, opcoes, msg):
        with self.cv:
            self._n += 1
            self.pendente = {"n": self._n, "tipo": tipo, "msg": msg,
                             "jogador": self.jogo.p.jogadores.index(jogador),
                             "opcoes": [self._descrever(o) for o in opcoes]}
            self.resposta = None
            self.cv.notify_all()
            while self.resposta is None:
                self.cv.wait()
            r, self.resposta, self.pendente = self.resposta, None, None
        return r

    def _escolher(self, jogador, opcoes, msg):
        if len(opcoes) == 1:
            return opcoes[0]
        ia = self.ias.get(self.jogo.p.jogadores.index(jogador))
        if ia is not None:
            return ia.escolher(jogador, opcoes, msg, self.jogo.p.fonte_escolha)
        return opcoes[self._perguntar(jogador, "escolher", opcoes, msg or "Escolha")["i"]]

    def _confirmar(self, jogador, msg):
        if self.jogo.p.jogadores.index(jogador) in self.ias:
            return True
        return self._perguntar(jogador, "confirmar", [], msg or "Usar a habilidade?")["sim"]

    # ------------------------------------------------------------ execução
    def _esperar(self, ignorar=None):
        with self.cv:
            while self.thread.is_alive() and (self.pendente is None or self.pendente["n"] == ignorar):
                self.cv.wait(0.05)

    def executar(self, fn, quem=None):
        with self.cv:
            if self.pendente is not None:
                raise ValueError("Responda à pergunta na tela primeiro.")
        self.erro = None
        self.erro_de = quem
        self.jogo.p.eventos = []
        self.seq += 1

        def corpo():
            try:
                fn()
                ia_mod.rodar(self.jogo, self.ias)      # se agora for a vez da IA, ela joga
            except ValueError as e:
                self.erro = str(e)
            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self.erro = f"Erro interno: {e}"
            finally:
                with self.cv:
                    self.cv.notify_all()

        self.thread = threading.Thread(target=corpo, daemon=True)
        self.thread.start()
        self._esperar()

    def responder(self, valor, quem=None):
        with self.cv:
            pend = self.pendente
            if pend is None:
                raise ValueError("Não há pergunta pendente.")
            if quem is not None and pend["jogador"] != quem:
                raise ValueError("Essa escolha é do outro jogador.")
            if pend["tipo"] == "confirmar":
                self.resposta = {"sim": bool(valor)}
            else:
                i = int(valor)
                if not 0 <= i < len(pend["opcoes"]):
                    raise ValueError("Opção inválida.")
                self.resposta = {"i": i}
            n = pend["n"]
            self.cv.notify_all()
        self.erro = None
        self._esperar(ignorar=n)

    def _encerrar_por(self, perdedor, motivo):
        """Termina a partida dando a vitória ao outro jogador (desistência ou queda de conexão)."""
        j = self.jogo
        if j.etapa == "fim":
            return
        with self.cv:
            j.p.vencedor = j.p.jogadores[1 - perdedor]
            j.p.log(f"{j.p.jogadores[perdedor].nome} {motivo}")
            j._checar_fim()
            self.seq += 1
            self.jogo.p.eventos = []
            self.cv.notify_all()

    def agir(self, acao, quem=None):
        """Executa um dicionário de ação vindo do navegador.

        `quem` (0 ou 1) só é informado em partida em rede: só vale a ação de quem tem a vez."""
        j, tipo = self.jogo, acao.get("tipo")
        if quem is not None:
            if tipo == "desistir":
                return self._encerrar_por(quem, "desistiu.")
            if tipo == "reivindicar":
                ausente = time.time() - self.lan["visto"][1 - quem]
                if ausente < 40:
                    raise ValueError("O oponente ainda está conectado.")
                return self._encerrar_por(1 - quem, "perdeu a conexão.")
            if tipo != "responder" and (self.pendente is not None or j.jogador_da_fase != quem):
                raise ValueError("Não é a sua vez.")
        if tipo == "responder":
            return self.responder(acao.get("valor"), quem)
        mapa = {
            "lado": lambda: j.escolher_lado(acao.get("lado")),
            "mulligan": lambda: j.mulligan(acao.get("indices", [])),
            "jogar": lambda: j.jogar(int(acao["indice"]), acao.get("coluna"), acao.get("fileira")),
            "ativar": lambda: j.ativar(int(acao["coluna"]), acao["fileira"]),
            "passar": j.passar_fase,
        }
        if tipo not in mapa:
            raise ValueError("Ação desconhecida.")
        self.executar(mapa[tipo], quem)

    def iniciar(self):
        """Se a IA for quem decide primeiro (ex.: IA contra IA), já deixa ela começar."""
        if self.ias and self.jogo.jogador_da_fase in self.ias:
            self.executar(lambda: None)

    def estado(self, ver=0):
        v = self.jogo.visao(ver)
        erro = self.erro if self.erro_de in (None, ver) else None     # em rede, o erro é só de quem errou
        v.update(id=self.id, seq=self.seq, erro=erro, pendente=self.pendente,
                 ia=[i in self.ias for i in (0, 1)])
        if self.lan:
            v["rede"] = {"eu": ver, "oponente_ausente": int(time.time() - self.lan["visto"][1 - ver])}
        return v

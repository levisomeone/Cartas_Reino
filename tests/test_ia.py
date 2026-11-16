import random
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from game import cartas, ia as ia_mod  # noqa: E402
from game.jogo import Jogo  # noqa: E402
from game.sessao import Sessao, deck_aleatorio  # noqa: E402

LISTA = cartas.carregar_cartas(RAIZ / "data" / "cards.json")


def partida(seed, ias=(0, 1), limite=60):
    rng = random.Random(seed)
    d1, p1 = deck_aleatorio(LISTA, rng)
    d2, p2 = deck_aleatorio(LISTA, rng)
    mapa = {}
    jogo = Jogo(d1, p1, d2, p2, ("A", "B"), seed,
                escolhedor=lambda j, o, m: _resp(jogo, mapa, j, o, m),
                confirmador=lambda j, m: True)
    for i in ias:
        mapa[i] = ia_mod.IA(jogo, i, random.Random(seed))
    return jogo, mapa


def _resp(jogo, mapa, jogador, opcoes, msg):
    i = jogo.p.jogadores.index(jogador)
    if i in mapa:
        return mapa[i].escolher(jogador, opcoes, msg, jogo.p.fonte_escolha)
    return opcoes[0]


class TestIA(unittest.TestCase):
    def test_ia_contra_ia_termina(self):
        fins = 0
        for seed in range(25):
            jogo, mapa = partida(seed)
            for _ in range(20000):
                if jogo.etapa == "fim" or jogo.p.rodada > 60:
                    break
                ia_mod.passo(jogo, mapa)
            self.assertLessEqual(jogo.p.rodada, 61, f"seed {seed} não terminou")
            fins += jogo.etapa == "fim"
        self.assertGreaterEqual(fins, 20)

    def test_ia_vence_jogador_passivo(self):
        vitorias = 0
        for seed in range(15):
            jogo, mapa = partida(seed, ias=(1,))
            for _ in range(20000):
                if jogo.etapa == "fim" or jogo.p.rodada > 60:
                    break
                if jogo.jogador_da_fase == 0:        # a "pessoa" só passa
                    if jogo.etapa == "moeda":
                        jogo.escolher_lado("cara")
                    elif jogo.etapa == "mulligan":
                        jogo.mulligan([])
                    else:
                        jogo.passar_fase()
                else:
                    ia_mod.passo(jogo, mapa)
            vitorias += jogo.p.vencedor is jogo.p.jogadores[1]
        self.assertGreaterEqual(vitorias, 12)

    def test_sessao_com_ia(self):
        rng = random.Random(3)
        d1, p1 = deck_aleatorio(LISTA, rng)
        d2, p2 = deck_aleatorio(LISTA, rng)
        s = Sessao(d1, p1, d2, p2, ("Eu", "Computador"), seed=3, ia=(False, True))
        s.agir({"tipo": "lado", "lado": "cara"})
        for _ in range(200):
            if s.pendente or s.jogo.etapa == "fim":
                break
            j = s.jogo
            if j.etapa == "mulligan":
                s.agir({"tipo": "mulligan", "indices": []})
            elif j.etapa == "rodada":
                s.agir({"tipo": "passar"})
        self.assertIsNone(s.erro)
        self.assertTrue(s.estado(0)["ia"][1])
        self.assertGreater(s.jogo.p.rodada, 1)


if __name__ == "__main__":
    unittest.main()

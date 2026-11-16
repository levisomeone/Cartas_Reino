import random
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from game import cartas, sessao  # noqa: E402

LISTA = cartas.carregar_cartas(RAIZ / "data" / "cards.json")
POR_ID = {c["id"]: c for c in LISTA}


def nova(seed=1):
    rng = random.Random(seed)
    d1, d2 = sessao.deck_aleatorio(LISTA, rng), sessao.deck_aleatorio(LISTA, rng)
    return sessao.Sessao(d1[0], d1[1], d2[0], d2[1], ("Ana", "Beto"), seed=seed)


def comecar(s):
    s.agir({"tipo": "lado", "lado": "cara"})
    s.agir({"tipo": "mulligan", "indices": []})
    s.agir({"tipo": "mulligan", "indices": []})


class TestFluxo(unittest.TestCase):
    def test_inicio_da_partida(self):
        s = nova()
        st = s.estado(0)
        self.assertEqual(st["etapa"], "moeda")
        self.assertEqual([j["mao_n"] for j in st["jogadores"]], [5, 5])
        self.assertEqual([j["deck"] for j in st["jogadores"]], [35, 35])
        self.assertEqual([j["surgimento"] for j in st["jogadores"]], [2, 2])
        self.assertIsNone(st["jogadores"][1]["mao"])           # mão do outro fica oculta

    def test_moeda_mulligan_e_ordem_das_fases(self):
        s = nova()
        s.agir({"tipo": "lado", "lado": "cara"})
        self.assertEqual(s.estado()["etapa"], "mulligan")
        primeiro = s.estado()["primeiro"]
        s.agir({"tipo": "mulligan", "indices": [0, 1]})        # troca 2 cartas, continua com 5
        self.assertEqual(s.jogo.p.jogadores[primeiro].mao.__len__(), 5)
        s.agir({"tipo": "mulligan", "indices": []})
        st = s.estado()
        self.assertEqual((st["etapa"], st["rodada"], st["fase_nome"]), ("rodada", 1, "Campo"))
        ordem = []
        for _ in range(4):
            ordem.append((s.estado()["fase_nome"], s.estado()["jogador_da_fase"]))
            s.agir({"tipo": "passar"})
        self.assertEqual(ordem, [("Campo", primeiro), ("Campo", 1 - primeiro),
                                 ("Preparação", primeiro), ("Preparação", 1 - primeiro)])
        st = s.estado()
        self.assertEqual((st["rodada"], st["fase_nome"]), (2, "Campo"))
        self.assertEqual([j["surgimento"] for j in st["jogadores"]], [3, 3])   # 2 + 1ª batalha
        self.assertEqual([j["mao_n"] for j in st["jogadores"]], [6, 6])        # comprou 1

    def test_regras_de_fase(self):
        s = nova()
        s.agir({"tipo": "passar"})                              # ainda é a moeda: recusado
        self.assertIn("agora", s.erro)
        comecar(s)
        j = s.jogo.p.jogadores[s.estado()["jogador_da_fase"]]
        j.mao = [POR_ID["hecatombe"]]; j.surgimento = 9
        s.agir({"tipo": "jogar", "indice": 0})                  # feitiço no Campo: recusado
        self.assertIn("Preparação", s.erro)
        self.assertFalse(s.estado(s.estado()["jogador_da_fase"])["jogadores"][s.estado()["jogador_da_fase"]]["mao"][0]["jogavel"])

    def test_criatura_ataca_na_primeira_batalha_e_custa_surgimento(self):
        s = nova()
        comecar(s)
        p = s.jogo.p
        a, b = p.jogadores[s.estado()["primeiro"]], p.jogadores[1 - s.estado()["primeiro"]]
        a.mao = [POR_ID["lobo_sangrento"]]
        s.agir({"tipo": "jogar", "indice": 0, "coluna": 2, "fileira": "frente"})   # custo 2, tem 2
        self.assertEqual(a.surgimento, 0)
        self.assertEqual(a.campo[2]["frente"].nome, "Lobo Sangrento")
        for _ in range(4):
            s.agir({"tipo": "passar"})
        self.assertEqual(b.vida, 38)                             # coluna vazia: dano no herói

    def test_pergunta_no_meio_do_efeito(self):
        s = nova()
        comecar(s)
        p = s.jogo.p
        a, b = p.jogadores[s.estado()["primeiro"]], p.jogadores[1 - s.estado()["primeiro"]]
        alvo1 = p.invocar(b, POR_ID["parede_centenaria"], 0, "frente")
        alvo2 = p.invocar(b, POR_ID["parede_centenaria"], 1, "frente")
        for _ in range(2):
            s.agir({"tipo": "passar"})                           # vai até a Preparação do 1º
        a.mao = [POR_ID["hecatombe"]]; a.surgimento = 9
        s.agir({"tipo": "jogar", "indice": 0})
        pend = s.estado()["pendente"]
        self.assertEqual(pend["tipo"], "escolher")
        self.assertEqual(len(pend["opcoes"]), 2)
        with self.assertRaises(ValueError):
            s.agir({"tipo": "passar"})                           # não dá para seguir sem responder
        s.agir({"tipo": "responder", "valor": 1})
        self.assertIsNone(s.estado()["pendente"])
        self.assertEqual((alvo1.dano, alvo2.dano), (0, 3))       # escolheu o segundo

    def test_partidas_completas_sem_erro(self):
        for seed in range(8):
            rng = random.Random(seed)
            s = nova(seed)
            for _ in range(3000):
                st = s.estado(0)
                self.assertFalse(s.erro and "interno" in s.erro, s.erro)
                if st["pendente"]:
                    s.agir({"tipo": "responder", "valor": 0 if st["pendente"]["tipo"] == "escolher" else True})
                elif st["etapa"] == "fim":
                    break
                elif st["etapa"] == "moeda":
                    s.agir({"tipo": "lado", "lado": "coroa"})
                elif st["etapa"] == "mulligan":
                    s.agir({"tipo": "mulligan", "indices": []})
                else:
                    idx = st["jogador_da_fase"]
                    jog = s.estado(idx)["jogadores"][idx]
                    jogavel = [c for c in jog["mao"] if c["jogavel"]]
                    if jogavel:
                        c = jogavel[0]
                        s.agir({"tipo": "jogar", "indice": c["i"], "coluna": rng.randrange(5)})
                    else:
                        s.agir({"tipo": "passar"})
            self.assertEqual(s.estado()["etapa"], "fim", f"seed {seed}")
            self.assertIsNotNone(s.estado()["vencedor"])


if __name__ == "__main__":
    unittest.main()

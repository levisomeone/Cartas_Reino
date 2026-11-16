import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from game import cartas, estado, habilidades  # noqa: E402

LISTA = cartas.carregar_cartas(RAIZ / "data" / "cards.json")
CARTAS = {c["id"]: c for c in LISTA}


class Base(unittest.TestCase):
    def setUp(self):
        self.p = estado.Partida(seed=1)
        self.a, self.b = self.p.jogadores
        self.p.iniciar_rodada()

    def inv(self, jogador, cid, col=0, fil="frente"):
        return self.p.invocar(jogador, CARTAS[cid], col, fil)

    def mao(self, jogador, cid):
        jogador.mao.append(CARTAS[cid])
        jogador.surgimento = 99
        return CARTAS[cid]


class TestPersistencia(Base):
    def test_ciclo_completo(self):
        z = self.inv(self.a, "zumbi_campones")
        self.p.causar_dano(z, 3)
        self.assertIs(self.a.campo[0]["frente"], z)
        self.assertTrue(z.inativa)
        self.p.iniciar_rodada()
        self.assertEqual((z.ataque, z.vida), (1, 1))
        self.p.causar_dano(z, 1)
        self.assertIsNone(self.a.campo[0]["frente"])
        self.assertEqual(len(self.a.cemiterio), 1)


class TestDanoECura(Base):
    def test_feitico_dano_e_imunidades(self):
        gi = self.inv(self.b, "guarda_imperial")
        nv = self.inv(self.b, "novata_vampira", 1)
        gm = self.inv(self.b, "golem_de_pedra", 2)
        self.mao(self.a, "hecatombe"); self.mao(self.a, "hecatombe"); self.mao(self.a, "hecatombe")
        for alvo in (gi, nv, gm):
            self.p.jogar_carta(self.a, CARTAS["hecatombe"], alvo=alvo)
        self.assertEqual((gi.dano, nv.dano, gm.dano), (0, 0, 2))

    def test_gargula_e_cinturao(self):
        g = self.inv(self.b, "gargula_ancestral")
        atk = self.inv(self.a, "lobo_sangrento")
        self.p.atacar(atk, g)
        self.assertEqual(g.dano, 1)
        c = self.inv(self.b, "esqueleto_errante", 1)
        c.item = CARTAS["cinturao_do_sobrevivente"]
        self.p.causar_dano(c, 1); self.assertEqual(c.dano, 0)
        self.p.causar_dano(c, 1); self.assertEqual(c.dano, 1)

    def test_anel_focus_sash(self):
        c = self.inv(self.a, "arqueiro_da_floresta")
        c.item = CARTAS["anel_da_redencao"]
        self.p.causar_dano(c, 9)
        self.assertEqual(c.vida, 1)
        self.p.causar_dano(c, 9)
        self.assertTrue(c.morta)

    def test_pocao_e_cura_limitada(self):
        c = self.inv(self.a, "gargula_ancestral")
        c.dano = 2
        self.mao(self.a, "pocao_de_cura")
        self.p.jogar_carta(self.a, CARTAS["pocao_de_cura"], alvo=c)
        self.assertEqual(c.dano, 0)

    def test_vitoria(self):
        self.p.dano_jogador(self.b, 40)
        self.assertIs(self.p.vencedor, self.a)


class TestPremios(Base):
    def test_dois_marcos_de_uma_vez(self):
        self.a.premio = [CARTAS["hecatombe"]] * 4
        self.p.dano_jogador(self.b, 17, self.inv(self.a, "lobo_sangrento"))
        self.assertEqual(len(self.a.mao), 2)
        self.assertEqual(len(self.a.premio), 2)


class TestAtaques(Base):
    def test_veneno_e_dreno(self):
        v = self.inv(self.b, "esqueleto_errante")
        self.p.atacar(self.inv(self.a, "aranha_venenosa"), v)
        self.assertEqual(v.ataque, 1)
        vs = self.inv(self.a, "vampiro_sanguinario", 1)
        vs.dano = 2
        self.p.atacar(vs, self.inv(self.b, "parede_centenaria", 1))
        self.assertEqual(vs.dano, 1)

    def test_golpe_furtivo_e_lobo_sombrio(self):
        novo = self.inv(self.b, "parede_centenaria")
        self.p.atacar(self.inv(self.a, "assassino_esqueletico"), novo)
        self.assertEqual(novo.dano, 4)
        lobo = self.inv(self.a, "lobo_sombrio", 1, "retaguarda")
        alvo = self.inv(self.b, "parede_centenaria", 1)
        self.p.atacar(lobo, alvo)
        self.assertEqual(alvo.dano, 2)

    def test_lobisomem_so_contra_criatura(self):
        w = self.inv(self.a, "lobisomem_furioso")
        c = self.inv(self.b, "parede_centenaria")
        self.p.atacar(w, c); self.assertEqual(c.dano, 3)
        self.b.campo[0]["frente"] = None
        self.p.atacar(w, self.b); self.assertEqual(self.b.vida, 38)

    def test_heroi_morcego_marca_saque(self):
        self.p.atacar(self.inv(self.a, "morcego_das_trevas"))
        self.assertEqual(self.b.vida, 38)
        self.a.vida = 30
        self.p.atacar(self.inv(self.a, "goblin_saqueador", 1))
        self.assertEqual(self.a.vida, 32)
        c = self.inv(self.b, "parede_centenaria", 2)
        self.p.atacar(self.inv(self.a, "cacadora_da_noite", 2), c)
        self.assertEqual(self.b.vida, 38 - 2 - 4)

    def test_evasao(self):
        self.inv(self.b, "parede_centenaria")
        self.p.atacar(self.inv(self.a, "espectro_errante"))
        self.assertEqual(self.b.vida, 39)

    def test_congelar_silenciar_e_ataque_adjacente(self):
        alvo = self.inv(self.b, "parede_centenaria")
        self.p.em_batalha = True
        self.p.atacar(self.inv(self.a, "espectro_glacial"), alvo)
        self.p.atacar(self.inv(self.a, "banshee", 1), alvo)
        self.assertTrue(alvo.status["sem_atacar"] and alvo.status["silenciada"])
        vizinha = self.inv(self.b, "parede_centenaria", 1)
        self.p.atacar(self.inv(self.a, "arqueiro_ossario", 2), alvo)
        self.assertEqual(vizinha.dano, 2)

    def test_zumbi_errante_devolve_ou_mata(self):
        z = self.inv(self.a, "zumbi_errante")
        forte = self.inv(self.b, "parede_centenaria")
        self.p.atacar(z, forte)
        self.assertEqual(len(self.b.mao), 1)
        fraco = self.inv(self.b, "corvo_agourento")
        self.b.deck.append(CARTAS["hecatombe"])
        self.p.atacar(z, fraco)
        self.assertEqual(len(self.b.cemiterio), 1)

    def test_mago_do_caos_cresce_e_lich(self):
        m = self.inv(self.a, "mago_do_caos")
        self.p.atacar(m, self.inv(self.b, "esqueleto_errante"))
        self.assertEqual(m.ataque, 3)
        l = self.inv(self.a, "lich_reanimador", 1)
        self.p.atacar(l, self.inv(self.b, "esqueleto_errante", 1))
        self.assertEqual(l.vida, 5)


class TestEntrada(Base):
    def test_compras_e_buscas(self):
        self.a.deck = [CARTAS["hecatombe"]] * 3
        self.inv(self.a, "arqueiro_da_floresta")
        self.assertEqual(len(self.a.mao), 1)
        self.mao(self.a, "lamento_das_almas")
        self.p.jogar_carta(self.a, CARTAS["lamento_das_almas"])
        self.assertEqual(len(self.a.mao), 3)

    def test_videira_busca_ou_nao_ativa(self):
        self.a.deck = [CARTAS["hecatombe"]]
        self.inv(self.a, "monstro_de_videira")
        self.assertEqual(len(self.a.mao), 0)
        self.a.deck.append(CARTAS["pe_de_feijao"])
        self.inv(self.a, "monstro_de_videira", 1)
        self.assertEqual([c["nome"] for c in self.a.mao], ["Pé de Feijão"])

    def test_invocacoes(self):
        self.inv(self.a, "necromante", 1)
        self.assertEqual(self.a.campo[2]["frente"].nome, "Esqueleto")
        e = self.inv(self.a, "esqueleto_guerreiro", 4)
        self.p.causar_dano(e, 5)
        self.assertEqual(self.a.campo[4]["frente"].nome, "Esqueleto")

    def test_dano_de_entrada(self):
        alvos = [self.inv(self.b, "parede_centenaria", i) for i in range(2)]
        self.inv(self.a, "mtech_600k", 4)
        self.assertEqual([x.dano for x in alvos], [3, 3])
        self.inv(self.a, "goblin_zarabatana", 1, "retaguarda")
        self.assertEqual(alvos[0].dano + alvos[1].dano, 8)

    def test_dragao_do_fim_e_chefe_goblin(self):
        self.inv(self.a, "guerreiro_goblin", 0)
        self.inv(self.a, "guerreiro_goblin", 1)
        self.inv(self.a, "chefe_goblin", 2)
        self.assertEqual([c.ataque for c in self.a.criaturas()], [2, 2, 2])
        self.inv(self.a, "dragao_do_fim", 3)
        self.assertEqual(self.b.vida, 40 - 2 - 4 * 3)

    def test_necromante_sombrio_e_lich(self):
        self.a.deck = [CARTAS["gavinhas"], CARTAS["dragao_do_fim"]]
        self.inv(self.b, "esqueleto_errante")
        self.inv(self.a, "necromante_sombrio")
        self.assertEqual([c["nome"] for c in self.a.mao], ["Gavinhas"])
        self.b.mao = [CARTAS["hecatombe"]]
        self.inv(self.a, "lich_reanimador", 1)
        self.assertEqual(len(self.b.premio), 1)

    def test_comandante_perdido(self):
        self.a.premio = [CARTAS["hecatombe"]]
        self.a.mao = [CARTAS["gavinhas"]]
        self.inv(self.a, "comandante_perdido")
        self.assertEqual(self.a.premio[0]["nome"], "Gavinhas")

    def test_irritador_e_cavaleiros(self):
        alvo = self.inv(self.b, "esqueleto_errante")
        self.inv(self.a, "irritador", 1)
        self.assertEqual(alvo.posicao, (0, "retaguarda"))
        self.a.deck = [CARTAS["esqueleto_errante"], CARTAS["adaga_afiada"]]
        c = self.p.invocar(self.a, CARTAS["cavaleiro_esqueletico_investida"], 2, "retaguarda")
        self.assertEqual(c.posicao, (2, "frente"))
        self.p.atacar(self.inv(self.a, "cavaleiro_esqueletico_lealdade", 3))
        self.assertEqual(len(self.a.mao), 1)

    def test_fadas_impedem_ataque(self):
        alvo = self.inv(self.b, "parede_centenaria")
        self.inv(self.a, "fada_maligna")
        self.assertFalse(self.p.pode_atacar(alvo))

    def test_lapide_protege_de_feiticos(self):
        v = self.inv(self.a, "esqueleto_errante", 1)
        self.inv(self.a, "lapide_profanada", 0)
        self.p.causar_dano(v, 3, None, "feitico")
        self.assertEqual(v.dano, 0)


class TestEntradaAgressiva(Base):
    def test_ataca_ao_entrar_e_todos_atacam_na_batalha(self):
        alvo = self.inv(self.b, "parede_centenaria")
        g = self.inv(self.a, "guerreiro_goblin")
        self.assertEqual(alvo.dano, 1)
        self.assertTrue(self.p.pode_atacar(g))
        normal = self.inv(self.a, "lobo_sangrento", 1)
        self.assertTrue(self.p.pode_atacar(normal))


class TestAuras(Base):
    def test_auras(self):
        l1 = self.inv(self.a, "lobo_sangrento", 0)
        self.inv(self.a, "lobo_alfa", 1)
        self.assertEqual(l1.ataque, 3)
        e = self.inv(self.a, "esqueleto_errante", 2)
        s = self.inv(self.a, "senhor_dos_ossos", 3)
        self.assertEqual((e.ataque, s.ataque), (3, 4))
        g = self.inv(self.a, "guardiao_da_cripta", 4)
        self.assertEqual(s.vida, 4)
        self.p.causar_dano(g, 99)
        self.assertEqual(s.vida, 3)
        self.inv(self.a, "mago_novato", 0, "retaguarda")
        self.assertEqual(l1.vida, 3)
        vn = self.inv(self.b, "vampiro_nobre", 0)
        vs = self.inv(self.b, "vampiro_sanguinario", 1)
        self.assertEqual((vn.ataque, vs.ataque), (2, 4))

    def test_adaga_e_item(self):
        c = self.inv(self.a, "lobo_sangrento")
        self.mao(self.a, "adaga_afiada")
        self.p.jogar_carta(self.a, CARTAS["adaga_afiada"], alvo=c)
        self.assertEqual(c.ataque, 3)


class TestFeiticos(Base):
    def test_assombracao_bandeira_frenesi(self):
        alvo = self.inv(self.b, "corvo_agourento")
        self.mao(self.a, "assombracao")
        self.a.vida = 10
        self.p.jogar_carta(self.a, CARTAS["assombracao"], alvo=alvo)
        self.assertTrue(alvo.morta)
        self.assertEqual(self.a.vida, 11)
        c = self.inv(self.a, "lobo_sangrento")
        self.mao(self.a, "bandeira_goblin")
        self.p.jogar_carta(self.a, CARTAS["bandeira_goblin"], alvo=c)
        self.assertEqual((c.ataque, c.vida), (3, 4))
        self.mao(self.a, "frenesi")
        v = self.inv(self.b, "parede_centenaria")
        self.p.jogar_carta(self.a, CARTAS["frenesi"], alvo=c)
        self.assertEqual(v.dano, 3)

    def test_destruicao_massiva_e_frio(self):
        grande = self.inv(self.b, "dragao_do_fim")
        pequeno = self.inv(self.b, "corvo_agourento", 1)
        self.mao(self.a, "destruicao_massiva")
        self.p.jogar_carta(self.a, CARTAS["destruicao_massiva"])
        self.assertTrue(grande.morta and not pequeno.morta)
        self.mao(self.a, "frio_congelante")
        self.p.jogar_carta(self.a, CARTAS["frio_congelante"], alvo=pequeno)
        self.assertFalse(self.p.pode_atacar(pequeno))

    def test_extracao_volta_ao_campo(self):
        c = self.inv(self.a, "gargula_ancestral")
        self.mao(self.a, "extracao")
        self.p.jogar_carta(self.a, CARTAS["extracao"], alvo=c)
        self.assertEqual(self.a.campo[0]["frente"].nome, "Extração")
        self.assertIn(CARTAS["gargula_ancestral"], self.a.mao)
        self.p.fim_de_batalha()
        self.assertEqual(self.a.campo[0]["frente"].nome, "Gárgula Ancestral")

    def test_goblin_maniaco_e_dragao_de_jade(self):
        self.inv(self.a, "goblin_maniaco")
        self.inv(self.b, "dragao_de_jade")
        self.mao(self.a, "lamento_das_almas")
        self.p.jogar_carta(self.a, CARTAS["lamento_das_almas"])
        self.assertEqual(self.b.vida, 39)
        self.assertEqual(self.a.vida, 38)


class TestTerrenos(Base):
    def test_lava_feijao_espinhos_iluminacao(self):
        mia = self.inv(self.a, "gargula_ancestral", 0)
        self.mao(self.b, "poca_de_lava")
        self.p.jogar_carta(self.b, CARTAS["poca_de_lava"], coluna=0)
        self.mao(self.a, "pe_de_feijao")
        self.p.jogar_carta(self.a, CARTAS["pe_de_feijao"], coluna=0)
        self.p.fim_de_batalha()
        self.assertEqual(mia.dano, 2)
        self.mao(self.a, "iluminacao_aurea")
        self.p.jogar_carta(self.a, CARTAS["iluminacao_aurea"], coluna=0)
        self.assertIsNone(self.b.terrenos[0])
        self.assertEqual(mia.dano, 1)
        self.mao(self.b, "espinhos_mandragora")
        self.p.jogar_carta(self.b, CARTAS["espinhos_mandragora"], coluna=1)
        a1 = self.inv(self.a, "dragao_do_fim", 1)
        self.assertEqual(a1.dano, 2)
        a2 = self.inv(self.a, "lobo_sangrento", 1, "retaguarda")
        self.assertEqual(a2.dano, 1)

    def test_armadura_imune_terreno(self):
        c = self.inv(self.a, "lobo_sangrento")
        c.item = CARTAS["armadura_indigna"]
        self.mao(self.b, "poca_de_lava")
        self.p.jogar_carta(self.b, CARTAS["poca_de_lava"], coluna=0)
        self.p.fim_de_batalha()
        self.assertEqual(c.dano, 0)


class TestRodada(Base):
    def test_sobreviver_e_fim_de_batalha(self):
        e = self.inv(self.a, "espadachim_solitario")
        self.inv(self.a, "cenotafio", 1)
        self.a.surgimento = 0
        self.p.fim_de_batalha()
        self.assertEqual((e.ataque, e.vida), (2, 3))
        self.assertEqual(self.a.surgimento, 1)
        g = self.inv(self.a, "goblin_incendiario", 2)
        self.inv(self.b, "goblin_maniaco")
        self.p.fim_de_batalha()
        self.assertTrue(g.morta)
        self.assertEqual(self.a.vida, 39)

    def test_broto_troca(self):
        self.a.deck = [CARTAS["gargula_ancestral"], CARTAS["corvo_agourento"],
                       CARTAS["goblin_saqueador"], CARTAS["cavaleiro_esqueletico_lealdade"]]
        self.inv(self.a, "broto_arcaico")
        self.p.fim_de_batalha()
        self.assertEqual(self.a.campo[0]["frente"].nome, "Cavaleiro Esquelético")

    def test_skinwalker_camufla(self):
        s = self.inv(self.b, "skinwalker", 2)
        self.p.iniciar_rodada()
        self.assertEqual(s.posicao, (3, "frente"))
        self.mao(self.a, "hecatombe")
        self.p.jogar_carta(self.a, CARTAS["hecatombe"])
        self.assertEqual(s.dano, 0)

    def test_rato_cadaverico_e_ceifador(self):
        r1 = self.inv(self.a, "rato_cadaverico", 0)
        self.a.mao.append(CARTAS["rato_cadaverico"])
        self.a.surgimento = 9
        self.p.jogar_carta(self.a, CARTAS["rato_cadaverico"], coluna=1)
        self.assertEqual(r1.ataque, 2)
        ce = self.inv(self.b, "ceifador_de_almas", 3)
        self.a.mao.append(CARTAS["esqueleto_errante"])
        self.p.jogar_carta(self.a, CARTAS["esqueleto_errante"], coluna=2)
        self.assertEqual(ce.posicao[0], 2)

    def test_arvore_maligna_e_cogumelo_e_planta(self):
        alvo = self.inv(self.b, "dragao_do_fim")
        arv = self.inv(self.a, "arvore_maligna")
        self.p.rng.seed(3)
        for _ in range(20):
            if alvo.dano:
                break
            arv.ativada_na_rodada.clear()
            self.p.ativar(arv)
        self.assertEqual(alvo.dano, 7)
        c = self.inv(self.a, "cogumelo_toxico", 1)
        self.p.atacar(c, self.inv(self.b, "parede_centenaria", 1))
        self.assertEqual(c.ataque, 2)
        pc = self.inv(self.a, "planta_carnivora", 2)
        pc.dano = 1
        self.p.atacar(pc, self.inv(self.b, "esqueleto_errante", 2))
        self.assertEqual(pc.dano, 0)


class TestBatalha(Base):
    """Resolução da fase de batalhas: simultânea, coluna a coluna."""

    def test_quem_morre_ainda_ataca(self):
        a = self.inv(self.a, "lobo_sangrento")           # 2/2
        b = self.inv(self.b, "lobo_sangrento")
        self.p.resolver_batalha()
        self.assertTrue(a.morta and b.morta)             # trocaram golpes ao mesmo tempo

    def test_retaguarda_ataca_sem_esperar_a_frente(self):
        self.inv(self.a, "parede_centenaria", 0, "frente")
        arq = self.inv(self.a, "lobo_sangrento", 0, "retaguarda")
        alvo = self.inv(self.b, "parede_centenaria", 0, "frente")
        self.p.resolver_batalha()
        self.assertEqual(alvo.dano, 2)                   # a parede tem 0 de ataque; só o lobo bate
        self.assertFalse(arq.morta)

    def test_coluna_vazia_vai_no_heroi(self):
        self.inv(self.a, "lobo_sangrento", 0)
        self.inv(self.a, "lobo_sangrento", 3)
        self.p.resolver_batalha()
        self.assertEqual(self.b.vida, 36)

    def test_dano_excedente_nao_atravessa(self):
        self.inv(self.a, "dragao_do_fim", 0)             # 3 de ataque
        frente = self.inv(self.b, "corvo_agourento", 0, "frente")
        tras = self.inv(self.b, "corvo_agourento", 0, "retaguarda")
        self.p.resolver_batalha()
        self.assertTrue(frente.morta)
        self.assertEqual(tras.dano, 0)

    def test_ciclo_de_rodada_surgimento_compra_e_cemiterio(self):
        self.a.deck = [CARTAS["hecatombe"]] * 3
        self.b.deck = [CARTAS["hecatombe"]] * 3
        self.a.cemiterio = [(CARTAS["corvo_agourento"], 0)]
        self.p.resolver_batalha()
        self.p.fim_de_rodada()
        self.assertEqual((self.a.surgimento, self.b.surgimento), (3, 3))     # 2 + 1ª batalha
        self.assertEqual(len(self.a.mao), 1)
        self.p.iniciar_rodada(); self.p.resolver_batalha(); self.p.fim_de_rodada()
        self.assertEqual(self.a.surgimento, 5)                                # + 2ª batalha
        self.assertEqual(self.a.cemiterio, [])                                # voltou ao deck
        self.assertIn(CARTAS["corvo_agourento"], self.a.deck + self.a.mao)

    def test_vitoria_encerra_a_batalha(self):
        self.b.vida = 2
        self.inv(self.a, "lobo_sangrento", 0)
        self.inv(self.a, "lobo_sangrento", 1)
        self.p.resolver_batalha()
        self.assertIs(self.p.vencedor, self.a)


class TestTodasAsCartas(Base):
    """Fumaça: toda carta pode ser jogada e ter suas habilidades disparadas sem erro."""

    def test_jogar_todas(self):
        for carta in LISTA:
            p = estado.Partida(seed=7)
            a, b = p.jogadores
            p.iniciar_rodada()
            for i, cid in enumerate(("esqueleto_errante", "parede_centenaria", "lobo_alfa")):
                p.invocar(a, CARTAS[cid], i, "frente")
                p.invocar(b, CARTAS[cid], i, "frente")
            a.deck = [CARTAS[c] for c in ("gavinhas", "pe_de_feijao", "esqueleto_errante", "dragao_de_jade")]
            b.deck = list(a.deck)
            b.mao, b.premio = [CARTAS["hecatombe"]], [CARTAS["hecatombe"]]
            a.mao, a.premio, a.surgimento = [carta], [CARTAS["gavinhas"]], 99
            try:
                col = 4 if carta["tipo"] in ("Criatura", "Terreno") else None
                p.jogar_carta(a, carta, coluna=col)
                for c in list(p.todas_criaturas()):
                    p.ativar(c)
                p.resolver_batalha()
                p.fim_de_rodada()
                p.iniciar_rodada()
                p.resolver_batalha()
            except Exception as e:  # noqa: BLE001
                self.fail(f"{carta['id']}: {type(e).__name__}: {e}")

    def test_todos_os_efeitos_programados(self):
        pendentes = [c["id"] for c in LISTA for h in c["habilidades"]
                     if h["efeito"] not in habilidades.REGISTRO]
        self.assertEqual(pendentes, [])


class TestDados(unittest.TestCase):
    def test_cartas_validas(self):
        self.assertEqual(cartas.validar_cartas(LISTA), [])

    def test_deck_invalido(self):
        self.assertTrue(cartas.validar_deck({"principal": {"a": 4}, "premio": {}}, LISTA))


if __name__ == "__main__":
    unittest.main()


class TestRework(Base):
    def test_margarida_cura_o_heroi(self):
        self.a.vida = 30
        self.inv(self.a, "margarida_curativa")
        self.assertEqual(self.a.vida, 32)

    def test_fada_das_ilusoes_reduz_custo(self):
        carta = CARTAS["zumbi_campones"]
        base = self.p.custo_de(self.a, carta)
        self.inv(self.a, "fada_das_ilusoes", 1)
        self.assertEqual(self.p.custo_de(self.a, carta), max(0, base - 1))
        self.assertEqual(self.p.custo_de(self.b, carta), base)

    def test_espectro_do_vazio_revive_e_causa_dano(self):
        esp = CARTAS["espectro_do_vazio"]
        outro = next(c for c in LISTA if c["tipo"] == "Criatura" and "Espectro" in estado.tribos_de(c)
                     and c["id"] != "espectro_do_vazio")
        self.a.cemiterio.append((outro, self.p.rodada))
        self.inv(self.a, "espectro_do_vazio", 0)
        self.assertEqual(len(self.a.criaturas()), 2)
        self.assertEqual(self.a.cemiterio, [])
        self.assertGreaterEqual(40 - self.b.vida, 1)
        self.assertIn(40 - self.b.vida, (1, 1 + 2 * outro["ataque"]))

    def test_espectro_do_vazio_sem_cemiterio(self):
        self.inv(self.a, "espectro_do_vazio", 0)
        self.assertEqual(40 - self.b.vida, 1)

class TestAlvosPorLado(Base):
    def test_feitico_de_dano_nao_acerta_criatura_propria(self):
        z = self.inv(self.a, "zumbi_campones")
        vida = z.vida
        self.mao(self.a, "hecatombe")
        self.p.jogar_carta(self.a, CARTAS["hecatombe"], None, None)
        self.assertEqual(z.vida, vida)

    def test_feitico_de_dano_acerta_inimiga(self):
        e = self.inv(self.b, "parede_centenaria")
        self.inv(self.a, "zumbi_campones")
        vida = e.vida
        self.mao(self.a, "hecatombe")
        self.p.jogar_carta(self.a, CARTAS["hecatombe"], None, None)
        self.assertLess(e.vida, vida)

    def test_pocao_so_cura_propria(self):
        e = self.inv(self.b, "parede_centenaria")
        self.p.causar_dano(e, 2)
        vida = e.vida
        z = self.inv(self.a, "zumbi_campones")
        self.p.causar_dano(z, 1)
        self.mao(self.a, "pocao_de_cura")
        self.p.jogar_carta(self.a, CARTAS["pocao_de_cura"], None, None)
        self.assertEqual(e.vida, vida)
        self.assertEqual(z.vida, z.vida_max)


class TestNovasCartas(Base):
    def _terreno(self, jogador, cid, col):
        return self.p.colocar_terreno(jogador, CARTAS[cid], col)

    def test_cemiterio_ancestral_da_surgimento_por_criatura_aliada(self):
        self._terreno(self.a, "cemiterio_ancestral", 0)
        s0 = self.a.surgimento
        self.inv(self.a, "zumbi_campones", 0, "frente")
        self.assertEqual(self.a.surgimento, s0 + 1)
        self.inv(self.a, "zumbi_campones", 0, "retaguarda")
        self.assertEqual(self.a.surgimento, s0 + 1 + 2)          # agora são 2 criaturas na coluna

    def test_cemiterio_ancestral_ignora_inimiga_e_outras_colunas(self):
        self._terreno(self.a, "cemiterio_ancestral", 0)
        s0, sb = self.a.surgimento, self.b.surgimento
        self.inv(self.b, "zumbi_campones", 0, "frente")
        self.inv(self.a, "zumbi_campones", 1, "frente")
        self.assertEqual((self.a.surgimento, self.b.surgimento), (s0, sb))

    def test_mandragora_causa_dano_continuo(self):
        self._terreno(self.a, "espinhos_mandragora", 0)
        e = self.inv(self.b, "parede_centenaria", 0)            # custo 1, 5 de vida
        self.assertEqual(e.vida, 4)                             # dano ao entrar
        self.p.fim_de_batalha()
        self.assertEqual(e.vida, 3)                             # e de novo a cada batalha
        self.p.fim_de_batalha()
        self.assertEqual(e.vida, 2)

    def test_mandragora_nao_fere_criatura_do_dono(self):
        self._terreno(self.a, "espinhos_mandragora", 0)
        z = self.inv(self.a, "parede_centenaria", 0)
        self.p.fim_de_batalha()
        self.assertEqual(z.vida, z.vida_max)

    def test_fragilidade_soma_dano_so_na_batalha(self):
        self.inv(self.a, "senhor_das_tumbas", 0)
        alvo = self.inv(self.b, "parede_centenaria", 2)
        self.p.disparar("ao_inicio_batalha", self.a.campo[0]["frente"])
        self.assertTrue(alvo.status.get("fragil"))
        v = alvo.vida
        self.p.causar_dano(alvo, 1, None, "feitico")
        self.assertEqual(alvo.vida, v - 2)
        self.p.fim_de_batalha()
        self.assertFalse(alvo.status.get("fragil"))

    def test_frenesi_ataca_criatura_de_outra_coluna(self):
        senhor = self.inv(self.a, "senhor_das_tumbas", 0)
        alvo = self.inv(self.b, "parede_centenaria", 3)
        v = alvo.vida
        self.p.atacar(senhor)
        self.assertLess(alvo.vida, v)

    def test_frenesi_sem_inimigas_ataca_o_heroi(self):
        senhor = self.inv(self.a, "senhor_das_tumbas", 0)
        self.p.atacar(senhor)
        self.assertEqual(self.b.vida, 40 - 3)

    def test_necromante_busca_carta_ao_eliminar(self):
        e = self.inv(self.b, "morcegos", 0)
        self.p.causar_dano(e, e.vida - 1)
        self.a.deck.append(CARTAS["zumbi_campones"])
        self.inv(self.a, "necromante_sombrio", 1)
        self.assertIn(CARTAS["zumbi_campones"], self.a.mao)

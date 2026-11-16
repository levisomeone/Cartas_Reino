"""Efeitos das cartas.

Como adicionar uma habilidade nova:
  1. Escreva uma função com o decorador @efeito("nome_do_efeito").
  2. Use esse mesmo nome no campo "efeito" da carta em data/cards.json.

Assinatura:   def meu_efeito(partida, fonte, params, ctx) -> dict | None

  partida : a Partida em andamento (game/estado.py)
  fonte   : quem tem a habilidade (Criatura, Terreno ou Feitico)
  params  : o dicionário "params" da habilidade no JSON
  ctx     : informações do momento (ex.: ctx["alvo"] no ataque ou no feitiço)

Retornos especiais:  {"impedir_morte": True}  /  {"fica_em_campo": True}

Habilidades "passivas" (aura, imunidade, redução de dano...) são apenas
marcadores: o motor (estado.py) lê o efeito quando precisa. Ficam registradas
aqui para constar como programadas.

Escolhas do jogador usam partida.escolher(...): na arena viram uma pergunta na
tela; nos testes escolhe o primeiro (inimigos antes de aliados).
"""

REGISTRO = {}

GATILHOS = ("ao_entrar", "ao_morrer", "ao_sobreviver", "passiva", "ativavel",
            "ao_atacar", "ao_causar_dano", "ao_usar", "ao_usar_feitico",
            "ao_fim_batalha", "ao_causar_dano_jogador", "ao_eliminar",
            "ao_carta_jogada_adjacente", "ao_inimigo_usa_feitico", "ao_aliado_equipa",
            "ao_inimigo_entra_coluna", "ao_aliado_entra_coluna", "ao_inicio_batalha", "ao_entrar_terreno", "ao_carta_jogada",
            "ao_inicio_rodada")


def efeito(nome):
    def registrar(funcao):
        REGISTRO[nome] = funcao
        return funcao
    return registrar


def marcador(*nomes):
    """Registra efeitos passivos que o motor lê diretamente."""
    for n in nomes:
        REGISTRO[n] = lambda partida, fonte, params, ctx: None


# ---------------------------------------------------------------- auxiliares

def _eh_criatura(x):
    return getattr(x, "tipo_fonte", "") == "criatura"


def _origem(fonte):
    return fonte if _eh_criatura(fonte) else None


def _tipo_dano(fonte):
    return {"feitico": "feitico", "terreno": "terreno"}.get(fonte.tipo_fonte, "habilidade")


def _inimigas(p, f):
    return [c for c in p.oponente(f.dono).criaturas() if not c.status.get("camuflada")]


def _aliadas(p, f):
    return [c for c in f.dono.criaturas() if c is not f]


def _alvo(p, f, candidatos, ctx, msg="Escolha o alvo"):
    """Usa ctx['alvo'] se for válido; senão escolhe entre os candidatos."""
    alvo = ctx.get("alvo")
    if alvo is not None and alvo in candidatos:
        return alvo
    if not candidatos:
        return None
    return candidatos[0] if len(candidatos) == 1 else p.escolher(f.dono, candidatos, msg, fonte=f)


def _casa(carta, params):
    """A carta atende aos filtros de busca (tipo, tribo, nome, custo)?"""
    from .estado import tribos_de
    if "tipo" in params and carta["tipo"] != params["tipo"]:
        return False
    if "tribo" in params and params["tribo"] not in tribos_de(carta):
        return False
    if "nome_carta" in params and carta["nome"] != params["nome_carta"]:
        return False
    if "custo" in params and carta.get("custo") != params["custo"]:
        return False
    if "custo_max" in params and carta.get("custo", 0) > params["custo_max"]:
        return False
    return True


def _buscar(p, j, params):
    """Procura no deck, move a carta escolhida para a mão e embaralha."""
    achados = [c for c in j.deck if _casa(c, params)]
    if not achados:
        return None
    carta = achados[0] if len(achados) == 1 else p.escolher(j, achados, "Escolha uma carta do deck")
    j.deck.remove(carta)
    j.mao.append(carta)
    p.embaralhar(j)
    return carta


def _vizinhas_livres(p, c, so_mesma_fileira=False):
    """Posições livres adjacentes (lados e fileira de trás/frente)."""
    col, fil = c.posicao
    outra = "retaguarda" if fil == "frente" else "frente"
    cand = [(col + 1, fil), (col - 1, fil)] + ([] if so_mesma_fileira else [(col, outra)])
    return [(x, y) for x, y in cand if 0 <= x < 5 and c.dono.campo[x][y] is None]


# ---------------------------------------------------------------- passivas (marcadores)
marcador("ataque_livre", "reduz_custo_criaturas", "aura_adjacentes", "aura_frente", "aura_tribo", "dano_extra",
         "evasao", "imune_feiticos", "imune_terreno_dano", "imune_terrenos_e_feiticos",
         "poder_ignora_resistencias", "reduzir_dano_ataque", "reduzir_dano_feitico",
         "reduzir_primeiro_dano", "sobreviver_com_1")


# ---------------------------------------------------------------- dano
@efeito("dano")
def dano(p, f, params, ctx):
    alvo = params.get("alvo", "carta")
    if alvo == "criatura_inimiga":
        cands = _inimigas(p, f)
    elif alvo == "carta_inimiga_adjacente":
        col = f.posicao[0]
        cands = [c for c in _inimigas(p, f) if abs(c.posicao[0] - col) <= 1]
    else:  # "carta": dano é sempre contra o inimigo, salvo carta que diga "qualquer" (params.alvo = "qualquer")
        cands = _inimigas(p, f) + (_aliadas(p, f) if params.get("alvo") == "qualquer" else [])
    a = _alvo(p, f, cands, ctx)
    if a:
        p.causar_dano(a, params["valor"], _origem(f), _tipo_dano(f))


@efeito("dano_direto")
def dano_direto(p, f, params, ctx):
    p.dano_jogador(p.oponente(f.dono), params["valor"], _origem(f))


@efeito("dano_direto_por_cartas")
def dano_direto_por_cartas(p, f, params, ctx):
    n = len(f.dono.criaturas()) + sum(1 for t in f.dono.terrenos if t)
    p.dano_jogador(p.oponente(f.dono), n * params["multiplicador"], _origem(f))


@efeito("dano_em_todas_inimigas")
def dano_em_todas_inimigas(p, f, params, ctx):
    for c in list(p.oponente(f.dono).criaturas()):
        p.causar_dano(c, params["valor"], _origem(f), _tipo_dano(f))


@efeito("dano_e_buscar_se_eliminar")
def dano_e_buscar_se_eliminar(p, f, params, ctx):
    a = _alvo(p, f, _inimigas(p, f), ctx)
    if a is None:
        return
    p.causar_dano(a, params["dano"], _origem(f), _tipo_dano(f))
    if a.morta:
        _buscar(p, f.dono, {"custo_max": params["custo_max"]})


@efeito("dano_proprio")
def dano_proprio(p, f, params, ctx):
    p.causar_dano(f, params["valor"], None, "habilidade")


@efeito("dano_na_coluna")
def dano_na_coluna(p, f, params, ctx):
    for c in p.criaturas_da_coluna(f.coluna):
        p.causar_dano(c, params["valor"], None, "terreno")


@efeito("dano_por_custo")
def dano_por_custo(p, f, params, ctx):
    c = ctx["criatura"]
    alto = c.carta.get("custo", 0) >= params["custo_min"]
    p.causar_dano(c, params["dano_alto"] if alto else params["dano"], None, "terreno")


@efeito("dano_por_custo_na_coluna")
def dano_por_custo_na_coluna(p, f, params, ctx):
    """Dano contínuo do terreno: a cada batalha, criaturas inimigas ao dono do terreno, na coluna."""
    for c in list(p.criaturas_da_coluna(f.coluna)):
        if c.dono is f.dono:
            continue
        alto = c.carta.get("custo", 0) >= params["custo_min"]
        p.causar_dano(c, params["dano_alto"] if alto else params["dano"], None, "terreno")


@efeito("surgimento_por_criaturas_na_coluna")
def surgimento_por_criaturas_na_coluna(p, f, params, ctx):
    """Cemitério Ancestral: ao entrar uma aliada, 1 de surgimento por criatura aliada na coluna."""
    n = sum(1 for c in p.criaturas_da_coluna(f.coluna) if c.dono is f.dono)
    if n:
        f.dono.surgimento += n * params["valor"]
        p.log(f"{f.nome}: {f.dono.nome} ganhou {n * params['valor']} de surgimento.")


@efeito("fragilizar")
def fragilizar(p, f, params, ctx):
    """Fragilidade: uma criatura inimiga escolhida toma +1 de dano de qualquer fonte nesta batalha."""
    a = _alvo(p, f, _inimigas(p, f), {}, "Escolha o alvo da Fragilidade")
    if a:
        a.status["fragil"] = 1                      # só esta batalha (some no fim dela)
        p.log(f"{f.nome} deixou {a.nome} frágil nesta batalha.")


@efeito("dano_igual_a_vida_se_cara")
def dano_igual_a_vida_se_cara(p, f, params, ctx):
    if p.moeda():
        a = _alvo(p, f, _inimigas(p, f), ctx)
        if a:
            p.causar_dano(a, f.vida, f, "habilidade")


@efeito("destruir_todas")
def destruir_todas(p, f, params, ctx):
    for c in p.todas_criaturas():
        if c.carta.get("custo", 0) >= params["custo_min"]:
            p.matar(c)
    for j in p.jogadores:
        for i, t in enumerate(j.terrenos):
            if t and t.carta.get("custo", 0) >= params["custo_min"]:
                p.enviar_cemiterio(j, t.carta)
                j.terrenos[i] = None


# ---------------------------------------------------------------- bônus no ataque
@efeito("atacar_ao_entrar")
def atacar_ao_entrar(p, f, params, ctx):
    """Agressivo: ao entrar em campo, ataca na hora (antes da fase de batalha)."""
    p.atacar(f)


@efeito("dano_extra_ataque")
def dano_extra_ataque(p, f, params, ctx):
    if params.get("se_fileira") and f.posicao[1] != params["se_fileira"]:
        return
    if params.get("so_criatura") and hasattr(ctx["alvo"], "campo"):
        return
    ctx["dano_extra"] += params["valor"]


@efeito("golpe_furtivo")
def golpe_furtivo(p, f, params, ctx):
    a = ctx["alvo"]
    if not hasattr(a, "campo") and a.entrou_na_rodada == p.rodada:
        ctx["dano_extra"] += params["dano_extra"]


@efeito("dano_extra_heroi_se_coluna_vazia")
def dano_extra_heroi(p, f, params, ctx):
    if hasattr(ctx["alvo"], "campo"):
        ctx["dano_extra"] += params["valor"]


@efeito("ataque_adjacente")
def ataque_adjacente(p, f, params, ctx):
    ctx["adjacente"] = True


@efeito("devolver_para_mao")
def devolver_para_mao(p, f, params, ctx):
    if not hasattr(ctx["alvo"], "campo"):
        ctx["devolver"] = True


@efeito("dano_heroi_repetido")
def dano_heroi_repetido(p, f, params, ctx):
    p.dano_jogador(p.oponente(f.dono), ctx["dano"], f)


@efeito("ataque_bonus")
def ataque_bonus(p, f, params, ctx):
    a = _alvo(p, f, f.dono.criaturas(), ctx, "Quem ataca?")
    for _ in range(params.get("quantidade", 1)):
        if a and not a.morta:
            p.atacar(a)


# ---------------------------------------------------------------- status e efeitos de controle
@efeito("congelar")
def congelar(p, f, params, ctx):
    a = ctx.get("alvo")
    if a is None or hasattr(a, "campo") or a.morta:
        a = _alvo(p, f, _inimigas(p, f), {}, "Quem congelar?")
    if a:
        p.aplicar_status(a, "sem_atacar", params["turnos"])


@efeito("impedir_ataque")
def impedir_ataque(p, f, params, ctx):
    a = _alvo(p, f, _inimigas(p, f), ctx)
    if a:
        p.aplicar_status(a, "sem_atacar", params["turnos"])


@efeito("silenciar")
def silenciar(p, f, params, ctx):
    a = ctx.get("alvo")
    if a is not None and not hasattr(a, "campo"):
        p.aplicar_status(a, "silenciada", params["turnos"])


@efeito("veneno")
def veneno(p, f, params, ctx):
    ctx["alvo"].bonus_ataque += params["ataque"]


@efeito("dar_protecao_feiticos")
def dar_protecao_feiticos(p, f, params, ctx):
    col = f.posicao[0]
    for c in _aliadas(p, f):
        if abs(c.posicao[0] - col) == 1:
            c.protecao_feiticos = True


# ---------------------------------------------------------------- cura
@efeito("curar")
def curar(p, f, params, ctx):
    alvo = params.get("alvo", "carta")
    if alvo in ("si_mesmo", "portador"):
        a = f
    elif alvo == "criatura_aliada":
        a = _alvo(p, f, _aliadas(p, f), ctx)
    else:
        a = _alvo(p, f, f.dono.criaturas(), ctx)         # cura só em criaturas suas
    if a:
        p.curar(a, params["valor"])


@efeito("curar_heroi")
def curar_heroi(p, f, params, ctx):
    """Margarida Curativa: cura a vida do próprio jogador."""
    p.curar_jogador(f.dono, params["valor"])


@efeito("curar_total")
def curar_total(p, f, params, ctx):
    f.dano = 0


@efeito("curar_igual_dano")
def curar_igual_dano(p, f, params, ctx):
    p.curar_jogador(f.dono, ctx["dano"])


@efeito("curar_cartas_nome")
def curar_cartas_nome(p, f, params, ctx):
    for c in f.dono.criaturas():
        if params["nome_contem"] in c.nome.lower():
            p.curar(c, params["valor"])


@efeito("curar_na_coluna")
def curar_na_coluna(p, f, params, ctx):
    for c in p.criaturas_da_coluna(f.coluna):
        p.curar(c, params["valor"])


@efeito("limpar_terrenos_e_curar")
def limpar_terrenos_e_curar(p, f, params, ctx):
    for j in p.jogadores:
        t = j.terrenos[f.coluna]
        if t and j is not f.dono:
            p.enviar_cemiterio(j, t.carta)
            j.terrenos[f.coluna] = None
    for c in p.criaturas_da_coluna(f.coluna):
        if params["exceto_tribo"] not in c.tribos:
            p.curar(c, params["valor"])


# ---------------------------------------------------------------- bônus de status
@efeito("aumentar_ataque_base")
def aumentar_ataque_base(p, f, params, ctx):
    f.bonus_ataque += params["valor"]


@efeito("aumentar_vida")
def aumentar_vida(p, f, params, ctx):
    f.bonus_vida += params["valor"]


@efeito("aumentar_status")
def aumentar_status(p, f, params, ctx):
    if params.get("se_carta") and ctx.get("carta", {}).get("nome") != params["se_carta"]:
        return
    f.bonus_ataque += params.get("ataque", 0)
    f.bonus_vida += params.get("vida", 0)


@efeito("buff")
def buff(p, f, params, ctx):
    a = _alvo(p, f, f.dono.criaturas(), ctx, "Quem fortalecer?")
    if a:
        a.bonus_ataque += params.get("ataque", 0)
        a.bonus_vida += params.get("vida", 0)


@efeito("buff_tribo_fileira")
def buff_tribo_fileira(p, f, params, ctx):
    for c in _aliadas(p, f):
        if c.posicao[1] == f.posicao[1] and params["tribo"] in c.tribos:
            c.bonus_ataque += params["ataque"]


@efeito("assombracao")
def assombracao(p, f, params, ctx):
    a = _alvo(p, f, _inimigas(p, f), ctx)               # penalidade só em inimigas
    if a is None:
        return
    a.bonus_ataque += params["ataque"]
    a.bonus_vida += params["vida"]
    p.verificar_mortes()
    if a.morta:
        p.curar_jogador(f.dono, params["cura_ao_matar"])


@efeito("ganhar_vida_por_tribo")
def ganhar_vida_por_tribo(p, f, params, ctx):
    from .estado import tribos_de
    t = params["tribo"]
    n = sum(1 for c in f.dono.criaturas() if t in c.tribos)
    n += sum(1 for carta, _ in f.dono.cemiterio if t in tribos_de(carta))
    f.bonus_vida += n * params["valor"]


@efeito("ganhar_surgimento")
def ganhar_surgimento(p, f, params, ctx):
    f.dono.surgimento += params["valor"]


# ---------------------------------------------------------------- cartas: comprar, buscar, prêmio
@efeito("comprar_cartas")
def comprar_cartas(p, f, params, ctx):
    p.comprar(f.dono, params["quantidade"])


@efeito("buscar_carta")
def buscar_carta(p, f, params, ctx):
    j = f.dono
    if params.get("opcional") and not p.confirmar(j, "Usar a habilidade?"):
        return
    if _buscar(p, j, params) is None and params.get("se_nao_houver") != "nao_ativa":
        p.comprar(j, 1)   # regra 16.6: sem carta válida, compra normal


@efeito("buscar_e_trocar")
def buscar_e_trocar(p, f, params, ctx):
    """Broto: troca de lugar com uma carta do deck (volta ao deck; a nova entra no campo)."""
    j = f.dono
    achados = [c for c in j.deck if c["tipo"] == "Criatura" and c.get("custo") == params["custo"]]
    if not achados:
        return
    nova = achados[0] if len(achados) == 1 else p.escolher(j, achados, "Escolha uma carta do deck")
    col, fil = f.posicao
    p.remover_do_campo(f)
    j.deck.remove(nova)
    j.deck.append(f.carta)
    p.embaralhar(j)
    p.invocar(j, nova, col, fil)


@efeito("banir_mao_para_premio")
def banir_mao_para_premio(p, f, params, ctx):
    opp = p.oponente(f.dono)
    if not opp.mao:
        return
    carta = p.escolher(f.dono, opp.mao, "Banir qual carta da mão do oponente?")
    opp.mao.remove(carta)
    opp.premio.append(carta)
    if len(opp.premio) > 4:                      # prêmio cheio: a mais antiga vai ao deck
        opp.deck.append(opp.premio.pop(0))
        p.embaralhar(opp)


@efeito("trocar_premio_por_mao")
def trocar_premio_por_mao(p, f, params, ctx):
    j = f.dono
    if not j.premio or not j.mao:
        return
    pr = p.escolher(j, j.premio, "Qual prêmio trocar?")
    mc = p.escolher(j, j.mao, "Por qual carta da mão?")
    j.premio[j.premio.index(pr)] = mc
    j.mao[j.mao.index(mc)] = pr


# ---------------------------------------------------------------- invocar, mover
@efeito("tumba_espectro")
def tumba_espectro(p, f, params, ctx):
    """Espectro do Vazio: revive um Espectro do cemitério e causa dano ao herói inimigo
    (1; se houver espectro revivido e a moeda der cara, soma 2x o ataque dele)."""
    from .estado import tribos_de
    j, opp = f.dono, p.oponente(f.dono)
    base = params.get("dano", 1)
    achados = [c for c, _ in j.cemiterio if c["tipo"] == "Criatura" and params.get("tribo", "Espectro") in tribos_de(c)]
    revivido = None
    livres = p.posicoes_livres(j)
    if achados and livres:
        carta = achados[0] if len(achados) == 1 else p.escolher(j, achados, "Reviver qual espectro?")
        pos = livres[0] if len(livres) == 1 else p.escolher(j, livres, "Onde colocar o espectro?")
        j.cemiterio.pop(next(i for i, (c, _) in enumerate(j.cemiterio) if c is carta))
        revivido = p.invocar(j, carta, *pos)
    dano = base
    if revivido is not None and p.moeda():     # cara: soma o dobro do ataque do espectro
        dano += 2 * revivido.ataque
    p.dano_jogador(opp, dano, f)

@efeito("invocar")
def invocar(p, f, params, ctx):
    j = f.dono
    col, fil = f.posicao
    outra = "retaguarda" if fil == "frente" else "frente"
    if params.get("posicao") == "lateral":
        ordem = [(col + 1, fil), (col - 1, fil)]
    else:  # mesma_coluna
        ordem = [(col, fil), (col, outra)]
    livres = [(x, y) for x, y in ordem if 0 <= x < 5 and j.campo[x][y] is None]
    if not livres:
        p.log("Sem espaço para invocar.")
        return
    token = {"id": "token_" + params["invocado"].lower(), "nome": params["invocado"], "tipo": "Criatura",
             "tribo": params.get("tribo"), "ataque": params["ataque"], "vida": params["vida"],
             "custo": 0, "habilidades": [], "token": True}
    p.invocar(j, token, *livres[0])


@efeito("mover_adjacente")
def mover_adjacente(p, f, params, ctx):
    livres = _vizinhas_livres(p, f)
    if not livres or (params.get("opcional") and not p.confirmar(f.dono, "Mover?")):
        return
    p.mover(f, *p.escolher(f.dono, livres, "Mover para onde?"))
    if params.get("sem_alvo_inimigo"):
        p.aplicar_status(f, "camuflada", 1)


@efeito("mover_e_atacar")
def mover_e_atacar(p, f, params, ctx):
    """Investida: pode avançar para a frente e ataca a criatura inimiga da coluna."""
    if params.get("opcional") and not p.confirmar(f.dono, "Usar Investida?"):
        return
    col, fil = f.posicao
    if fil == "retaguarda":
        p.mover(f, col, "frente")
    alvo = p.alvo_padrao(f)
    if not hasattr(alvo, "campo"):
        p.atacar(f, alvo)


@efeito("mover_para_carta")
def mover_para_carta(p, f, params, ctx):
    """Perseguição: vai para a coluna onde uma carta foi jogada (se adjacente)."""
    col = ctx["coluna"]
    if abs(f.posicao[0] - col) != 1:
        return
    if params.get("alvo") == "inimiga" and ctx["jogador"] is f.dono:
        return
    fil = f.posicao[1]
    for destino in (fil, "retaguarda" if fil == "frente" else "frente"):
        if p.mover(f, col, destino):
            return


@efeito("mudar_de_fileira")
def mudar_de_fileira(p, f, params, ctx):
    """Medo: a carta escolhida troca de fileira (frente <-> retaguarda)."""
    cands = _inimigas(p, f)                               # temor: só em inimigas
    a = _alvo(p, f, cands, ctx, "Quem muda de fileira?")
    if a is None:
        return
    col, fil = a.posicao
    outra = "retaguarda" if fil == "frente" else "frente"
    outro = a.dono.campo[col][outra]
    if outro is None:
        p.mover(a, col, outra)
    else:  # troca de lugar
        a.dono.campo[col][fil], a.dono.campo[col][outra] = outro, a
        a.posicao, outro.posicao = (col, outra), (col, fil)


@efeito("recuar_criatura")
def recuar_criatura(p, f, params, ctx):
    """Extração: uma criatura aliada volta à mão e o feitiço ocupa seu lugar (0/2).
    Se o feitiço sobreviver à batalha, a criatura volta ao campo."""
    j = f.dono
    a = _alvo(p, f, j.criaturas(), ctx, "Quem recuar?")
    if a is None:
        return {}
    pos, original = a.posicao, a.carta
    p.devolver_para_mao(a)
    sub = p.invocar(j, f.carta, *pos)
    sub.substituto = original
    return {"fica_em_campo": True}


# ---------------------------------------------------------------- morte
@efeito("persistencia")
def persistencia(p, f, params, ctx):
    """Ao morrer, permanece em campo e volta na rodada seguinte com ataque/vida
    de params. Funciona uma única vez."""
    if f.persistencia_usada:
        return None
    f.persistencia_usada = True
    f.dano = f.vida_max
    f.inativa = True
    f.reviver_na_rodada = p.rodada + 1
    f.revive_com = (params.get("ataque", 1), params.get("vida", 1))
    p.log(f"{f.nome} persiste em campo e voltará na rodada {p.rodada + 1}.")
    return {"impedir_morte": True}

"""Motor da partida: sorteio de ordem, rolagem, movimento e compra.

Regras deste arquivo:

- Ele não conhece Flask, banco nem rede. Recebe o estado (um dicionário
  puro, que vira JSON sem tradução) e devolve o estado novo.
- Todo sorteio passa pelo `Gerador`, e o estado guarda em que ponto da
  sequência a partida está. Com a semente, a partida inteira se repete.
- Toda regra recusa em voz alta: ação fora de hora levanta `ErroDeRegra`
  com uma mensagem que pode ir direto para a tela.

Por enquanto só existem três sistemas — rolar, andar e comprar. As casas de
evento são reconhecidas e registradas no log, mas ainda não fazem nada.
"""

from __future__ import annotations

import copy

from engine.board.tabuleiro import Tabuleiro, carregar_tabuleiro
from engine.regras.balanceamento import (
    carregar_balanceamento,
    grupo_do_morro,
    multiplicador_do_morro,
)
from engine.rng.gerador import Gerador

VERSAO_DO_ESTADO = 1

FASE_SORTEIO = "sorteio_ordem"
FASE_ROLAR = "aguardando_rolagem"
FASE_COMPRA = "decidindo_compra"
FASE_FIM = "encerrada"


class ErroDeRegra(Exception):
    """Ação que a regra não permite. A mensagem vai direto ao jogador."""

    def __init__(self, mensagem: str, http: int = 400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.http = http


# --------------------------------------------------------------------------
# apoio
# --------------------------------------------------------------------------

def _reais(valor: float) -> str:
    return "R$ " + f"{int(round(valor)):,}".replace(",", ".")


def _gerador(estado: dict) -> Gerador:
    return Gerador(estado["semente"], estado.get("consumidos", 0))


def _guardar_gerador(estado: dict, gerador: Gerador) -> None:
    estado["consumidos"] = gerador.consumidos


def _log(estado: dict, tipo: str, texto: str, jogador_id: int | None = None) -> None:
    estado["log"].append({"tipo": tipo, "texto": texto, "jogador_id": jogador_id})
    # O log só serve para a tela contar o que aconteceu; manter os últimos
    # basta e evita o estado crescer sem limite dentro do banco.
    del estado["log"][:-80]


def _jogador_da_vez(estado: dict) -> dict:
    return estado["jogadores"][estado["vez"]]


def _jogador_por_id(estado: dict, jogador_id: int) -> dict:
    for j in estado["jogadores"]:
        if j["jogador_id"] == jogador_id:
            return j
    raise ErroDeRegra("Você não está nesta partida.", http=403)


def _exigir_vez(estado: dict, jogador_id: int) -> dict:
    jogador = _jogador_por_id(estado, jogador_id)
    if _jogador_da_vez(estado)["jogador_id"] != jogador_id:
        raise ErroDeRegra(f"Não é sua vez — quem joga é {_jogador_da_vez(estado)['nome']}.", http=409)
    return jogador


def _dono(estado: dict, indice: int) -> int | None:
    return (estado["propriedades"].get(str(indice)) or {}).get("dono")


# --------------------------------------------------------------------------
# aluguel
# --------------------------------------------------------------------------

def calcular_aluguel(estado: dict, tabuleiro: Tabuleiro, bal: dict, casa, dono_id: int) -> dict:
    """Quanto custa parar nesta propriedade, e de onde veio cada fator.

    A fórmula é:

        aluguel = preço × base × (1 + por_nível × nível) × morro

    Os níveis de upgrade somam sobre a base (não compõem entre si): três
    níveis a 15% dão +45%, não 1,15³. É a leitura mais fácil de explicar ao
    jogador — "20% do valor, mais 15% por nível, e o morro multiplica tudo".
    O multiplicador do Morro só vale para o grupo definido em
    `morro.grupo` do balanceamento, e conta quantas casas DAQUELE grupo o
    dono tem no total.
    """
    registro = estado["propriedades"].get(str(casa.indice)) or {}
    nivel = registro.get("nivel", 0)

    base = casa.preco * bal["aluguel"]["base"]
    fator_upgrade = 1 + bal["aluguel"]["por_nivel_de_upgrade"] * nivel

    fator_morro = 1.0
    becos = 0
    if casa.grupo == grupo_do_morro(bal):
        becos = sum(
            1
            for indice, dados in estado["propriedades"].items()
            if dados.get("dono") == dono_id
            and tabuleiro.casa(int(indice)).grupo == casa.grupo
        )
        fator_morro = multiplicador_do_morro(bal, becos)

    return {
        "valor": int(round(base * fator_upgrade * fator_morro)),
        "base": int(round(base)),
        "nivel": nivel,
        "fator_upgrade": fator_upgrade,
        "fator_morro": fator_morro,
        "becos_do_dono": becos,
    }


def _cobrar_aluguel(estado: dict, devedor: dict, dono: dict, casa, conta: dict) -> None:
    """Transfere o aluguel. Quem não tem como pagar sai da partida."""
    valor = conta["valor"]
    detalhe = ""
    if conta["fator_morro"] > 1:
        detalhe = f" (bônus do morro {conta['fator_morro']:.1f}× com {conta['becos_do_dono']} becos)"
    elif conta["nivel"]:
        detalhe = f" (nível {conta['nivel']})"

    # A tela mostra um aviso com estes dados; o `lance` é o que permite ao
    # espectador saber que o pagamento é desta jogada e não de uma anterior.
    estado["ultimo_aluguel"] = {
        "lance": estado.get("lances", 0),
        "de": devedor["nome"],
        "de_id": devedor["jogador_id"],
        "para": dono["nome"],
        "para_id": dono["jogador_id"],
        "casa": casa.indice,
        "casa_nome": casa.nome,
        "grupo": casa.grupo,
        "valor": valor,
        "detalhe": detalhe.strip(" ()") or None,
        "faliu": False,
    }

    if devedor["caixa"] >= valor:
        devedor["caixa"] -= valor
        dono["caixa"] += valor
        _log(
            estado,
            "aluguel",
            f"{devedor['nome']} pagou {_reais(valor)} de aluguel a {dono['nome']} "
            f"por {casa.nome}{detalhe}.",
            devedor["jogador_id"],
        )
        return

    # Caixa não cobre. A especificação manda eliminar quem não consegue
    # pagar; a venda forçada de propriedades para cobrir a dívida ainda não
    # está definida (item 3 do backlog), então aqui ele entrega o que tem.
    pago = devedor["caixa"]
    devedor["caixa"] = 0
    dono["caixa"] += pago
    devedor["falido"] = True
    estado["ultimo_aluguel"]["faliu"] = True
    estado["ultimo_aluguel"]["pago"] = pago
    for indice in devedor["propriedades"]:
        estado["propriedades"].pop(str(indice), None)
    devedor["propriedades"] = []

    _log(
        estado,
        "falencia",
        f"{devedor['nome']} devia {_reais(valor)} a {dono['nome']} e só tinha {_reais(pago)}. "
        f"Faliu — os terrenos dele voltaram ao banco.",
        devedor["jogador_id"],
    )


# --------------------------------------------------------------------------
# criar
# --------------------------------------------------------------------------

def criar_partida(
    jogadores: list[dict],
    semente: int,
    tabuleiro: str = "vila_original",
    perfil: str = "padrao",
) -> dict:
    """`jogadores` vem do lobby: jogador_id, nome e personagem.

    A ordem de jogada ainda NÃO está definida aqui — a partida nasce na fase
    de sorteio, e é o dado que decide quem começa.
    """
    if len(jogadores) < 2:
        raise ErroDeRegra("Precisa de pelo menos 2 jogadores para começar.")

    bal = carregar_balanceamento(perfil)
    caixa = bal["dinheiro"]["caixa_inicial"]

    estado = {
        "versao": VERSAO_DO_ESTADO,
        "semente": int(semente),
        "consumidos": 0,
        "tabuleiro": tabuleiro,
        "perfil": perfil,
        "fase": FASE_SORTEIO,
        "rodada": 1,
        "vez": 0,
        "jogadores": [
            {
                "jogador_id": j["jogador_id"],
                "nome": j["nome"],
                "personagem": j.get("personagem"),
                "caixa": caixa,
                "posicao": 0,
                "propriedades": [],
                "falido": False,
            }
            for j in jogadores
        ],
        "propriedades": {},
        "sorteio": [],
        #: Contador de rolagens. A tela usa para saber o que já encenou.
        "lances": 0,
        "ultimo_movimento": None,
        #: Ultimo aluguel cobrado, para a tela avisar quem pagou a quem.
        "ultimo_aluguel": None,
        "compra_pendente": None,
        "log": [],
    }

    _log(estado, "inicio", f"A partida começou. Todo mundo com {_reais(caixa)} em caixa.")
    _log(estado, "sorteio", "Rolem os dados para ver quem começa.")
    return estado


# --------------------------------------------------------------------------
# 1. sorteio da ordem de jogada
# --------------------------------------------------------------------------

def _desempatar(grupo: list[dict], gerador: Gerador, faces: int, tentativa: int = 0) -> list[dict]:
    """Empate no sorteio: os empatados rolam UM dado, e só entre eles."""
    if len(grupo) == 1 or tentativa >= 5:
        return grupo

    for tirada in grupo:
        tirada["desempates"].append(gerador.dado(faces))

    por_valor: dict[int, list[dict]] = {}
    for tirada in grupo:
        por_valor.setdefault(tirada["desempates"][-1], []).append(tirada)

    saida: list[dict] = []
    for valor in sorted(por_valor, reverse=True):
        sub = por_valor[valor]
        saida.extend(sub if len(sub) == 1 else _desempatar(sub, gerador, faces, tentativa + 1))
    return saida


def sortear_ordem(estado: dict) -> dict:
    """Cada jogador rola os dados; o maior começa e o menor joga por último.

    Os do meio ficam em ordem decrescente entre eles — isto é, cada um fica
    mais perto do primeiro quanto maior tiver tirado.
    """
    if estado["fase"] != FASE_SORTEIO:
        raise ErroDeRegra("A ordem de jogada já foi sorteada.")

    estado = copy.deepcopy(estado)
    bal = carregar_balanceamento(estado["perfil"])
    quantidade = bal["dados"]["quantidade"]
    faces = bal["dados"]["faces"]
    gerador = _gerador(estado)

    tiradas = []
    for jogador in estado["jogadores"]:
        dados = gerador.dados(quantidade, faces)
        tiradas.append(
            {
                "jogador_id": jogador["jogador_id"],
                "nome": jogador["nome"],
                "dados": dados,
                "soma": sum(dados),
                "desempates": [],
            }
        )
        _log(estado, "sorteio", f"{jogador['nome']} tirou {' + '.join(map(str, dados))} = {sum(dados)}.",
             jogador["jogador_id"])

    por_soma: dict[int, list[dict]] = {}
    for tirada in tiradas:
        por_soma.setdefault(tirada["soma"], []).append(tirada)

    ordenadas: list[dict] = []
    for soma in sorted(por_soma, reverse=True):
        grupo = por_soma[soma]
        if len(grupo) > 1:
            nomes = ", ".join(t["nome"] for t in grupo)
            _log(estado, "sorteio", f"Empate em {soma} entre {nomes}. Dado extra para desempatar.")
            grupo = _desempatar(grupo, gerador, faces)
            for tirada in grupo:
                _log(estado, "sorteio",
                     f"{tirada['nome']} desempatou com {tirada['desempates'][-1]}.",
                     tirada["jogador_id"])
        ordenadas.extend(grupo)

    # A lista de jogadores passa a estar NA ORDEM DE JOGADA. Assim `vez` é
    # só um índice que anda, e nada mais precisa saber da ordem.
    por_id = {j["jogador_id"]: j for j in estado["jogadores"]}
    estado["jogadores"] = [por_id[t["jogador_id"]] for t in ordenadas]
    estado["sorteio"] = ordenadas
    estado["vez"] = 0
    estado["fase"] = FASE_ROLAR
    _guardar_gerador(estado, gerador)

    ordem = " → ".join(t["nome"] for t in ordenadas)
    _log(estado, "sorteio", f"Ordem de jogada: {ordem}.")
    _log(estado, "vez", f"É a vez de {estado['jogadores'][0]['nome']}.",
         estado["jogadores"][0]["jogador_id"])
    return estado


# --------------------------------------------------------------------------
# 2. rolar e andar
# --------------------------------------------------------------------------

def rolar(estado: dict, jogador_id: int) -> dict:
    if estado["fase"] != FASE_ROLAR:
        raise ErroDeRegra("Não dá para rolar os dados agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)

    bal = carregar_balanceamento(estado["perfil"])
    tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
    gerador = _gerador(estado)

    dados = gerador.dados(bal["dados"]["quantidade"], bal["dados"]["faces"])
    passos = sum(dados)
    _guardar_gerador(estado, gerador)

    de = jogador["posicao"]
    para = tabuleiro.avancar(de, passos)
    jogador["posicao"] = para

    # Numerar o lance é o que permite a tela de quem está ASSISTINDO saber
    # que chegou uma jogada nova e encená-la — sem isso o espectador só via
    # o peão aparecer no destino, como se teletransportasse.
    estado["lances"] = estado.get("lances", 0) + 1
    # Zera o aviso da jogada anterior: sem isso a tela repetiria o aluguel
    # antigo a cada rolagem.
    estado["ultimo_aluguel"] = None

    estado["ultimo_movimento"] = {
        "lance": estado["lances"],
        "jogador_id": jogador_id,
        "dados": dados,
        "passos": passos,
        "de": de,
        "para": para,
        "deu_a_volta": tabuleiro.passou_pelo_inicio(de, passos),
    }

    casa = tabuleiro.casa(para)
    _log(estado, "dado",
         f"{jogador['nome']} tirou {' + '.join(map(str, dados))} = {passos} e parou em {casa.nome}.",
         jogador_id)

    return _resolver_casa(estado, jogador, casa, tabuleiro)


def _resolver_casa(estado: dict, jogador: dict, casa, tabuleiro: Tabuleiro) -> dict:
    """O que acontece ao parar. Só a compra existe por enquanto."""
    if casa.e_propriedade:
        dono = _dono(estado, casa.indice)

        if dono is None:
            if jogador["caixa"] >= casa.preco:
                estado["fase"] = FASE_COMPRA
                estado["compra_pendente"] = {"casa": casa.indice, "preco": casa.preco}
                _log(estado, "compra",
                     f"{casa.nome} está à venda por {_reais(casa.preco)}.", jogador["jogador_id"])
                return estado
            _log(estado, "compra",
                 f"{casa.nome} custa {_reais(casa.preco)} e {jogador['nome']} não tem esse dinheiro.",
                 jogador["jogador_id"])

        elif dono == jogador["jogador_id"]:
            _log(estado, "info", f"{casa.nome} já é de {jogador['nome']}.", jogador["jogador_id"])

        else:
            proprietario = _jogador_por_id(estado, dono)
            bal = carregar_balanceamento(estado["perfil"])
            conta = calcular_aluguel(estado, tabuleiro, bal, casa, dono)
            _cobrar_aluguel(estado, jogador, proprietario, casa, conta)

    elif casa.tipo == "inicial":
        _log(estado, "info", f"{jogador['nome']} está no início.", jogador["jogador_id"])
    elif casa.tipo == "neutra":
        _log(estado, "info", "Nada acontece aqui.", jogador["jogador_id"])
    else:
        _log(estado, "info", f"{casa.nome} ainda não foi construída.", jogador["jogador_id"])

    return passar_turno(estado)


# --------------------------------------------------------------------------
# 3. comprar
# --------------------------------------------------------------------------

def decidir_compra(estado: dict, jogador_id: int, comprar: bool) -> dict:
    if estado["fase"] != FASE_COMPRA:
        raise ErroDeRegra("Não há nada para comprar agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)

    pendente = estado["compra_pendente"] or {}
    indice = pendente.get("casa")
    preco = pendente.get("preco", 0)
    casa = carregar_tabuleiro(estado["tabuleiro"]).casa(indice)

    if not comprar:
        _log(estado, "compra", f"{jogador['nome']} não quis {casa.nome}.", jogador_id)
    elif jogador["caixa"] < preco:
        # Caixa pode ter mudado entre a oferta e a resposta.
        raise ErroDeRegra(f"Você não tem {_reais(preco)} em caixa.")
    else:
        jogador["caixa"] -= preco
        jogador["propriedades"].append(indice)
        estado["propriedades"][str(indice)] = {"dono": jogador_id, "nivel": 0}
        _log(estado, "compra",
             f"{jogador['nome']} comprou {casa.nome} por {_reais(preco)}. "
             f"Sobrou {_reais(jogador['caixa'])}.",
             jogador_id)

    estado["compra_pendente"] = None
    return passar_turno(estado)


# --------------------------------------------------------------------------
# passagem de turno
# --------------------------------------------------------------------------

def abandonar(estado: dict, jogador_id: int) -> dict:
    """Jogador saiu no meio da partida.

    Ele é marcado como fora e as propriedades dele voltam ao banco — mesmo
    tratamento da falência. Sem isto o turno dele travava a mesa, porque a
    vez ficava esperando alguém que não está mais ali.
    """
    estado = copy.deepcopy(estado)
    jogador = _jogador_por_id(estado, jogador_id)

    if jogador["falido"]:
        return estado

    jogador["falido"] = True
    for indice in jogador["propriedades"]:
        estado["propriedades"].pop(str(indice), None)
    jogador["propriedades"] = []

    _log(estado, "saida", f"{jogador['nome']} abandonou a partida. Os terrenos voltaram ao banco.",
         jogador_id)

    era_a_vez = _jogador_da_vez(estado)["jogador_id"] == jogador_id
    if era_a_vez:
        # Se ele estava decidindo uma compra, a oferta morre junto.
        estado["compra_pendente"] = None
        return passar_turno(estado)

    return estado


def passar_turno(estado: dict) -> dict:
    vivos = [i for i, j in enumerate(estado["jogadores"]) if not j["falido"]]
    if len(vivos) <= 1:
        estado["fase"] = FASE_FIM
        if vivos:
            _log(estado, "fim", f"{estado['jogadores'][vivos[0]]['nome']} ficou de pé sozinho.")
        return estado

    inicio = estado["vez"]
    total = len(estado["jogadores"])
    proximo = (inicio + 1) % total
    while estado["jogadores"][proximo]["falido"]:
        proximo = (proximo + 1) % total

    # Voltar para alguém antes de quem acabou de jogar significa rodada nova.
    if proximo <= inicio:
        estado["rodada"] += 1
        _log(estado, "rodada", f"Rodada {estado['rodada']}.")

    estado["vez"] = proximo
    estado["fase"] = FASE_ROLAR
    _log(estado, "vez", f"É a vez de {estado['jogadores'][proximo]['nome']}.",
         estado["jogadores"][proximo]["jogador_id"])
    return estado


# --------------------------------------------------------------------------
# o que a tela recebe
# --------------------------------------------------------------------------

def estado_publico(estado: dict, jogador_id: int | None = None) -> dict:
    """Nestes três sistemas nada é secreto — todo mundo vê o mesmo tabuleiro.
    A função existe para marcar quem é 'você' e para não vazar a semente, que
    permitiria prever os dados."""
    da_vez = _jogador_da_vez(estado)
    return {
        "fase": estado["fase"],
        "rodada": estado["rodada"],
        "vez": {
            "jogador_id": da_vez["jogador_id"],
            "nome": da_vez["nome"],
            "sou_eu": da_vez["jogador_id"] == jogador_id,
        },
        "jogadores": [
            {
                "jogador_id": j["jogador_id"],
                "nome": j["nome"],
                "personagem": j["personagem"],
                "caixa": j["caixa"],
                "posicao": j["posicao"],
                "propriedades": j["propriedades"],
                "falido": j["falido"],
                "sou_eu": j["jogador_id"] == jogador_id,
            }
            for j in estado["jogadores"]
        ],
        "propriedades": estado["propriedades"],
        "sorteio": estado["sorteio"],
        "ultimo_movimento": estado["ultimo_movimento"],
        "ultimo_aluguel": estado.get("ultimo_aluguel"),
        "compra_pendente": estado["compra_pendente"],
        "log": estado["log"][-25:],
    }

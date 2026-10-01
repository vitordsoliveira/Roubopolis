"""Motor da partida: sorteio, rolagem, movimento e compra básica.

Regras deste arquivo:

- Ele não conhece Flask, banco nem rede. Recebe o estado (um dicionário
  puro, que vira JSON sem tradução) e devolve o estado novo.
- Todo sorteio passa pelo `Gerador`, e o estado guarda em que ponto da
  sequência a partida está. Com a semente, a partida inteira se repete.
- Toda regra recusa em voz alta: ação fora de hora levanta `ErroDeRegra`
  com uma mensagem que pode ir direto para a tela.

O jogador pode comprar um terreno livre onde parou; aluguel e efeitos das
casas de evento ainda não fazem parte desta etapa.
"""

from __future__ import annotations

import copy
import time

from engine.board.tabuleiro import carregar_tabuleiro
from engine.regras.balanceamento import carregar_balanceamento
from engine.rng.gerador import Gerador

#: v4: prazo autoritativo por turno, compartilhado entre todos os clientes.
VERSAO_DO_ESTADO = 4

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


def _definir_prazo(estado: dict, agora: float | None = None) -> None:
    duracao = int(estado.get("segundos_por_turno", 0))
    estado["prazo_vez"] = (agora if agora is not None else time.time()) + duracao if duracao > 0 else None


# --------------------------------------------------------------------------
# estado gravado por uma versão anterior
# --------------------------------------------------------------------------

def _atualizar(estado: dict) -> dict:
    """Traz para o formato atual um estado gravado por um motor mais velho.

    A partida mora no banco como JSON: uma mesa que começou antes de uma
    mudança aqui volta com o formato antigo. Sem esta conversão, quem
    estava decidindo uma compra quando a compra saiu do jogo ficaria preso
    para sempre numa fase que não existe mais.
    """
    versao = estado.get("versao", 1)
    if versao >= VERSAO_DO_ESTADO:
        return estado

    estado = copy.deepcopy(estado)

    estava_comprando = False
    if versao < 3:
        # v1 -> v2: o tabuleiro encolheu; posse antiga não é compatível por índice.
        estava_comprando = estado.get("fase") == "decidindo_compra"
        for chave in ("propriedades", "compra_pendente", "ultimo_aluguel"):
            estado.pop(chave, None)

        total = len(carregar_tabuleiro(estado["tabuleiro"]))
        for jogador in estado["jogadores"]:
            jogador.pop("propriedades", None)
            jogador["posicao"] %= total

        # Estados anteriores à v3 não guardavam posse compatível com o mapa atual.
        estado["propriedades"] = {}
        estado["compra_pendente"] = None

    if versao < 4:
        bal = carregar_balanceamento(estado.get("perfil", "padrao"))
        estado["segundos_por_turno"] = int(
            estado.get("segundos_por_turno", bal["tempo"]["segundos_por_turno"])
        )
        _definir_prazo(estado)

    estado["versao"] = VERSAO_DO_ESTADO
    if estava_comprando:
        # Quem decidia a compra já tinha andado: a vez segue adiante.
        estado = passar_turno(estado)
    return estado


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
    indice_inicial = carregar_tabuleiro(tabuleiro).indice_inicial

    estado = {
        "versao": VERSAO_DO_ESTADO,
        "semente": int(semente),
        "consumidos": 0,
        "tabuleiro": tabuleiro,
        "perfil": perfil,
        "segundos_por_turno": int(bal["tempo"]["segundos_por_turno"]),
        "prazo_vez": None,
        "fase": FASE_SORTEIO,
        "rodada": 1,
        "vez": 0,
        "jogadores": [
            {
                "jogador_id": j["jogador_id"],
                "nome": j["nome"],
                "personagem": j.get("personagem"),
                "caixa": caixa,
                "posicao": indice_inicial,
                "falido": False,
            }
            for j in jogadores
        ],
        "sorteio": [],
        "propriedades": {},
        "compra_pendente": None,
        #: Contador de rolagens. A tela usa para saber o que já encenou.
        "lances": 0,
        "ultimo_movimento": None,
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
    _definir_prazo(estado)

    ordem = " → ".join(t["nome"] for t in ordenadas)
    _log(estado, "sorteio", f"Ordem de jogada: {ordem}.")
    _log(estado, "vez", f"É a vez de {estado['jogadores'][0]['nome']}.",
         estado["jogadores"][0]["jogador_id"])
    return estado


# --------------------------------------------------------------------------
# 2. rolar e andar
# --------------------------------------------------------------------------

def rolar(estado: dict, jogador_id: int) -> dict:
    estado = atualizar_tempo(estado)
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

    propriedade = estado["propriedades"].get(str(para))
    if casa.tipo == "propriedade" and propriedade is None:
        if jogador["caixa"] >= casa.preco:
            estado["fase"] = FASE_COMPRA
            _definir_prazo(estado)
            estado["compra_pendente"] = {
                "casa": para,
                "preco": casa.preco,
                "jogador_id": jogador_id,
            }
            _log(estado, "compra", f"{jogador['nome']} pode comprar {casa.nome} por {_reais(casa.preco)}.", jogador_id)
            return estado
        _log(estado, "compra", f"{jogador['nome']} não tem dinheiro para comprar {casa.nome}.", jogador_id)

    # Aluguel e efeitos das outras casas ainda não fazem parte desta etapa.
    return passar_turno(estado)


def decidir_compra(estado: dict, jogador_id: int, comprar: bool) -> dict:
    """Compra ou recusa o terreno oferecido e encerra o turno atual."""
    estado = atualizar_tempo(estado)
    if estado["fase"] != FASE_COMPRA or not estado.get("compra_pendente"):
        raise ErroDeRegra("Não há uma compra para decidir agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)
    pendente = estado["compra_pendente"]
    if pendente["jogador_id"] != jogador_id:
        raise ErroDeRegra("Essa compra pertence a outro jogador.", http=403)

    if comprar:
        preco = pendente["preco"]
        if jogador["caixa"] < preco:
            raise ErroDeRegra("Você não tem dinheiro suficiente para comprar este terreno.", http=409)
        indice = str(pendente["casa"])
        if indice in estado["propriedades"]:
            raise ErroDeRegra("Este terreno já foi comprado.", http=409)
        jogador["caixa"] -= preco
        estado["propriedades"][indice] = {"dono": jogador_id, "nivel": 0}
        tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
        casa = tabuleiro.casa(pendente["casa"])
        _log(estado, "compra", f"{jogador['nome']} comprou {casa.nome} por {_reais(preco)}.", jogador_id)
    else:
        _log(estado, "compra", f"{jogador['nome']} recusou a compra.", jogador_id)

    estado["compra_pendente"] = None
    return passar_turno(estado)


# --------------------------------------------------------------------------
# passagem de turno
# --------------------------------------------------------------------------

def abandonar(estado: dict, jogador_id: int) -> dict:
    """Jogador saiu no meio da partida.

    Ele é marcado como fora e sai da roda. Sem isto o turno dele travava a
    mesa, porque a vez ficava esperando alguém que não está mais ali.
    """
    estado = copy.deepcopy(_atualizar(estado))
    jogador = _jogador_por_id(estado, jogador_id)

    if jogador["falido"]:
        return estado

    jogador["falido"] = True
    _log(estado, "saida", f"{jogador['nome']} abandonou a partida.", jogador_id)

    if _jogador_da_vez(estado)["jogador_id"] == jogador_id:
        return passar_turno(estado)
    return estado


def passar_turno(estado: dict, agora: float | None = None) -> dict:
    estado["compra_pendente"] = None
    vivos = [i for i, j in enumerate(estado["jogadores"]) if not j["falido"]]
    if len(vivos) <= 1:
        estado["fase"] = FASE_FIM
        estado["prazo_vez"] = None
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
    _definir_prazo(estado, agora)
    _log(estado, "vez", f"É a vez de {estado['jogadores'][proximo]['nome']}.",
         estado["jogadores"][proximo]["jogador_id"])
    return estado


def atualizar_tempo(estado: dict, agora: float | None = None) -> dict:
    """Aplica a ação padrão quando o prazo do turno termina."""
    estado = _atualizar(estado)
    prazo = estado.get("prazo_vez")
    if prazo is None or estado["fase"] in (FASE_SORTEIO, FASE_FIM):
        return estado

    instante = time.time() if agora is None else agora
    if instante < prazo:
        return estado

    estado = copy.deepcopy(estado)
    jogador = _jogador_da_vez(estado)
    if estado["fase"] == FASE_COMPRA and estado.get("compra_pendente"):
        _log(estado, "tempo", f"Tempo esgotado: {jogador['nome']} não comprou o terreno.", jogador["jogador_id"])
    else:
        _log(estado, "tempo", f"Tempo esgotado: a vez de {jogador['nome']} passou.", jogador["jogador_id"])

    estado["prazo_vez"] = None
    return passar_turno(estado, agora=instante)


# --------------------------------------------------------------------------
# o que a tela recebe
# --------------------------------------------------------------------------

def estado_publico(estado: dict, jogador_id: int | None = None) -> dict:
    """Nada aqui é secreto — todo mundo vê o mesmo tabuleiro. A função existe
    para marcar quem é 'você' e para não vazar a semente, que permitiria
    prever os dados."""
    estado = _atualizar(estado)
    da_vez = _jogador_da_vez(estado)
    prazo = estado.get("prazo_vez")
    restante = None if prazo is None else max(0, int(prazo - time.time() + 0.999))
    return {
        "fase": estado["fase"],
        "prazo_vez": estado.get("prazo_vez"),
        "segundos_restantes": restante,
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
                "falido": j["falido"],
                "sou_eu": j["jogador_id"] == jogador_id,
            }
            for j in estado["jogadores"]
        ],
        "sorteio": estado["sorteio"],
        "propriedades": estado.get("propriedades", {}),
        "compra_pendente": estado.get("compra_pendente"),
        "ultimo_movimento": estado["ultimo_movimento"],
        "log": estado["log"][-25:],
    }

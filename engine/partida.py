"""Motor da partida: sorteio, rolagem, movimento e compra básica.

Regras deste arquivo:

- Ele não conhece Flask, banco nem rede. Recebe o estado (um dicionário
  puro, que vira JSON sem tradução) e devolve o estado novo.
- Todo sorteio passa pelo `Gerador`, e o estado guarda em que ponto da
  sequência a partida está. Com a semente, a partida inteira se repete.
- Toda regra recusa em voz alta: ação fora de hora levanta `ErroDeRegra`
  com uma mensagem que pode ir direto para a tela.

O jogador pode comprar um terreno livre onde parou ou, ao cair numa propriedade
de outro jogador, comprá-la dele pelo preço da tabela ou pagar aluguel. Os
demais efeitos das casas de evento ainda não fazem parte desta etapa.
"""

from __future__ import annotations

import copy
import time

from engine.board.tabuleiro import carregar_tabuleiro
from engine.regras.balanceamento import carregar_balanceamento
from engine.rng.gerador import Gerador

#: v7: prazo total e encerramento por patrimônio ao fim da rodada.
VERSAO_DO_ESTADO = 7

FASE_SORTEIO = "sorteio_ordem"
FASE_ROLAR = "aguardando_rolagem"
FASE_COMPRA = "decidindo_compra"
FASE_COMPRA_JOGADOR = "decidindo_compra_jogador"
FASE_LIQUIDACAO_ALUGUEL = "liquidando_para_aluguel"
FASE_FIM = "encerrada"

TAXA_VENDA_BANCO = 35


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


def _observar_prazo_partida(estado: dict, agora: float | None = None) -> None:
    prazo = estado.get("prazo_partida")
    if prazo is None or estado.get("encerrar_apos_rodada") is not None:
        return
    instante = time.time() if agora is None else agora
    if instante >= prazo and estado["fase"] not in (FASE_SORTEIO, FASE_FIM):
        estado["encerrar_apos_rodada"] = estado["rodada"]
        _log(
            estado,
            "tempo_partida",
            f"O tempo da partida acabou. A rodada {estado['rodada']} será concluída antes do resultado.",
        )


def _patrimonio(estado: dict, jogador: dict) -> int:
    """Caixa mais valor de tabela das propriedades (upgrades ainda sem preço)."""
    tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
    valor_propriedades = sum(
        tabuleiro.casa(int(indice)).preco or 0
        for indice, propriedade in estado["propriedades"].items()
        if propriedade["dono"] == jogador["jogador_id"]
    )
    return int(jogador["caixa"] + valor_propriedades)


def _encerrar_partida(estado: dict, motivo: str) -> dict:
    ativos = [j for j in estado["jogadores"] if not j["falido"]]
    patrimonios = {str(j["jogador_id"]): _patrimonio(estado, j) for j in ativos}
    maior = max(patrimonios.values(), default=None)
    vencedores = [int(jogador_id) for jogador_id, valor in patrimonios.items() if valor == maior]
    estado["fase"] = FASE_FIM
    estado["prazo_vez"] = None
    estado["prazo_partida"] = None
    estado["encerrar_apos_rodada"] = None
    estado["motivo_fim"] = motivo
    estado["patrimonios_finais"] = patrimonios
    estado["vencedores"] = vencedores
    if motivo == "tempo":
        if len(vencedores) == 1:
            vencedor = next(j for j in ativos if j["jogador_id"] == vencedores[0])
            _log(estado, "fim", f"O tempo acabou. {vencedor['nome']} venceu com patrimônio de {_reais(maior or 0)}.", vencedor["jogador_id"])
        elif vencedores:
            nomes = ", ".join(j["nome"] for j in ativos if j["jogador_id"] in vencedores)
            _log(estado, "fim", f"O tempo acabou empatado entre {nomes}, com {_reais(maior or 0)} de patrimônio.")
        else:
            _log(estado, "fim", "O tempo acabou. Não há jogadores ativos.")
    else:
        if len(ativos) == 1:
            vencedor = ativos[0]
            vencedores = [vencedor["jogador_id"]]
            estado["vencedores"] = vencedores
            _log(estado, "fim", f"{vencedor['nome']} ficou de pé sozinho.", vencedor["jogador_id"])
        else:
            _log(estado, "fim", "A partida acabou sem jogadores ativos.")
    return estado


def _valor_aluguel(casa, propriedade: dict) -> int:
    """Aluguel base de 20%, com +15% do base por nível de upgrade."""
    nivel = max(0, int(propriedade.get("nivel", 0)))
    return int(round(casa.preco * 0.20 * (1 + 0.15 * nivel)))


def _valor_venda_banco(casa) -> int:
    """O banco compra por 35% do preço de tabela, como no leilão."""
    return (casa.preco * TAXA_VENDA_BANCO + 50) // 100


def _cobrar_aluguel(estado: dict, pagador: dict, dono: dict, casa, propriedade: dict) -> int:
    aluguel = _valor_aluguel(casa, propriedade)
    pagador["caixa"] -= aluguel
    dono["caixa"] += aluguel
    _log(
        estado,
        "aluguel",
        f"{pagador['nome']} pagou {_reais(aluguel)} de aluguel a {dono['nome']} por {casa.nome}.",
        pagador["jogador_id"],
    )
    return aluguel


def _propriedades_de(estado: dict, jogador_id: int) -> list[tuple[int, dict]]:
    return [
        (int(indice), propriedade)
        for indice, propriedade in estado["propriedades"].items()
        if propriedade["dono"] == jogador_id
    ]


def _falir(estado: dict, jogador: dict, credor: dict, divida: int) -> dict:
    """Aplica o caixa restante à dívida, devolve os imóveis ao banco e elimina."""
    pagamento_parcial = min(max(0, jogador["caixa"]), divida)
    jogador["caixa"] -= pagamento_parcial
    credor["caixa"] += pagamento_parcial
    devolvidas = [indice for indice, prop in estado["propriedades"].items() if prop["dono"] == jogador["jogador_id"]]
    for indice in devolvidas:
        del estado["propriedades"][indice]
    jogador["falido"] = True
    estado["aluguel_pendente"] = None
    estado["compra_pendente"] = None
    _log(
        estado,
        "falencia",
        f"{jogador['nome']} faliu sem conseguir pagar {_reais(divida)} de aluguel a {credor['nome']}. "
        f"Pagamento parcial: {_reais(pagamento_parcial)}; {len(devolvidas)} propriedade(s) voltou(aram) ao banco.",
        jogador["jogador_id"],
    )
    return passar_turno(estado)


def _resolver_aluguel(estado: dict, pagador: dict, dono: dict, casa, propriedade: dict) -> dict:
    """Paga o aluguel, abre liquidação ou declara falência se não há ativos."""
    aluguel = _valor_aluguel(casa, propriedade)
    if pagador["caixa"] >= aluguel:
        _cobrar_aluguel(estado, pagador, dono, casa, propriedade)
        return estado

    estado["compra_pendente"] = None
    ativos = _propriedades_de(estado, pagador["jogador_id"])
    if not ativos:
        return _falir(estado, pagador, dono, aluguel)

    estado["fase"] = FASE_LIQUIDACAO_ALUGUEL
    estado["aluguel_pendente"] = {
        "casa": casa.indice,
        "jogador_id": pagador["jogador_id"],
        "dono_id": dono["jogador_id"],
        "aluguel": aluguel,
        "divida": aluguel,
    }
    _definir_prazo(estado)
    _log(
        estado,
        "liquidacao",
        f"{pagador['nome']} precisa levantar {_reais(aluguel - max(0, pagador['caixa']))} para pagar o aluguel de {casa.nome}.",
        pagador["jogador_id"],
    )
    return estado


def _encerrar_liquidacao(estado: dict) -> dict:
    """Conclui a dívida se já há dinheiro ou declara falência sem ativos."""
    pendente = estado["aluguel_pendente"]
    pagador = _jogador_por_id(estado, pendente["jogador_id"])
    dono = _jogador_por_id(estado, pendente["dono_id"])
    if pagador["caixa"] >= pendente["divida"]:
        casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
        propriedade = estado["propriedades"].get(str(pendente["casa"]))
        if propriedade is None or propriedade["dono"] != dono["jogador_id"]:
            raise ErroDeRegra("O dono desta propriedade mudou durante a liquidação.", http=409)
        _cobrar_aluguel(estado, pagador, dono, casa, propriedade)
        estado["aluguel_pendente"] = None
        return passar_turno(estado)

    if not _propriedades_de(estado, pagador["jogador_id"]):
        return _falir(estado, pagador, dono, pendente["divida"])
    return estado


def vender_propriedade_para_aluguel(estado: dict, jogador_id: int, casa_indice: int) -> dict:
    """Vende ao banco uma propriedade escolhida para quitar aluguel pendente."""
    estado = atualizar_tempo(estado)
    if estado["fase"] != FASE_LIQUIDACAO_ALUGUEL or not estado.get("aluguel_pendente"):
        raise ErroDeRegra("Você não precisa vender propriedades agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)
    if estado["aluguel_pendente"]["jogador_id"] != jogador_id:
        raise ErroDeRegra("Essa dívida pertence a outro jogador.", http=403)
    if isinstance(casa_indice, bool) or not isinstance(casa_indice, int):
        raise ErroDeRegra("Escolha uma propriedade válida.")
    indice = str(casa_indice)
    propriedade = estado["propriedades"].get(indice)
    if propriedade is None or propriedade["dono"] != jogador_id:
        raise ErroDeRegra("Essa propriedade não é sua ou já foi vendida.", http=409)

    casa = carregar_tabuleiro(estado["tabuleiro"]).casa(casa_indice)
    if not casa.e_propriedade or casa.preco is None:
        raise ErroDeRegra("Essa casa não pode ser vendida ao banco.")

    valor = _valor_venda_banco(casa)
    jogador["caixa"] += valor
    del estado["propriedades"][indice]
    _log(estado, "venda", f"{jogador['nome']} vendeu {casa.nome} ao banco por {_reais(valor)} para pagar aluguel.", jogador_id)
    return _encerrar_liquidacao(estado)


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

    if versao < 6:
        estado.setdefault("aluguel_pendente", None)
        pendente = estado.get("compra_pendente")
        if estado.get("fase") == FASE_COMPRA_JOGADOR and pendente:
            pendente.setdefault("tipo", "jogador")
            if "aluguel" not in pendente:
                casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
                propriedade = estado.get("propriedades", {}).get(str(pendente["casa"]), {})
                pendente["aluguel"] = _valor_aluguel(casa, propriedade)

    if versao < 7:
        bal = carregar_balanceamento(estado.get("perfil", "padrao"))
        estado["minutos_de_partida"] = int(
            estado.get("minutos_de_partida", bal["tempo"].get("minutos_de_partida", 0))
        )
        ativa = estado.get("fase") not in (FASE_SORTEIO, FASE_FIM)
        if "prazo_partida" not in estado:
            duracao = estado["minutos_de_partida"] * 60
            estado["prazo_partida"] = time.time() + duracao if ativa and duracao > 0 else None
        estado.setdefault("encerrar_apos_rodada", None)
        estado.setdefault("motivo_fim", None)
        estado.setdefault("vencedores", [])
        estado.setdefault("patrimonios_finais", {})

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
        "minutos_de_partida": int(bal["tempo"].get("minutos_de_partida", 0)),
        "prazo_vez": None,
        "prazo_partida": None,
        "encerrar_apos_rodada": None,
        "motivo_fim": None,
        "vencedores": [],
        "patrimonios_finais": {},
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
        "aluguel_pendente": None,
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
    agora = time.time()
    _definir_prazo(estado, agora)
    duracao_partida = int(estado.get("minutos_de_partida", 0)) * 60
    estado["prazo_partida"] = agora + duracao_partida if duracao_partida > 0 else None

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
    elif casa.tipo == "propriedade" and propriedade["dono"] != jogador_id:
        vendedor = _jogador_por_id(estado, propriedade["dono"])
        if not vendedor["falido"] and jogador["caixa"] >= casa.preco:
            estado["fase"] = FASE_COMPRA_JOGADOR
            _definir_prazo(estado)
            estado["compra_pendente"] = {
                "tipo": "jogador",
                "casa": para,
                "preco": casa.preco,
                "aluguel": _valor_aluguel(casa, propriedade),
                "jogador_id": jogador_id,
                "vendedor_id": vendedor["jogador_id"],
            }
            _log(
                estado,
                "compra_jogador",
                f"{jogador['nome']} parou em {casa.nome}, de {vendedor['nome']}, e pode comprar por {_reais(casa.preco)}.",
                jogador_id,
            )
            return estado
        if not vendedor["falido"]:
            if jogador["caixa"] < casa.preco:
                _log(estado, "compra_jogador", f"{jogador['nome']} não tem dinheiro para comprar {casa.nome} de {vendedor['nome']}.", jogador_id)
            estado = _resolver_aluguel(estado, jogador, vendedor, casa, propriedade)

    # Aluguel de propriedade alheia é resolvido antes de passar a vez.
    if estado["fase"] == FASE_LIQUIDACAO_ALUGUEL or jogador["falido"]:
        return estado
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


def decidir_compra_jogador(estado: dict, jogador_id: int, comprar: bool) -> dict:
    """Aceita ou recusa a oferta recebida ao cair numa propriedade alheia."""
    estado = atualizar_tempo(estado)
    pendente = estado.get("compra_pendente")
    if estado["fase"] != FASE_COMPRA_JOGADOR or not pendente or pendente.get("tipo") != "jogador":
        raise ErroDeRegra("Não há uma oferta de compra de outro jogador para decidir.", http=409)

    estado = copy.deepcopy(estado)
    comprador = _exigir_vez(estado, jogador_id)
    pendente = estado["compra_pendente"]
    if pendente["jogador_id"] != jogador_id:
        raise ErroDeRegra("Essa compra pertence a outro jogador.", http=403)

    indice = str(pendente["casa"])
    propriedade = estado["propriedades"].get(indice)
    if propriedade is None or propriedade["dono"] != pendente["vendedor_id"]:
        raise ErroDeRegra("A propriedade não pertence mais ao mesmo jogador.", http=409)
    vendedor = _jogador_por_id(estado, pendente["vendedor_id"])
    if vendedor["falido"]:
        estado["compra_pendente"] = None
        _log(estado, "compra_jogador", f"A compra foi cancelada porque {vendedor['nome']} saiu da partida.", jogador_id)
        return passar_turno(estado)

    if comprar:
        preco = pendente["preco"]
        if comprador["caixa"] < preco:
            raise ErroDeRegra("Você não tem dinheiro suficiente para comprar essa propriedade.", http=409)
        comprador["caixa"] -= preco
        vendedor["caixa"] += preco
        propriedade["dono"] = jogador_id
        casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
        _log(
            estado,
            "compra_jogador",
            f"{comprador['nome']} comprou {casa.nome} de {vendedor['nome']} por {_reais(preco)}.",
            jogador_id,
        )
    else:
        casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
        _log(estado, "compra_jogador", f"{comprador['nome']} recusou comprar {casa.nome} de {vendedor['nome']}.", jogador_id)
        estado["compra_pendente"] = None
        estado = _resolver_aluguel(estado, comprador, vendedor, casa, propriedade)
        if estado["fase"] == FASE_LIQUIDACAO_ALUGUEL or estado["fase"] == FASE_FIM:
            return estado

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
    instante = time.time() if agora is None else agora
    _observar_prazo_partida(estado, instante)
    estado["compra_pendente"] = None
    estado["aluguel_pendente"] = None
    vivos = [i for i, j in enumerate(estado["jogadores"]) if not j["falido"]]
    if len(vivos) <= 1:
        return _encerrar_partida(estado, "ultimo_sobrevivente")

    inicio = estado["vez"]
    total = len(estado["jogadores"])
    proximo = (inicio + 1) % total
    while estado["jogadores"][proximo]["falido"]:
        proximo = (proximo + 1) % total

    # Voltar para alguém antes de quem acabou de jogar significa rodada nova.
    encerra_rodada = proximo <= inicio
    if encerra_rodada and estado.get("encerrar_apos_rodada") is not None:
        if estado["rodada"] >= estado["encerrar_apos_rodada"]:
            estado["vez"] = proximo
            return _encerrar_partida(estado, "tempo")

    if encerra_rodada:
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
    instante = time.time() if agora is None else agora
    prazo_partida = estado.get("prazo_partida")
    if (
        prazo_partida is not None
        and instante >= prazo_partida
        and estado.get("encerrar_apos_rodada") is None
        and estado["fase"] not in (FASE_SORTEIO, FASE_FIM)
    ):
        estado = copy.deepcopy(estado)
        _observar_prazo_partida(estado, instante)

    prazo = estado.get("prazo_vez")
    if prazo is None or estado["fase"] in (FASE_SORTEIO, FASE_FIM):
        return estado

    if instante < prazo:
        return estado

    estado = copy.deepcopy(estado)
    jogador = _jogador_da_vez(estado)
    if estado["fase"] == FASE_COMPRA and estado.get("compra_pendente"):
        _log(estado, "tempo", f"Tempo esgotado: {jogador['nome']} não comprou o terreno.", jogador["jogador_id"])
    elif estado["fase"] == FASE_COMPRA_JOGADOR and estado.get("compra_pendente"):
        pendente = estado["compra_pendente"]
        propriedade = estado["propriedades"].get(str(pendente["casa"]))
        vendedor = next((j for j in estado["jogadores"] if j["jogador_id"] == pendente["vendedor_id"]), None)
        casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
        _log(estado, "tempo", f"Tempo esgotado: {jogador['nome']} não comprou a propriedade.", jogador["jogador_id"])
        if propriedade and vendedor and propriedade["dono"] == vendedor["jogador_id"] and not vendedor["falido"]:
            estado["compra_pendente"] = None
            estado = _resolver_aluguel(estado, jogador, vendedor, casa, propriedade)
            if estado["fase"] in (FASE_LIQUIDACAO_ALUGUEL, FASE_FIM):
                return estado
    elif estado["fase"] == FASE_LIQUIDACAO_ALUGUEL and estado.get("aluguel_pendente"):
        pendente = estado["aluguel_pendente"]
        dono = _jogador_por_id(estado, pendente["dono_id"])
        estado = _falir(estado, jogador, dono, pendente["divida"])
        return estado
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
    prazo_partida = estado.get("prazo_partida")
    restante_partida = None if prazo_partida is None else max(0, int(prazo_partida - time.time() + 0.999))
    return {
        "fase": estado["fase"],
        "prazo_vez": estado.get("prazo_vez"),
        "segundos_restantes": restante,
        "prazo_partida": prazo_partida,
        "segundos_partida_restantes": restante_partida,
        "encerrar_apos_rodada": estado.get("encerrar_apos_rodada"),
        "motivo_fim": estado.get("motivo_fim"),
        "vencedores": estado.get("vencedores", []),
        "patrimonios_finais": estado.get("patrimonios_finais", {}),
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
        "aluguel_pendente": estado.get("aluguel_pendente"),
        "ultimo_movimento": estado["ultimo_movimento"],
        "log": estado["log"][-25:],
    }

"""A partida por HTTP.

Mesma abordagem do lobby: a tela consulta de tempos em tempos. Quando
`server/sockets/partida.py` existir, o formato do estado devolvido aqui não
muda — só o transporte.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.db.session import Sessao
from server.rotas.auth import token_da_requisicao
from server.salas import gerenciador as g
from server.salas import partida as p

bp = Blueprint("partida", __name__, url_prefix="/api")


def _sala_e_jogador(codigo: str):
    sessao = Sessao()
    jogador = g.exigir_jogador(sessao, token_da_requisicao())
    sala = g.buscar_sala(sessao, codigo)
    return sessao, sala, jogador


def _sim_ou_nao(campo: str):
    """Lê do corpo um booleano obrigatório; `None` quando veio outra coisa."""
    valor = (request.get_json(silent=True) or {}).get(campo)
    return valor if isinstance(valor, bool) else None


def _casa_ou_nada(obrigatoria: bool):
    """`casa` do corpo: índice inteiro, ou null quando o jogador recusa.

    Devolve (valor, valido)."""
    dados = request.get_json(silent=True) or {}
    casa = dados.get("casa")
    if casa is None:
        return None, not obrigatoria
    if isinstance(casa, bool) or not isinstance(casa, int):
        return None, False
    return casa, True


@bp.get("/eventos/frases")
def frases_dos_eventos():
    """As frases de sátira das janelas de evento. Texto fixo, igual para
    todo mundo: a tela da partida busca uma vez ao abrir."""
    return jsonify(p.frases_dos_eventos()), 200


@bp.post("/salas/<codigo>/iniciar")
def iniciar(codigo: str):
    """Sai do lobby e começa a partida. Só o dono, e só com todos prontos."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    return jsonify(p.iniciar(sessao, sala, jogador)), 200


@bp.get("/partidas/<codigo>")
def estado(codigo: str):
    sessao, sala, jogador = _sala_e_jogador(codigo)
    g.marcar_visto(sessao, jogador)
    return jsonify(p.estado_para(sessao, sala, jogador)), 200


@bp.post("/partidas/<codigo>/rolar")
def rolar(codigo: str):
    sessao, sala, jogador = _sala_e_jogador(codigo)
    return jsonify(p.rolar(sessao, sala, jogador)), 200


@bp.post("/partidas/<codigo>/comprar")
def comprar(codigo: str):
    sessao, sala, jogador = _sala_e_jogador(codigo)
    comprar = _sim_ou_nao("comprar")
    if comprar is None:
        return jsonify({"erro": "Informe se deseja comprar o terreno."}), 400
    return jsonify(p.decidir_compra(sessao, sala, jogador, comprar)), 200


@bp.post("/partidas/<codigo>/comprar-propriedade")
def comprar_propriedade(codigo: str):
    """Aceita ou recusa a oferta recebida ao cair numa propriedade alheia."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    comprar = _sim_ou_nao("comprar")
    if comprar is None:
        return jsonify({"erro": "Informe se deseja comprar a propriedade."}), 400
    return jsonify(p.decidir_compra_jogador(sessao, sala, jogador, comprar)), 200


@bp.post("/partidas/<codigo>/melhoria")
def melhoria(codigo: str):
    """Aceita ou recusa subir um nível na casa própria onde o jogador parou."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    melhorar = _sim_ou_nao("melhorar")
    if melhorar is None:
        return jsonify({"erro": "Informe se deseja melhorar a propriedade."}), 400
    return jsonify(p.decidir_melhoria(sessao, sala, jogador, melhorar)), 200


@bp.post("/partidas/<codigo>/vender-para-aluguel")
def vender_para_aluguel(codigo: str):
    """Vende ao banco uma propriedade escolhida para cobrir aluguel pendente."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    casa, valido = _casa_ou_nada(obrigatoria=True)
    if not valido:
        return jsonify({"erro": "Escolha uma propriedade válida para vender."}), 400
    return jsonify(p.vender_propriedade_para_aluguel(sessao, sala, jogador, casa)), 200


@bp.post("/partidas/<codigo>/coringa")
def coringa(codigo: str):
    """Arrisca ou não na Casa Coringa."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    arriscar = _sim_ou_nao("arriscar")
    if arriscar is None:
        return jsonify({"erro": "Informe se deseja arriscar."}), 400
    return jsonify(p.decidir_coringa(sessao, sala, jogador, arriscar)), 200


@bp.post("/partidas/<codigo>/reconstrucao")
def reconstrucao(codigo: str):
    """Reforma com desconto a propriedade escolhida; `casa: null` recusa."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    casa, valido = _casa_ou_nada(obrigatoria=False)
    if not valido:
        return jsonify({"erro": "Escolha uma propriedade válida para reformar."}), 400
    return jsonify(p.decidir_reconstrucao(sessao, sala, jogador, casa)), 200


@bp.post("/partidas/<codigo>/prejuizo")
def prejuizo(codigo: str):
    """Escolhe a propriedade do líder que volta ao banco."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    casa, valido = _casa_ou_nada(obrigatoria=True)
    if not valido:
        return jsonify({"erro": "Escolha uma das propriedades da lista."}), 400
    return jsonify(p.escolher_prejuizo(sessao, sala, jogador, casa)), 200


@bp.post("/partidas/<codigo>/bonus-banco")
def bonus_banco(codigo: str):
    """Vende ao banco no Bônus do banco; `casa: null` recusa a oferta."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    casa, valido = _casa_ou_nada(obrigatoria=False)
    if not valido:
        return jsonify({"erro": "Escolha uma propriedade válida para vender."}), 400
    return jsonify(p.vender_no_bonus(sessao, sala, jogador, casa)), 200


@bp.post("/partidas/<codigo>/leilao")
def leilao(codigo: str):
    """Põe uma propriedade própria em leilão, no começo da vez."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    casa, valido = _casa_ou_nada(obrigatoria=True)
    if not valido:
        return jsonify({"erro": "Escolha uma propriedade sua para leiloar."}), 400
    return jsonify(p.abrir_leilao(sessao, sala, jogador, casa)), 200


@bp.post("/partidas/<codigo>/leilao/lance")
def lance(codigo: str):
    """Um lance no leilão aberto. `valor` em reais, inteiro."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    valor = (request.get_json(silent=True) or {}).get("valor")
    if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
        return jsonify({"erro": "Informe o valor do lance."}), 400
    return jsonify(p.dar_lance(sessao, sala, jogador, valor)), 200


def _inteiro(campo: str):
    """Um inteiro obrigatório do corpo; `None` quando veio outra coisa."""
    valor = (request.get_json(silent=True) or {}).get(campo)
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


# --- modo dev: trapaças de teste, só com MODO_DEV ligado (server/config.py) ---

@bp.post("/partidas/<codigo>/dev/caixa")
def dev_caixa(codigo: str):
    sessao, sala, jogador = _sala_e_jogador(codigo)
    valor = _inteiro("valor")
    if valor is None:
        return jsonify({"erro": "Informe o valor do caixa."}), 400
    return jsonify(p.dev_definir_caixa(sessao, sala, jogador, valor)), 200


@bp.post("/partidas/<codigo>/dev/andar")
def dev_andar(codigo: str):
    sessao, sala, jogador = _sala_e_jogador(codigo)
    passos = _inteiro("passos")
    if passos is None:
        return jsonify({"erro": "Informe quantas casas andar."}), 400
    return jsonify(p.dev_andar(sessao, sala, jogador, passos)), 200


@bp.post("/partidas/<codigo>/dev/ir")
def dev_ir(codigo: str):
    sessao, sala, jogador = _sala_e_jogador(codigo)
    casa, valido = _casa_ou_nada(obrigatoria=True)
    if not valido:
        return jsonify({"erro": "Escolha uma casa do tabuleiro."}), 400
    return jsonify(p.dev_ir(sessao, sala, jogador, casa)), 200


@bp.post("/partidas/<codigo>/sair")
def sair(codigo: str):
    """Abandona a partida em andamento. Avisa os outros pelo log."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    return jsonify(p.abandonar(sessao, sala, jogador)), 200

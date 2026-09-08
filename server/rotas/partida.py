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


@bp.post("/salas/<codigo>/iniciar")
def iniciar(codigo: str):
    """Sai do lobby e começa a partida. Só o dono, e só com todos prontos."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    return jsonify(p.iniciar(sessao, sala, jogador)), 200


@bp.get("/partidas/<codigo>")
def estado(codigo: str):
    sessao, sala, jogador = _sala_e_jogador(codigo)
    return jsonify(p.estado_para(sessao, sala, jogador)), 200


@bp.post("/partidas/<codigo>/rolar")
def rolar(codigo: str):
    sessao, sala, jogador = _sala_e_jogador(codigo)
    return jsonify(p.rolar(sessao, sala, jogador)), 200


@bp.post("/partidas/<codigo>/sair")
def sair(codigo: str):
    """Abandona a partida em andamento. Avisa os outros pelo log."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    return jsonify(p.abandonar(sessao, sala, jogador)), 200


@bp.post("/partidas/<codigo>/comprar")
def comprar(codigo: str):
    """`{"comprar": true}` compra; `false` recusa. Nos dois casos o turno passa."""
    sessao, sala, jogador = _sala_e_jogador(codigo)
    corpo = request.get_json(silent=True) or {}
    return jsonify(p.decidir_compra(sessao, sala, jogador, bool(corpo.get("comprar")))), 200

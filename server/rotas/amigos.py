"""Amigos por HTTP. A regra mora em server/social/amigos.py."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.db.session import Sessao
from server.rotas.auth import token_da_requisicao
from server.salas import gerenciador as g
from server.social import amigos

bp = Blueprint("amigos", __name__, url_prefix="/api")


def _eu():
    sessao = Sessao()
    return sessao, g.exigir_jogador(sessao, token_da_requisicao())


@bp.get("/amigos")
def painel():
    sessao, jogador = _eu()
    g.marcar_visto(sessao, jogador)
    return jsonify(amigos.painel(sessao, jogador)), 200


@bp.post("/amigos")
def pedir():
    """Manda pedido de amizade pelo nome de usuário (login)."""
    sessao, jogador = _eu()
    corpo = request.get_json(silent=True) or {}
    return jsonify(amigos.pedir(sessao, jogador, str(corpo.get("login", "")))), 201


@bp.post("/amigos/<int:outro_id>/aceitar")
def aceitar(outro_id: int):
    sessao, jogador = _eu()
    return jsonify(amigos.aceitar(sessao, jogador, outro_id)), 200


@bp.delete("/amigos/<int:outro_id>")
def desfazer(outro_id: int):
    """Recusa pedido recebido, cancela pedido enviado ou desfaz a amizade."""
    sessao, jogador = _eu()
    return jsonify(amigos.desfazer(sessao, jogador, outro_id)), 200

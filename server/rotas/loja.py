"""Loja por HTTP. A regra mora em server/social/loja.py."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.db.session import Sessao
from server.rotas.auth import token_da_requisicao
from server.salas import gerenciador as g
from server.social import loja

bp = Blueprint("loja", __name__, url_prefix="/api")


def _eu():
    sessao = Sessao()
    return sessao, g.exigir_jogador(sessao, token_da_requisicao())


def _slug() -> str:
    return str((request.get_json(silent=True) or {}).get("item", ""))


@bp.get("/loja")
def vitrine():
    sessao, jogador = _eu()
    return jsonify(loja.estado_da_loja(sessao, jogador)), 200


@bp.post("/loja/comprar")
def comprar():
    sessao, jogador = _eu()
    return jsonify(loja.comprar(sessao, jogador, _slug())), 200


@bp.post("/loja/equipar")
def equipar():
    sessao, jogador = _eu()
    return jsonify(loja.equipar(sessao, jogador, _slug())), 200

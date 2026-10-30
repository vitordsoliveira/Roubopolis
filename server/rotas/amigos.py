"""Amigos e convites para sala por HTTP. A regra mora em
server/social/amigos.py e server/social/convites_de_sala.py."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.db.session import Sessao
from server.rotas.auth import token_da_requisicao
from server.salas import gerenciador as g
from server.social import amigos, convites_de_sala

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


# --- convites para sala e cartões na tela ------------------------------


@bp.get("/notificacoes")
def notificacoes():
    """Convites para sala e pedidos de amizade à espera deste jogador. O menu
    e o lobby consultam de tempos em tempos e mostram cada um num cartão."""
    sessao, jogador = _eu()
    g.marcar_visto(sessao, jogador)
    return jsonify(convites_de_sala.notificacoes(sessao, jogador)), 200


@bp.post("/salas/<codigo>/convites")
def convidar(codigo: str):
    """O dono chama um amigo para a sala."""
    sessao, jogador = _eu()
    sala = g.buscar_sala(sessao, codigo)
    amigo_id = (request.get_json(silent=True) or {}).get("amigo_id")
    if isinstance(amigo_id, bool) or not isinstance(amigo_id, int):
        return jsonify({"erro": "Escolha um amigo para convidar."}), 400
    return jsonify(convites_de_sala.convidar(sessao, sala, jogador, amigo_id)), 201


@bp.post("/convites/<int:convite_id>/aceitar")
def aceitar_convite(convite_id: int):
    """Entra na sala do convite; a resposta traz o código para a tela ir."""
    sessao, jogador = _eu()
    return jsonify(convites_de_sala.aceitar(sessao, jogador, convite_id)), 200


@bp.post("/convites/<int:convite_id>/recusar")
def recusar_convite(convite_id: int):
    sessao, jogador = _eu()
    return jsonify(convites_de_sala.recusar(sessao, jogador, convite_id)), 200

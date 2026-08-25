"""Lobby por HTTP.

Enquanto o multiplayer em tempo real não chega (server/sockets/lobby.py), a
tela consulta este endpoint de tempos em tempos. A troca para socket depois
não muda o formato do estado devolvido aqui.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from server.db.models import Personagem
from server.db.session import Sessao
from server.rotas.auth import token_da_requisicao
from server.salas import gerenciador as g

bp = Blueprint("salas", __name__, url_prefix="/api")


@bp.get("/personagens")
def listar_personagens():
    sessao = Sessao()
    personagens = sessao.scalars(
        select(Personagem).where(Personagem.ativo.is_(True)).order_by(Personagem.ordem)
    ).all()
    return jsonify([p.para_dict() for p in personagens]), 200


@bp.post("/salas")
def criar():
    """JOGAR: cria a sala e devolve o código do convite."""
    sessao = Sessao()
    token = token_da_requisicao()
    jogador = g.exigir_jogador(sessao, token)
    corpo = request.get_json(silent=True) or {}
    sala = g.criar_sala(sessao, jogador, perfil=corpo.get("perfil", "padrao"))
    return jsonify(g.estado_do_lobby(sessao, sala, token)), 201


@bp.post("/salas/<codigo>/entrar")
def entrar(codigo: str):
    sessao = Sessao()
    token = token_da_requisicao()
    jogador = g.exigir_jogador(sessao, token)
    sala = g.entrar_na_sala(sessao, codigo, jogador)
    return jsonify(g.estado_do_lobby(sessao, sala, token)), 200


@bp.get("/salas/<codigo>")
def estado(codigo: str):
    sessao = Sessao()
    token = token_da_requisicao() or request.args.get("token")
    sala = g.buscar_sala(sessao, codigo)
    return jsonify(g.estado_do_lobby(sessao, sala, token)), 200


@bp.post("/salas/<codigo>/personagem")
def escolher(codigo: str):
    sessao = Sessao()
    token = token_da_requisicao()
    jogador = g.exigir_jogador(sessao, token)
    corpo = request.get_json(silent=True) or {}
    sala = g.buscar_sala(sessao, codigo)
    sala = g.escolher_personagem(sessao, sala, jogador, corpo.get("personagem", ""))
    return jsonify(g.estado_do_lobby(sessao, sala, token)), 200


@bp.post("/salas/<codigo>/pronto")
def pronto(codigo: str):
    sessao = Sessao()
    token = token_da_requisicao()
    jogador = g.exigir_jogador(sessao, token)
    corpo = request.get_json(silent=True) or {}
    sala = g.buscar_sala(sessao, codigo)
    sala = g.alternar_pronto(sessao, sala, jogador, bool(corpo.get("pronto", True)))
    return jsonify(g.estado_do_lobby(sessao, sala, token)), 200


@bp.post("/salas/<codigo>/sair")
def sair(codigo: str):
    sessao = Sessao()
    token = token_da_requisicao()
    jogador = g.exigir_jogador(sessao, token)
    sala = g.buscar_sala(sessao, codigo)
    g.sair_da_sala(sessao, sala, jogador)
    return jsonify({"ok": True}), 200

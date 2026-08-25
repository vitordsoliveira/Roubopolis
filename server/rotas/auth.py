"""Identidade do jogador.

Não há senha nem e-mail: o token devolvido no cadastro fica no navegador e
é o que reconhece quem voltou. Perdeu o token, virou outra pessoa.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.db.session import Sessao
from server.salas.gerenciador import (
    ErroDeSala,
    autenticar_jogador,
    criar_conta,
    entrar_ou_criar_jogador,
    jogador_por_token,
)

bp = Blueprint("auth", __name__, url_prefix="/api")


def token_da_requisicao() -> str | None:
    """Aceita o token no cabeçalho ou no corpo — o cliente usa o cabeçalho."""
    cabecalho = request.headers.get("X-Jogador-Token")
    if cabecalho:
        return cabecalho.strip()
    corpo = request.get_json(silent=True) or {}
    token = corpo.get("token")
    return token.strip() if isinstance(token, str) else None


@bp.post("/jogador")
def criar_ou_atualizar():
    """Entrada do menu: manda o nome, recebe o token de volta."""
    corpo = request.get_json(silent=True) or {}
    jogador = entrar_ou_criar_jogador(Sessao(), corpo.get("nome", ""), token_da_requisicao())
    # Único lugar que devolve o token: é a credencial da pessoa.
    return jsonify({**jogador.para_dict(), "token": jogador.token}), 200


@bp.post("/auth/entrar")
def entrar():
    corpo = request.get_json(silent=True) or {}
    jogador = autenticar_jogador(Sessao(), corpo.get("login", ""), corpo.get("senha", ""))
    return jsonify({**jogador.para_dict(), "token": jogador.token}), 200


@bp.post("/auth/cadastrar")
def cadastrar():
    corpo = request.get_json(silent=True) or {}
    jogador = criar_conta(Sessao(), corpo.get("login", ""), corpo.get("senha", ""), corpo.get("nome", ""))
    return jsonify({**jogador.para_dict(), "token": jogador.token}), 201


@bp.get("/jogador")
def quem_sou_eu():
    jogador = jogador_por_token(Sessao(), token_da_requisicao())
    if jogador is None:
        raise ErroDeSala("Token desconhecido.", http=401)
    return jsonify(jogador.para_dict()), 200

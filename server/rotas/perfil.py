"""Perfil do jogador: o que ele vê sobre si e o que pode alterar."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.db.session import Sessao
from server.rotas.auth import token_da_requisicao
from server.salas.gerenciador import atualizar_perfil, exigir_jogador

bp = Blueprint("perfil", __name__, url_prefix="/api")


def _resposta(jogador) -> dict:
    """Formato único para GET e POST: a tela redesenha tudo com uma resposta."""
    return {
        "jogador": jogador.para_dict(),
        "estatisticas": {
            "partidas_jogadas": jogador.partidas_jogadas,
            "vitorias": jogador.vitorias,
            "derrotas": jogador.derrotas,
            "taxa_vitorias": jogador.taxa_vitorias,
        },
    }


@bp.get("/perfil")
def perfil():
    jogador = exigir_jogador(Sessao(), token_da_requisicao())
    return jsonify(_resposta(jogador)), 200


@bp.post("/perfil")
def salvar_perfil():
    """Altera nome, senha e/ou foto.

    Campo ausente no corpo não é tocado — mandar só `{"nome": "..."}` troca
    apenas o nome. Para tirar a foto, mande `remover_foto: true`.
    """
    sessao = Sessao()
    jogador = exigir_jogador(sessao, token_da_requisicao())
    corpo = request.get_json(silent=True) or {}

    jogador = atualizar_perfil(
        sessao,
        jogador,
        nome=corpo.get("nome"),
        senha_atual=corpo.get("senha_atual"),
        senha_nova=corpo.get("senha_nova"),
        foto=corpo.get("foto"),
        remover_foto=bool(corpo.get("remover_foto")),
    )
    return jsonify(_resposta(jogador)), 200

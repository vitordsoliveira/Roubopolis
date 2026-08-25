from __future__ import annotations

from flask import Blueprint, jsonify

from server.db.session import Sessao
from server.rotas.auth import token_da_requisicao
from server.salas.gerenciador import exigir_jogador

bp = Blueprint("perfil", __name__, url_prefix="/api")


@bp.get("/perfil")
def perfil():
	jogador = exigir_jogador(Sessao(), token_da_requisicao())
	return jsonify(
		{
			"jogador": jogador.para_dict(),
			"estatisticas": {
				"partidas_jogadas": jogador.partidas_jogadas,
				"vitorias": jogador.vitorias,
				"derrotas": jogador.derrotas,
			},
		}
	), 200

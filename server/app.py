"""Flask do Roubodopolis.

Serve os arquivos de `client/` e a API do menu e do lobby. Os canais de
tempo real (server/sockets/) entram na fase de multiplayer; até lá a tela
do lobby consulta a API por conta própria.
"""

from __future__ import annotations

from flask import Flask, jsonify, send_from_directory
from sqlalchemy.exc import OperationalError

from server.config import Config
from server.db.session import Sessao
from server.rotas.auth import bp as bp_auth
from server.rotas.salas import bp as bp_salas
from server.salas.gerenciador import ErroDeSala


def criar_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["JSON_SORT_KEYS"] = False

    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_salas)

    # ---- telas -------------------------------------------------------
    @app.get("/")
    def menu():
        return send_from_directory(Config.DIR_CLIENTE, "index.html")

    @app.get("/lobby")
    def lobby():
        return send_from_directory(Config.DIR_CLIENTE, "lobby.html")

    @app.get("/<path:caminho>")
    def estaticos(caminho: str):
        return send_from_directory(Config.DIR_CLIENTE, caminho)

    # ---- erros -------------------------------------------------------
    @app.errorhandler(ErroDeSala)
    def erro_de_sala(erro: ErroDeSala):
        return jsonify({"erro": erro.mensagem}), erro.http

    @app.errorhandler(OperationalError)
    def banco_fora(erro: OperationalError):
        app.logger.error("Banco indisponível: %s", erro)
        return jsonify({"erro": "O banco de dados não respondeu. Tente de novo."}), 503

    # ---- ciclo de vida ------------------------------------------------
    @app.teardown_appcontext
    def encerrar_sessao(_exc=None):
        # Devolve a conexão ao pool ao fim de cada request.
        Sessao.remove()

    return app

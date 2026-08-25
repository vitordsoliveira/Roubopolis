"""Ponto de entrada do servidor.

    python run.py

Antes da primeira execução, prepare o banco:

    python -m server.db.criar_banco
"""

from server.app import criar_app
from server.config import Config

app = criar_app()

if __name__ == "__main__":
    print(f"Roubodopolis em http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)

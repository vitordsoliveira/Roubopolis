"""
Antes da primeira execução, prepare o banco:

    python -m server.db.criar_banco
----------------------------------------------------------------------
Para executar o servidor, use o comando:
    python run.py

    node electron/iniciar.js --local (abre o navegador com o servidor local)
    node electron/iniciar.js --local --perfil-teste (abre o navegador com o servidor local e perfil de teste)
"""

from server.app import criar_app
from server.config import Config

app = criar_app()

if __name__ == "__main__":
    print(f"Roubodopolis em http://{Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)



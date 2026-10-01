import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# O Passenger inicia o processo com o cwd em outro lugar, então o pacote
# `server` só é importável se a raiz do projeto entrar no path na mão.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from server.app import criar_app  # noqa: E402  (precisa vir depois do sys.path)

application = criar_app()

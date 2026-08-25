"""Porta de entrada do Passenger (cPanel → Setup Python App).

O cPanel não executa `run.py`. Ele procura, na raiz do aplicativo, um
`passenger_wsgi.py` que exponha uma variável chamada `application`. É só
isso que este arquivo faz: monta o mesmo Flask que o `run.py` monta.

Diferença para o `run.py`:
    run.py            -> `app.run(...)`, servidor de desenvolvimento, sua máquina
    passenger_wsgi.py -> só expõe `application`, quem serve é o Passenger

Nunca chame `app.run()` aqui: isso prenderia o processo do Passenger.
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# O Passenger inicia o processo com o cwd em outro lugar, então o pacote
# `server` só é importável se a raiz do projeto entrar no path na mão.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from server.app import criar_app  # noqa: E402  (precisa vir depois do sys.path)

application = criar_app()

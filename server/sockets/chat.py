"""Mensagens temporarias do chat do lobby."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from threading import Lock

LIMITE_MENSAGENS = 100
LIMITE_TEXTO = 280

_mensagens: dict[str, deque[dict]] = defaultdict(lambda: deque(maxlen=LIMITE_MENSAGENS))
_trava = Lock()


def listar(codigo: str) -> list[dict]:
    with _trava:
        return list(_mensagens[codigo])


def adicionar(codigo: str, jogador_id: int, nome: str, texto: str) -> dict:
    mensagem = {
        "jogador_id": jogador_id,
        "nome": nome,
        "texto": texto,
        "enviada_em": datetime.now().isoformat(timespec="seconds"),
    }
    with _trava:
        _mensagens[codigo].append(mensagem)
    return mensagem
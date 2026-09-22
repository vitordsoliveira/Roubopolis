"""Mensagens do chat do lobby, guardadas no banco.

Não usar memória do processo aqui: em produção o Passenger sobe mais de um
processo, e cada um teria a sua própria lista de mensagens.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.db.models import MensagemChat

LIMITE_MENSAGENS = 100
LIMITE_TEXTO = 280


def listar(sessao: Session, sala_id: int) -> list[dict]:
    """As últimas mensagens da sala, da mais antiga para a mais nova."""
    recentes = sessao.scalars(
        select(MensagemChat)
        .where(MensagemChat.sala_id == sala_id)
        .order_by(MensagemChat.id.desc())
        .limit(LIMITE_MENSAGENS)
    ).all()
    return [m.para_dict() for m in reversed(recentes)]


def adicionar(sessao: Session, sala_id: int, jogador_id: int, nome: str, texto: str) -> dict:
    mensagem = MensagemChat(sala_id=sala_id, jogador_id=jogador_id, nome=nome, texto=texto)
    sessao.add(mensagem)
    sessao.commit()
    sessao.refresh(mensagem)
    return mensagem.para_dict()

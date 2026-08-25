"""Código de sala e link de convite."""

from __future__ import annotations

import secrets

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from server.config import Config
from server.db.models import Sala

# Sem I, O, 0 e 1: o código é lido em voz alta e digitado à mão.
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def gerar_codigo(tamanho: int | None = None) -> str:
    tamanho = tamanho or Config.TAMANHO_CODIGO
    return "".join(secrets.choice(ALFABETO) for _ in range(tamanho))


def normalizar_codigo(bruto: str) -> str:
    """Aceita o que a pessoa digitou: minúscula, espaço, hífen."""
    return "".join(c for c in (bruto or "").upper() if c in ALFABETO)


def gerar_codigo_livre(sessao: Session, tentativas: int = 20) -> str:
    for _ in range(tentativas):
        codigo = gerar_codigo()
        if not sessao.scalar(select(exists().where(Sala.codigo == codigo))):
            return codigo
    raise RuntimeError("Não consegui gerar um código de sala livre. Há salas antigas demais?")


def link_de_convite(codigo: str, base: str = "") -> str:
    return f"{base.rstrip('/')}/lobby?codigo={codigo}"

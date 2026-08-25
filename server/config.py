"""Configuração do servidor.

Tudo que muda entre a sua máquina e a hospedagem sai do `.env`.
Nada aqui é importado pelo `engine/` — o motor não sabe que banco existe.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]

load_dotenv(RAIZ / ".env")


class Config:
    # --- banco ---------------------------------------------------------
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

    # --- servidor ------------------------------------------------------
    SECRET_KEY: str = os.getenv("SECRET_KEY", "roubodopolis-dev-nao-use-em-producao")
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "5000"))
    DEBUG: bool = os.getenv("DEBUG", "1") == "1"

    # --- caminhos ------------------------------------------------------
    DIR_RAIZ: Path = RAIZ
    DIR_DADOS: Path = RAIZ / "data"
    DIR_CLIENTE: Path = RAIZ / "client"

    # --- regras de sala ------------------------------------------------
    MIN_JOGADORES: int = 2
    MAX_JOGADORES: int = 4
    TAMANHO_CODIGO: int = 6

    # --- regras de nome ------------------------------------------------
    NOME_MIN: int = 3
    NOME_MAX: int = 16


def exigir_database_url() -> str:
    """Devolve a DATABASE_URL ou explica exatamente o que está faltando."""
    if not Config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL não encontrada.\n"
            f"Esperado no arquivo: {RAIZ / '.env'}\n"
            "Formato: mysql+pymysql://usuario:senha@host:3306/banco\n"
            "Se a senha tiver caracteres especiais, use percent-encoding "
            "(@ vira %40, # vira %23, : vira %3A)."
        )
    return Config.DATABASE_URL

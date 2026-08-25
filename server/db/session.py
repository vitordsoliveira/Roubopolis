"""Engine e sessão do SQLAlchemy.

`create_engine` não abre conexão: ele só guarda a receita. A conexão de
verdade só acontece no primeiro `.connect()` / `.execute()`. Por isso
importar este módulo é seguro mesmo com o banco fora do ar.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, scoped_session, sessionmaker

from server.config import url_do_banco


class Base(DeclarativeBase):
    """Base declarativa de todos os models."""


_engine: Engine | None = None
_fabrica: sessionmaker[Session] | None = None


def obter_engine() -> Engine:
    """Cria a engine uma única vez e reaproveita."""
    global _engine
    if _engine is None:
        url = url_do_banco()
        opcoes: dict = {"future": True, "pool_pre_ping": True}

        if url.startswith("mysql"):
            # Hospedagem compartilhada derruba conexão ociosa sem avisar.
            # pool_recycle abaixo do timeout do servidor evita o
            # "MySQL server has gone away" na primeira ação após um tempo parado.
            opcoes["pool_recycle"] = 280
            opcoes["connect_args"] = {"connect_timeout": 10, "charset": "utf8mb4"}

        elif url.startswith("sqlite"):
            # O servidor de desenvolvimento do Flask atende em várias threads e
            # a conexão do pool circula entre elas.
            opcoes["connect_args"] = {"check_same_thread": False}

        _engine = create_engine(url, **opcoes)

        if _engine.dialect.name == "sqlite":
            # SQLite ignora chave estrangeira a menos que se peça, conexão por
            # conexão. Sem isto, o ON DELETE CASCADE do sala_jogador não vale e
            # o teste local se comporta diferente do MySQL.
            @event.listens_for(_engine, "connect")
            def _ligar_fk(conexao, _registro):
                cursor = conexao.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def obter_fabrica() -> sessionmaker[Session]:
    global _fabrica
    if _fabrica is None:
        _fabrica = sessionmaker(bind=obter_engine(), autoflush=False, expire_on_commit=False)
    return _fabrica


# Sessão por thread. O Flask chama `Sessao.remove()` ao fim de cada request.
Sessao = scoped_session(lambda: obter_fabrica()())


def descrever_alvo() -> str:
    """Onde estamos gravando — sem a senha, seguro para log."""
    from sqlalchemy.engine import make_url

    url = make_url(url_do_banco())
    if url.drivername.startswith("sqlite"):
        return f"SQLite (arquivo local) — {url.database}"
    porta = f":{url.port}" if url.port else ""
    return f"{url.username or '?'}@{url.host or 'local'}{porta}/{url.database or '?'}"

"""Modelos de banco do Roubodopolis.

Só entra aqui o que precisa sobreviver ao fim do processo:
quem é o jogador, quais personagens existem, e quais salas foram criadas.

O estado de uma partida em andamento (caixa, posição no tabuleiro, dono de
cada propriedade) NÃO mora aqui — isso é do `engine/`, vive em memória e é
o que permite rodar simulação sem banco nenhum.
"""

from __future__ import annotations

import enum
import secrets
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.db.session import Base

# InnoDB para ter chave estrangeira de verdade; utf8mb4 para acento e emoji
# no nome do jogador. Em SQLite estes argumentos são ignorados em silêncio.
ARGS_MYSQL = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


class StatusSala(str, enum.Enum):
    AGUARDANDO = "aguardando"
    EM_PARTIDA = "em_partida"
    ENCERRADA = "encerrada"
    ABANDONADA = "abandonada"


def _enum_texto(classe: type[enum.Enum], nome: str) -> Enum:
    """Grava o valor legível ('aguardando') em vez do nome ('AGUARDANDO')."""
    return Enum(classe, name=nome, values_callable=lambda e: [m.value for m in e])


def gerar_token() -> str:
    """Identidade do jogador guardada no navegador. Sem senha, sem e-mail."""
    return secrets.token_hex(24)


class Jogador(Base):
    """Uma pessoa, com credencial persistente e token de sessão.

    O token é a identidade real: é ele que reconhece quem voltou. O nome é
    apenas exibição, então dois jogadores podem se chamar igual.
    """

    __tablename__ = "jogador"
    __table_args__ = ARGS_MYSQL

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    login: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    senha_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    token: Mapped[str] = mapped_column(String(48), nullable=False, unique=True, default=gerar_token)
    partidas_jogadas: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    vitorias: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    derrotas: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    visto_em: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    participacoes: Mapped[list["SalaJogador"]] = relationship(back_populates="jogador")

    def para_dict(self) -> dict:
        """Versão pública: nunca inclui o token."""
        return {"id": self.id, "nome": self.nome}

    def __repr__(self) -> str:
        return f"<Jogador {self.id} {self.nome!r}>"


class Personagem(Base):
    """Boneco escolhível no lobby.

    As linhas nascem de `data/personagens/personagens.json` — a fonte da
    verdade é o arquivo, o banco é só a cópia que a API serve.
    """

    __tablename__ = "personagem"
    __table_args__ = ARGS_MYSQL

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    nome: Mapped[str] = mapped_column(String(40), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(180))
    # Cor de identificação do jogador: borda do cartão, painel da mesa e,
    # mais tarde, o peão no tabuleiro.
    cor: Mapped[str] = mapped_column(String(7), nullable=False, default="#ffd93d")
    sprite: Mapped[str | None] = mapped_column(String(160))
    # Passiva ainda não definida nas regras: fica nulo até existir em passivas.json.
    passiva: Mapped[str | None] = mapped_column(String(40))
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def para_dict(self) -> dict:
        return {
            "slug": self.slug,
            "nome": self.nome,
            "descricao": self.descricao,
            "cor": self.cor,
            "sprite": self.sprite,
        }

    def __repr__(self) -> str:
        return f"<Personagem {self.slug}>"


class Sala(Base):
    """Um lobby. Vira partida quando o dono manda começar."""

    __tablename__ = "sala"
    __table_args__ = ARGS_MYSQL

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(8), nullable=False, unique=True, index=True)
    dono_id: Mapped[int] = mapped_column(ForeignKey("jogador.id"), nullable=False)
    status: Mapped[StatusSala] = mapped_column(
        _enum_texto(StatusSala, "status_sala"), nullable=False, default=StatusSala.AGUARDANDO
    )
    max_jogadores: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    # Nomes de arquivo em data/balanceamento/ e data/tabuleiros/.
    perfil: Mapped[str] = mapped_column(String(20), nullable=False, default="padrao")
    tabuleiro: Mapped[str] = mapped_column(String(40), nullable=False, default="vila_original")
    # Semente do engine/rng/gerador.py: guardar isso é o que permite
    # reproduzir a partida inteira depois, quando alguém reclamar de um bug.
    seed: Mapped[int] = mapped_column(Integer, nullable=False)

    criada_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    atualizada_em: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime)
    encerrada_em: Mapped[datetime | None] = mapped_column(DateTime)

    dono: Mapped["Jogador"] = relationship(foreign_keys=[dono_id])
    participantes: Mapped[list["SalaJogador"]] = relationship(
        back_populates="sala",
        cascade="all, delete-orphan",
        order_by="SalaJogador.ordem",
    )

    @property
    def cheia(self) -> bool:
        return len(self.participantes) >= self.max_jogadores

    def para_dict(self, token_de: str | None = None) -> dict:
        """Estado do lobby. `token_de` marca qual participante é 'você'."""
        return {
            "codigo": self.codigo,
            "status": self.status.value,
            "max_jogadores": self.max_jogadores,
            "perfil": self.perfil,
            "dono_id": self.dono_id,
            "cheia": self.cheia,
            "participantes": [
                p.para_dict(sou_eu=bool(token_de) and p.jogador.token == token_de)
                for p in self.participantes
            ],
        }

    def __repr__(self) -> str:
        return f"<Sala {self.codigo} {self.status.value}>"


class SalaJogador(Base):
    """Assento de um jogador numa sala."""

    __tablename__ = "sala_jogador"
    __table_args__ = (
        # Ninguém entra duas vezes na mesma sala.
        UniqueConstraint("sala_id", "jogador_id", name="uq_sala_jogador"),
        # Dois jogadores não escolhem o mesmo boneco. Em MySQL um índice
        # único aceita vários NULL, então "ninguém escolheu ainda" passa.
        UniqueConstraint("sala_id", "personagem_id", name="uq_sala_personagem"),
        ARGS_MYSQL,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sala_id: Mapped[int] = mapped_column(ForeignKey("sala.id", ondelete="CASCADE"), nullable=False)
    jogador_id: Mapped[int] = mapped_column(ForeignKey("jogador.id"), nullable=False)
    personagem_id: Mapped[int | None] = mapped_column(ForeignKey("personagem.id"))
    # Ordem de chegada = ordem de jogada na mesa.
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pronto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    entrou_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    sala: Mapped["Sala"] = relationship(back_populates="participantes")
    jogador: Mapped["Jogador"] = relationship(back_populates="participacoes")
    personagem: Mapped["Personagem | None"] = relationship()

    def para_dict(self, sou_eu: bool = False) -> dict:
        return {
            "jogador_id": self.jogador_id,
            "nome": self.jogador.nome,
            "ordem": self.ordem,
            "pronto": self.pronto,
            "dono": self.jogador_id == self.sala.dono_id,
            "sou_eu": sou_eu,
            "personagem": self.personagem.para_dict() if self.personagem else None,
        }

    def __repr__(self) -> str:
        return f"<SalaJogador sala={self.sala_id} jogador={self.jogador_id}>"


#: Ordem de criação (respeita as chaves estrangeiras).
TODOS_OS_MODELOS = (Jogador, Personagem, Sala, SalaJogador)

"""Criar sala, entrar, sair, escolher personagem.

Toda regra de lobby mora aqui. As rotas só traduzem HTTP; este módulo
trabalha com objetos do banco e levanta `ErroDeSala` quando a ação não vale.
"""

from __future__ import annotations

import random
import re
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from server.config import Config
from server.db.models import Jogador, Personagem, Sala, SalaJogador, StatusSala, gerar_token
from server.salas.convites import gerar_codigo_livre, normalizar_codigo

RE_NOME = re.compile(r"^[A-Za-z0-9À-ÿ_][A-Za-z0-9À-ÿ_ .-]*$")


class ErroDeSala(Exception):
    """Erro que o jogador precisa ler. A mensagem vai direto para a tela."""

    def __init__(self, mensagem: str, http: int = 400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.http = http


# --------------------------------------------------------------------------
# jogador
# --------------------------------------------------------------------------

def limpar_nome(bruto: str) -> str:
    nome = " ".join((bruto or "").split())
    if len(nome) < Config.NOME_MIN:
        raise ErroDeSala(f"O nome precisa de pelo menos {Config.NOME_MIN} letras.")
    if len(nome) > Config.NOME_MAX:
        raise ErroDeSala(f"O nome pode ter no máximo {Config.NOME_MAX} letras.")
    if not RE_NOME.match(nome):
        raise ErroDeSala("Use só letras, números, espaço, ponto, hífen ou _.")
    return nome


def jogador_por_token(sessao: Session, token: str | None) -> Jogador | None:
    if not token:
        return None
    return sessao.scalar(select(Jogador).where(Jogador.token == token))


def jogador_por_login(sessao: Session, login: str) -> Jogador | None:
    return sessao.scalar(select(Jogador).where(Jogador.login == login.lower()))


def limpar_login(bruto: str) -> str:
    login = (bruto or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_][a-z0-9_.-]{2,31}", login):
        raise ErroDeSala("O nome de usuário deve ter de 3 a 32 caracteres: letras, números, ponto, hífen ou _.")
    return login


def validar_senha(bruta: str) -> str:
    if not isinstance(bruta, str) or len(bruta) < 6:
        raise ErroDeSala("A senha precisa ter pelo menos 6 caracteres.")
    if len(bruta) > 128:
        raise ErroDeSala("A senha pode ter no máximo 128 caracteres.")
    return bruta


def autenticar_jogador(sessao: Session, login_bruto: str, senha: str) -> Jogador:
    login = limpar_login(login_bruto)
    jogador = jogador_por_login(sessao, login)
    if jogador is None or not jogador.senha_hash or not check_password_hash(jogador.senha_hash, senha):
        raise ErroDeSala("Usuário ou senha incorretos.", http=401)
    jogador.token = gerar_token()
    jogador.visto_em = datetime.now()
    sessao.commit()
    return jogador


def criar_conta(sessao: Session, login_bruto: str, senha: str, nome_bruto: str) -> Jogador:
    login = limpar_login(login_bruto)
    senha = validar_senha(senha)
    nome = limpar_nome(nome_bruto)
    if jogador_por_login(sessao, login) is not None:
        raise ErroDeSala("Esse usuário já existe. Escolha outro ou entre na sua conta.", http=409)
    jogador = Jogador(nome=nome, login=login, senha_hash=generate_password_hash(senha), token=gerar_token())
    sessao.add(jogador)
    try:
        sessao.commit()
    except IntegrityError:
        sessao.rollback()
        raise ErroDeSala("Esse usuário já existe. Escolha outro ou entre na sua conta.", http=409)
    return jogador


def exigir_jogador(sessao: Session, token: str | None) -> Jogador:
    jogador = jogador_por_token(sessao, token)
    if jogador is None:
        raise ErroDeSala("Não reconheci você. Volte ao menu e digite seu nome.", http=401)
    return jogador


def entrar_ou_criar_jogador(sessao: Session, nome_bruto: str, token: str | None = None) -> Jogador:
    """Cria o jogador na primeira vez; nas seguintes só atualiza o nome."""
    nome = limpar_nome(nome_bruto)
    jogador = jogador_por_token(sessao, token)
    if jogador is None:
        jogador = Jogador(nome=nome, token=gerar_token())
        sessao.add(jogador)
    else:
        jogador.nome = nome
        jogador.visto_em = datetime.now()
    sessao.commit()
    return jogador


# --------------------------------------------------------------------------
# sala
# --------------------------------------------------------------------------

def _vagas_maximas(sessao: Session) -> int:
    """Nunca mais jogadores do que bonecos: cada personagem é de um só."""
    disponiveis = sessao.scalar(
        select(func.count()).select_from(Personagem).where(Personagem.ativo.is_(True))
    ) or 0
    if disponiveis == 0:
        raise ErroDeSala(
            "Nenhum personagem cadastrado. Rode: python -m server.db.criar_banco",
            http=503,
        )
    return min(Config.MAX_JOGADORES, disponiveis)


def _personagem_livre(sessao: Session, sala: Sala | None = None) -> Personagem | None:
    """O primeiro boneco que ninguém pegou, na ordem do catálogo."""
    tomados = {p.personagem_id for p in sala.participantes if p.personagem_id} if sala else set()
    consulta = select(Personagem).where(Personagem.ativo.is_(True)).order_by(Personagem.ordem)
    if tomados:
        consulta = consulta.where(Personagem.id.not_in(tomados))
    return sessao.scalar(consulta)


def buscar_sala(sessao: Session, codigo: str) -> Sala:
    codigo = normalizar_codigo(codigo)
    sala = sessao.scalar(select(Sala).where(Sala.codigo == codigo))
    if sala is None:
        raise ErroDeSala("Sala não encontrada. Confira o código.", http=404)
    return sala


def criar_sala(sessao: Session, dono: Jogador, perfil: str = "padrao") -> Sala:
    _sair_das_salas_abertas(sessao, dono)

    sala = Sala(
        codigo=gerar_codigo_livre(sessao),
        dono_id=dono.id,
        status=StatusSala.AGUARDANDO,
        max_jogadores=_vagas_maximas(sessao),
        perfil=perfil,
        # Guardada agora para a partida ser reproduzível depois.
        seed=random.randint(1, 2_147_483_647),
    )
    sessao.add(sala)
    sessao.flush()

    # Já entra com um boneco: o lugar do jogador nunca aparece vazio, e as
    # setas do lobby servem só para trocar.
    livre = _personagem_livre(sessao)
    sessao.add(
        SalaJogador(
            sala_id=sala.id,
            jogador_id=dono.id,
            ordem=0,
            personagem_id=livre.id if livre else None,
        )
    )
    sessao.commit()
    sessao.refresh(sala)
    return sala


def entrar_na_sala(sessao: Session, codigo: str, jogador: Jogador) -> Sala:
    sala = buscar_sala(sessao, codigo)

    ja_dentro = next((p for p in sala.participantes if p.jogador_id == jogador.id), None)
    if ja_dentro is not None:
        return sala  # reconexão: entrar de novo não é erro

    if sala.status is not StatusSala.AGUARDANDO:
        raise ErroDeSala("Essa partida já começou.", http=409)
    if sala.cheia:
        raise ErroDeSala("A sala está cheia.", http=409)

    _sair_das_salas_abertas(sessao, jogador)

    proxima_ordem = max((p.ordem for p in sala.participantes), default=-1) + 1
    livre = _personagem_livre(sessao, sala)
    sessao.add(
        SalaJogador(
            sala_id=sala.id,
            jogador_id=jogador.id,
            ordem=proxima_ordem,
            personagem_id=livre.id if livre else None,
        )
    )
    sessao.commit()
    sessao.refresh(sala)
    return sala


def sair_da_sala(sessao: Session, sala: Sala, jogador: Jogador) -> None:
    assento = next((p for p in sala.participantes if p.jogador_id == jogador.id), None)
    if assento is None:
        return

    sala.participantes.remove(assento)
    sessao.flush()

    if not sala.participantes:
        sala.status = StatusSala.ABANDONADA
        sala.encerrada_em = datetime.now()
    elif sala.dono_id == jogador.id:
        # Quem chegou primeiro depois dele assume a sala.
        sala.dono_id = sala.participantes[0].jogador_id

    sessao.commit()


def _sair_das_salas_abertas(sessao: Session, jogador: Jogador) -> None:
    """Um jogador só pode estar em um lobby por vez."""
    abertas = sessao.scalars(
        select(Sala)
        .join(SalaJogador, SalaJogador.sala_id == Sala.id)
        .where(SalaJogador.jogador_id == jogador.id, Sala.status == StatusSala.AGUARDANDO)
    ).unique().all()
    for sala in abertas:
        sair_da_sala(sessao, sala, jogador)


# --------------------------------------------------------------------------
# personagem
# --------------------------------------------------------------------------

def escolher_personagem(sessao: Session, sala: Sala, jogador: Jogador, slug: str) -> Sala:
    if sala.status is not StatusSala.AGUARDANDO:
        raise ErroDeSala("A partida já começou, não dá para trocar de boneco.", http=409)

    assento = next((p for p in sala.participantes if p.jogador_id == jogador.id), None)
    if assento is None:
        raise ErroDeSala("Você não está nessa sala.", http=403)
    if assento.pronto:
        raise ErroDeSala("Tire o pronto antes de trocar de personagem.", http=409)

    personagem = sessao.scalar(
        select(Personagem).where(Personagem.slug == slug, Personagem.ativo.is_(True))
    )
    if personagem is None:
        raise ErroDeSala("Esse personagem não existe.", http=404)

    dono_atual = next(
        (p for p in sala.participantes if p.personagem_id == personagem.id and p.id != assento.id),
        None,
    )
    if dono_atual is not None:
        raise ErroDeSala(f"{personagem.nome} já é de {dono_atual.jogador.nome}.", http=409)

    assento.personagem_id = personagem.id
    # Trocar de boneco derruba o pronto: ninguém começa sem confirmar de novo.
    assento.pronto = False
    try:
        sessao.commit()
    except IntegrityError:
        # Dois cliques no mesmo boneco no mesmo instante: o banco decide.
        sessao.rollback()
        raise ErroDeSala("Alguém pegou esse personagem antes de você.", http=409)

    sessao.refresh(sala)
    return sala


def alternar_pronto(sessao: Session, sala: Sala, jogador: Jogador, pronto: bool) -> Sala:
    assento = next((p for p in sala.participantes if p.jogador_id == jogador.id), None)
    if assento is None:
        raise ErroDeSala("Você não está nessa sala.", http=403)
    if pronto and assento.personagem_id is None:
        raise ErroDeSala("Escolha um personagem antes de ficar pronto.")
    assento.pronto = pronto
    sessao.commit()
    sessao.refresh(sala)
    return sala


# --------------------------------------------------------------------------
# estado que a tela consome
# --------------------------------------------------------------------------

def estado_do_lobby(sessao: Session, sala: Sala, token: str | None = None) -> dict:
    tomados = {p.personagem_id: p.jogador.nome for p in sala.participantes if p.personagem_id}
    catalogo = sessao.scalars(
        select(Personagem).where(Personagem.ativo.is_(True)).order_by(Personagem.ordem)
    ).all()

    eu = None
    if token:
        eu = next((p for p in sala.participantes if p.jogador.token == token), None)

    personagens = []
    for personagem in catalogo:
        dono = tomados.get(personagem.id)
        personagens.append(
            {
                **personagem.para_dict(),
                "disponivel": dono is None,
                "tomado_por": dono,
                "meu": bool(eu and eu.personagem_id == personagem.id),
            }
        )

    estado = sala.para_dict(token_de=token)
    estado["personagens"] = personagens
    estado["vagas"] = sala.max_jogadores - len(sala.participantes)
    estado["disponiveis"] = sum(1 for p in personagens if p["disponivel"])
    estado["sou_dono"] = bool(eu and eu.jogador_id == sala.dono_id)
    estado["pode_iniciar"] = (
        len(sala.participantes) >= Config.MIN_JOGADORES
        and all(p.personagem_id is not None and p.pronto for p in sala.participantes)
    )
    return estado

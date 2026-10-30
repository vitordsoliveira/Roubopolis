"""Amigos: pedido, aceite e onde cada um está jogando.

A amizade é o que abre a porta da partida de outra pessoa: amigo de alguém
da mesa pode assistir (ver `pode_assistir`), mas não joga — o motor recusa
qualquer ação de quem não está entre os jogadores.

Para adicionar alguém é preciso o nome de usuário (login), que é único. O
nome no jogo não serve: dois jogadores podem se chamar igual.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from engine import partida as motor
from server.db.models import Amizade, Jogador, Partida, Sala, SalaJogador, StatusAmizade, StatusSala
from server.salas.gerenciador import ErroDeSala, jogador_por_login
from server.social.loja import resumo_visual

#: Quem foi visto há menos que isto aparece como online.
JANELA_ONLINE = timedelta(minutes=2)
#: Partida cuja vez venceu há mais que isto foi largada: ninguém mais joga.
PARTIDA_PARADA_SEGUNDOS = 10 * 60


def _par(sessao: Session, a_id: int, b_id: int) -> Amizade | None:
    return sessao.scalar(
        select(Amizade).where(
            or_(
                and_(Amizade.de_id == a_id, Amizade.para_id == b_id),
                and_(Amizade.de_id == b_id, Amizade.para_id == a_id),
            )
        )
    )


def _ids_de_amigos(sessao: Session, jogador_id: int) -> set[int]:
    linhas = sessao.scalars(
        select(Amizade).where(
            Amizade.status == StatusAmizade.ACEITA,
            or_(Amizade.de_id == jogador_id, Amizade.para_id == jogador_id),
        )
    )
    return {a.para_id if a.de_id == jogador_id else a.de_id for a in linhas}


def pode_assistir(sessao: Session, jogador_id: int, ids_da_mesa: list[int]) -> bool:
    """Espectador é amigo de pelo menos uma pessoa sentada na mesa."""
    return bool(_ids_de_amigos(sessao, jogador_id) & set(ids_da_mesa))


def online(jogador: Jogador) -> bool:
    # abs(): em desenvolvimento o SQLite grava o horário de criação em UTC e
    # o resto em hora local; sem isso, conta nova aparecia "no futuro".
    return bool(jogador.visto_em) and abs(datetime.now() - jogador.visto_em) <= JANELA_ONLINE


def _partida_viva(linha: Partida | None) -> bool:
    """A partida ainda está sendo jogada? O prazo da vez é hora do relógio do
    motor (time.time), então a conta não depende do fuso do banco."""
    if linha is None:
        return False
    estado = json.loads(linha.estado)
    if estado.get("fase") == motor.FASE_FIM:
        return False
    prazo = estado.get("prazo_vez")
    return prazo is None or time.time() - prazo < PARTIDA_PARADA_SEGUNDOS


def _onde_esta(sessao: Session, amigo: Jogador) -> dict | None:
    """A sala em que o amigo está agora: partida viva (para assistir) ou
    lobby (para entrar, se houver lugar)."""
    salas = sessao.scalars(
        select(Sala)
        .join(SalaJogador, SalaJogador.sala_id == Sala.id)
        .where(
            SalaJogador.jogador_id == amigo.id,
            Sala.status.in_([StatusSala.AGUARDANDO, StatusSala.EM_PARTIDA]),
        )
        .order_by(Sala.atualizada_em.desc(), Sala.id.desc())
    ).all()
    for sala in salas:
        if sala.status is StatusSala.EM_PARTIDA:
            linha = sessao.scalar(select(Partida).where(Partida.sala_id == sala.id))
            if _partida_viva(linha):
                return {"codigo": sala.codigo, "status": "em_partida"}
        elif online(amigo):
            return {"codigo": sala.codigo, "status": "aguardando", "cheia": sala.cheia}
    return None


def _cartao(jogador: Jogador) -> dict:
    return {"id": jogador.id, "nome": jogador.nome, "login": jogador.login, "foto": jogador.foto}


def painel(sessao: Session, jogador: Jogador) -> dict:
    """Tudo o que a tela de amigos mostra, numa resposta só."""
    pedidos = sessao.scalars(
        select(Amizade).where(or_(Amizade.de_id == jogador.id, Amizade.para_id == jogador.id))
    ).all()

    amigos, recebidos, enviados = [], [], []
    for amizade in pedidos:
        outro = amizade.para if amizade.de_id == jogador.id else amizade.de
        if amizade.status is StatusAmizade.ACEITA:
            amigos.append({
                **_cartao(outro),
                "online": online(outro),
                "sala": _onde_esta(sessao, outro),
                "visual": resumo_visual(outro),
            })
        elif amizade.para_id == jogador.id:
            recebidos.append(_cartao(outro))
        else:
            enviados.append(_cartao(outro))

    # Quem está jogando primeiro, depois quem está online, depois o resto.
    amigos.sort(key=lambda a: (a["sala"] is None, not a["online"], a["nome"].lower()))
    return {"eu": _cartao(jogador), "amigos": amigos, "recebidos": recebidos, "enviados": enviados}


def pedir(sessao: Session, jogador: Jogador, login_bruto: str) -> dict:
    login = (login_bruto or "").strip().lower()
    if not login:
        raise ErroDeSala("Digite o nome de usuário do seu amigo.")
    outro = jogador_por_login(sessao, login)
    if outro is None:
        raise ErroDeSala("Não achei ninguém com esse nome de usuário.", http=404)
    if outro.id == jogador.id:
        raise ErroDeSala("Esse é você.")

    existente = _par(sessao, jogador.id, outro.id)
    if existente is not None:
        if existente.status is StatusAmizade.ACEITA:
            raise ErroDeSala(f"Você e {outro.nome} já são amigos.", http=409)
        if existente.de_id == jogador.id:
            raise ErroDeSala(f"O pedido para {outro.nome} já foi enviado.", http=409)
        # Os dois pediram: o segundo pedido vale como aceite.
        existente.status = StatusAmizade.ACEITA
        sessao.commit()
        return painel(sessao, jogador)

    sessao.add(Amizade(de_id=jogador.id, para_id=outro.id))
    try:
        sessao.commit()
    except IntegrityError:
        sessao.rollback()
        raise ErroDeSala(f"O pedido para {outro.nome} já foi enviado.", http=409)
    return painel(sessao, jogador)


def aceitar(sessao: Session, jogador: Jogador, outro_id: int) -> dict:
    amizade = _par(sessao, jogador.id, outro_id)
    if amizade is None or amizade.status is not StatusAmizade.PENDENTE or amizade.para_id != jogador.id:
        raise ErroDeSala("Esse pedido de amizade não existe mais.", http=404)
    amizade.status = StatusAmizade.ACEITA
    sessao.commit()
    return painel(sessao, jogador)


def desfazer(sessao: Session, jogador: Jogador, outro_id: int) -> dict:
    """Recusa um pedido recebido, cancela um enviado ou desfaz a amizade."""
    amizade = _par(sessao, jogador.id, outro_id)
    if amizade is None:
        raise ErroDeSala("Vocês não têm amizade nem pedido em aberto.", http=404)
    sessao.delete(amizade)
    sessao.commit()
    return painel(sessao, jogador)

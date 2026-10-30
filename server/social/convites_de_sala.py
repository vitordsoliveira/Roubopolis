"""Convite para a sala: o dono chama um amigo, e a tela do amigo pergunta se
ele quer entrar.

O convite vale enquanto a sala espera jogadores, com lugar livre e com quem
convidou ainda nela — e no máximo por `VALIDADE`. Respondido ou vencido, a
linha some: no banco fica só o que ainda espera resposta.

O menu e o lobby perguntam por `notificacoes()` de tempos em tempos, e cada
convite ou pedido de amizade vira um cartão na tela de quem recebeu.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.db.models import ConviteSala, Jogador, Sala, StatusSala
from server.salas.gerenciador import ErroDeSala, entrar_na_sala
from server.social.amigos import pedidos_recebidos, sao_amigos

#: Depois disto o convite some da tela do amigo: quem chamou já não está
#: mais esperando por ele.
VALIDADE = timedelta(minutes=10)


def convidar(sessao: Session, sala: Sala, dono: Jogador, amigo_id: int) -> dict:
    if sala.dono_id != dono.id:
        raise ErroDeSala("Só o dono da sala convida.", http=403)
    if sala.status is not StatusSala.AGUARDANDO:
        raise ErroDeSala("A partida já começou.", http=409)
    if sala.cheia:
        raise ErroDeSala("A sala está cheia.", http=409)
    amigo = sessao.get(Jogador, amigo_id)
    if amigo is None or not sao_amigos(sessao, dono.id, amigo_id):
        raise ErroDeSala("Só dá para convidar amigos.", http=403)
    if any(p.jogador_id == amigo_id for p in sala.participantes):
        raise ErroDeSala(f"{amigo.nome} já está na sala.", http=409)

    convite = sessao.scalar(
        select(ConviteSala).where(ConviteSala.sala_id == sala.id, ConviteSala.para_id == amigo_id)
    )
    if convite is None:
        sessao.add(ConviteSala(sala_id=sala.id, de_id=dono.id, para_id=amigo_id))
    else:
        # Convidar de novo renova: o prazo recomeça e o cartão volta à tela
        # do amigo, mesmo que ele o tenha fechado.
        convite.de_id = dono.id
        convite.criado_em = datetime.now()
    try:
        sessao.commit()
    except IntegrityError:
        # Dois cliques no mesmo instante: o outro já gravou o convite.
        sessao.rollback()
    return {"convidado": amigo.nome}


def _por_que_nao_vale(convite: ConviteSala, agora: datetime) -> str | None:
    sala = convite.sala
    if agora - convite.criado_em > VALIDADE:
        return "Esse convite venceu."
    if sala.status is StatusSala.EM_PARTIDA:
        return "A partida dessa sala já começou."
    if sala.status is not StatusSala.AGUARDANDO:
        return "Essa sala fechou."
    if not any(p.jogador_id == convite.de_id for p in sala.participantes):
        return "Quem te convidou saiu da sala."
    if sala.cheia:
        return "A sala encheu."
    return None


def _cartao(convite: ConviteSala) -> dict:
    sala = convite.sala
    return {
        "id": convite.id,
        # Muda quando o convite é renovado: é o que traz de volta o cartão
        # que o amigo tinha fechado.
        "chave": f"convite-{convite.id}-{convite.criado_em:%Y%m%d%H%M%S}",
        "sala": sala.codigo,
        "de": {"id": convite.de.id, "nome": convite.de.nome, "foto": convite.de.foto},
        "jogadores": len(sala.participantes),
        "lugares": sala.max_jogadores,
    }


def convites_para(sessao: Session, jogador: Jogador) -> list[dict]:
    """Os convites que esperam resposta deste jogador, do mais antigo ao mais
    novo. Os que não valem mais saem do banco aqui mesmo, e o da sala em que
    ele já está não aparece."""
    agora = datetime.now()
    validos, vencidos = [], []
    for convite in sessao.scalars(select(ConviteSala).where(ConviteSala.para_id == jogador.id)):
        ja_dentro = any(p.jogador_id == jogador.id for p in convite.sala.participantes)
        if ja_dentro or _por_que_nao_vale(convite, agora):
            vencidos.append(convite)
        else:
            validos.append(convite)

    cartoes = [_cartao(c) for c in sorted(validos, key=lambda c: c.criado_em)]
    if vencidos:
        for convite in vencidos:
            sessao.delete(convite)
        sessao.commit()
    return cartoes


def notificacoes(sessao: Session, jogador: Jogador) -> dict:
    """O que aparece num cartão na tela do jogador: convites para sala e
    pedidos de amizade."""
    return {"convites": convites_para(sessao, jogador), "pedidos": pedidos_recebidos(sessao, jogador)}


def _do_jogador(sessao: Session, jogador: Jogador, convite_id: int) -> ConviteSala:
    convite = sessao.get(ConviteSala, convite_id)
    if convite is None or convite.para_id != jogador.id:
        raise ErroDeSala("Esse convite não existe mais.", http=404)
    return convite


def aceitar(sessao: Session, jogador: Jogador, convite_id: int) -> dict:
    """Entra na sala do convite e devolve o código dela. O convite some de
    qualquer jeito: deu certo, já serviu; não deu, não vai dar depois."""
    convite = _do_jogador(sessao, jogador, convite_id)
    motivo = _por_que_nao_vale(convite, datetime.now())
    codigo = convite.sala.codigo
    sessao.delete(convite)
    sessao.commit()
    if motivo:
        raise ErroDeSala(motivo, http=409)
    sala = entrar_na_sala(sessao, codigo, jogador)
    return {"codigo": sala.codigo}


def recusar(sessao: Session, jogador: Jogador, convite_id: int) -> dict:
    convite = _do_jogador(sessao, jogador, convite_id)
    sessao.delete(convite)
    sessao.commit()
    return {"ok": True}

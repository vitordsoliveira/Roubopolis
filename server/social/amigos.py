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
#: Quem teve a tela da sala (lobby ou partida) aberta há menos que isto
#: ainda está nela. As telas consultam a cada segundo ou dois e a presença
#: é gravada a cada 10 s (server/salas/gerenciador.py, `marcar_presenca`).
JANELA_PRESENCA = timedelta(seconds=30)
#: Partida cuja vez venceu há mais que isto foi largada: ninguém mais joga.
#: Numa partida de verdade a tela consulta o servidor a cada segundo, e a
#: consulta faz a vez andar quando o prazo vence — o prazo nunca fica dois
#: minutos para trás (a vez dura 30 segundos; o leilão, no máximo 45). Com
#: 10 minutos, quem fechava o jogo no meio da partida ainda aparecia "em
#: partida" para os amigos, com o botão de assistir.
PARTIDA_PARADA_SEGUNDOS = 2 * 60


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


def sao_amigos(sessao: Session, a_id: int, b_id: int) -> bool:
    amizade = _par(sessao, a_id, b_id)
    return amizade is not None and amizade.status is StatusAmizade.ACEITA


def online(jogador: Jogador) -> bool:
    # abs(): em desenvolvimento o SQLite grava o horário de criação em UTC e
    # o resto em hora local; sem isso, conta nova aparecia "no futuro".
    return bool(jogador.visto_em) and abs(datetime.now() - jogador.visto_em) <= JANELA_ONLINE


def _jogando_nela(linha: Partida | None, jogador_id: int, agora: float | None = None) -> bool:
    """A partida ainda está sendo jogada, e com este jogador na mesa?

    Parada há mais de `PARTIDA_PARADA_SEGUNDOS` é partida largada. Quem
    abandonou não está mais nela, mesmo com os outros jogando. O prazo da vez
    é hora do relógio do motor (time.time), então a conta não depende do fuso
    do banco."""
    if linha is None:
        return False
    estado = json.loads(linha.estado)
    if estado.get("fase") == motor.FASE_FIM:
        return False
    prazo = estado.get("prazo_vez")
    instante = time.time() if agora is None else agora
    if prazo is not None and instante - prazo >= PARTIDA_PARADA_SEGUNDOS:
        return False
    jogador = next((j for j in estado.get("jogadores", []) if j.get("jogador_id") == jogador_id), None)
    return jogador is not None and not jogador.get("abandonou")


def _presente(sala: Sala, jogador_id: int, agora: datetime | None = None) -> bool:
    """O jogador está com a tela desta sala aberta agora? Quem fechou o jogo,
    voltou ao menu ou saiu da partida para de consultar, e em segundos deixa
    de contar — sem esperar o "online" vencer."""
    assento = next((p for p in sala.participantes if p.jogador_id == jogador_id), None)
    if assento is None or assento.visto_em is None:
        return False
    instante = datetime.now() if agora is None else agora
    return abs(instante - assento.visto_em) <= JANELA_PRESENCA


def _onde_esta(sessao: Session, amigo: Jogador) -> dict | None:
    """A sala em que o amigo está agora: partida viva (para assistir) ou
    lobby (para entrar, se houver lugar). Só conta a sala cuja tela ele tem
    aberta agora (`_presente`): a que ficou para trás quando ele fechou o
    jogo ou saiu não conta."""
    if not online(amigo):
        return None
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
        if not _presente(sala, amigo.id):
            continue
        if sala.status is StatusSala.EM_PARTIDA:
            linha = sessao.scalar(select(Partida).where(Partida.sala_id == sala.id))
            if _jogando_nela(linha, amigo.id):
                return {"codigo": sala.codigo, "status": "em_partida"}
        else:
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


def pedidos_recebidos(sessao: Session, jogador: Jogador) -> list[dict]:
    """Quem pediu amizade a este jogador e ainda espera resposta: é o que
    aparece num cartão na tela dele (server/social/convites_de_sala.py)."""
    pedidos = sessao.scalars(
        select(Amizade).where(Amizade.para_id == jogador.id, Amizade.status == StatusAmizade.PENDENTE)
    ).all()
    return [_cartao(amizade.de) for amizade in pedidos]


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

"""Ponte entre o lobby (banco) e o motor (`engine/`).

Este módulo é o único lugar que conhece os dois lados. Ele lê o estado do
banco, entrega ao motor, e grava o que voltou. O motor continua sem saber
que existe banco; o banco continua sem saber que existe regra de jogo.
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from engine import partida as motor
from engine.board.tabuleiro import carregar_tabuleiro
from engine.regras.balanceamento import carregar_balanceamento
from engine.rng.gerador import gerar_semente
from server.config import Config
from server.db.models import Partida, Sala, StatusSala
from server.salas.gerenciador import ErroDeSala


def _erro(erro: motor.ErroDeRegra) -> ErroDeSala:
    """Traduz o erro do motor para o erro que as rotas já sabem devolver."""
    return ErroDeSala(erro.mensagem, http=erro.http)


def buscar_partida(sessao: Session, sala: Sala, *, bloquear: bool = False) -> Partida:
    consulta = select(Partida).where(Partida.sala_id == sala.id)
    if bloquear:
        # Serializa ações que leem e substituem o JSON completo da partida.
        consulta = consulta.with_for_update()
    linha = sessao.scalar(consulta)
    if linha is None:
        raise ErroDeSala("Esta sala ainda não começou a partida.", http=404)
    return linha


def _ler(linha: Partida) -> dict:
    return json.loads(linha.estado)


def _gravar(sessao: Session, linha: Partida, estado: dict) -> None:
    linha.estado = json.dumps(estado, ensure_ascii=False)
    sessao.commit()


def _marcar_sala_encerrada(sala: Sala, estado: dict) -> None:
    if estado["fase"] == motor.FASE_FIM:
        sala.status = StatusSala.ENCERRADA
        sala.encerrada_em = datetime.now()


def _atualizar_tempo(sessao: Session, linha: Partida) -> dict:
    original = _ler(linha)
    estado = motor.atualizar_tempo(original)
    if estado != original:
        _gravar(sessao, linha, estado)
    return estado


# --------------------------------------------------------------------------

def iniciar(sessao: Session, sala: Sala, jogador) -> dict:
    """Começa a partida. Só o dono, e só com todo mundo pronto."""
    if jogador.id != sala.dono_id:
        raise ErroDeSala("Só quem criou a sala pode começar.", http=403)

    if sala.status is StatusSala.EM_PARTIDA:
        # Clicar duas vezes não pode criar duas partidas.
        return estado_para(sessao, sala, jogador)

    if sala.status is not StatusSala.AGUARDANDO:
        raise ErroDeSala("Esta sala não está mais aguardando.", http=409)

    if len(sala.participantes) < Config.MIN_JOGADORES:
        raise ErroDeSala(f"Precisa de pelo menos {Config.MIN_JOGADORES} jogadores.")

    faltando = [p.jogador.nome for p in sala.participantes if not (p.pronto and p.personagem_id)]
    if faltando:
        raise ErroDeSala("Ainda não está todo mundo pronto: " + ", ".join(faltando))

    jogadores = [
        {
            "jogador_id": p.jogador_id,
            "nome": p.jogador.nome,
            "personagem": p.personagem.para_dict() if p.personagem else None,
            "foto": p.jogador.foto,
        }
        for p in sala.participantes
    ]

    # A semente da sala foi sorteada quando ela nasceu: guardá-la é o que
    # permite repetir a partida inteira depois.
    semente = sala.seed or gerar_semente()
    try:
        estado = motor.criar_partida(
            jogadores, semente=semente, tabuleiro=sala.tabuleiro, perfil=sala.perfil
        )
        # O sorteio da ordem acontece já: a tela mostra o resultado como
        # abertura da partida, e ninguém precisa clicar para isso.
        estado = motor.sortear_ordem(estado)
    except motor.ErroDeRegra as erro:
        raise _erro(erro)

    linha = sessao.scalar(select(Partida).where(Partida.sala_id == sala.id))
    if linha is None:
        linha = Partida(sala_id=sala.id, estado="{}")
        sessao.add(linha)

    sala.status = StatusSala.EM_PARTIDA
    _gravar(sessao, linha, estado)
    return _envelope(estado, jogador, sala)


def estado_para(sessao: Session, sala: Sala, jogador) -> dict:
    linha = buscar_partida(sessao, sala)
    estado = _atualizar_tempo(sessao, linha)
    _marcar_sala_encerrada(sala, estado)
    sessao.commit()
    return _envelope(estado, jogador, sala)


def rolar(sessao: Session, sala: Sala, jogador) -> dict:
    linha = buscar_partida(sessao, sala, bloquear=True)
    estado_atual = motor.atualizar_tempo(_ler(linha))
    try:
        estado = motor.rolar(estado_atual, jogador.id)
    except motor.ErroDeRegra as erro:
        raise _erro(erro)
    _marcar_sala_encerrada(sala, estado)
    _gravar(sessao, linha, estado)
    return _envelope(estado, jogador, sala)


def decidir_compra(sessao: Session, sala: Sala, jogador, comprar: bool) -> dict:
    linha = buscar_partida(sessao, sala, bloquear=True)
    estado_atual = motor.atualizar_tempo(_ler(linha))
    try:
        estado = motor.decidir_compra(estado_atual, jogador.id, comprar)
    except motor.ErroDeRegra as erro:
        raise _erro(erro)
    _marcar_sala_encerrada(sala, estado)
    _gravar(sessao, linha, estado)
    return _envelope(estado, jogador, sala)


def decidir_compra_jogador(sessao: Session, sala: Sala, jogador, comprar: bool) -> dict:
    """Decide a compra oferecida ao jogador ao cair numa propriedade alheia."""
    linha = buscar_partida(sessao, sala, bloquear=True)
    original = _ler(linha)
    estado_atual = motor.atualizar_tempo(original)
    if estado_atual != original:
        # Se a resposta chegou depois do prazo, persiste a resolução automática
        # (pagamento, liquidação ou falência) e devolve o estado atualizado.
        _gravar(sessao, linha, estado_atual)
        if estado_atual["fase"] != motor.FASE_COMPRA_JOGADOR:
            _marcar_sala_encerrada(sala, estado_atual)
            sessao.commit()
            return _envelope(estado_atual, jogador, sala)
    try:
        estado = motor.decidir_compra_jogador(estado_atual, jogador.id, comprar)
    except motor.ErroDeRegra as erro:
        raise _erro(erro)
    _marcar_sala_encerrada(sala, estado)
    _gravar(sessao, linha, estado)
    return _envelope(estado, jogador, sala)


def vender_propriedade_para_aluguel(
    sessao: Session, sala: Sala, jogador, casa_indice: int
) -> dict:
    linha = buscar_partida(sessao, sala, bloquear=True)
    original = _ler(linha)
    estado_atual = motor.atualizar_tempo(original)
    if estado_atual != original and estado_atual["fase"] != motor.FASE_LIQUIDACAO_ALUGUEL:
        _gravar(sessao, linha, estado_atual)
        _marcar_sala_encerrada(sala, estado_atual)
        sessao.commit()
        return _envelope(estado_atual, jogador, sala)
    try:
        estado = motor.vender_propriedade_para_aluguel(estado_atual, jogador.id, casa_indice)
    except motor.ErroDeRegra as erro:
        raise _erro(erro)
    _marcar_sala_encerrada(sala, estado)
    _gravar(sessao, linha, estado)
    return _envelope(estado, jogador, sala)


def abandonar(sessao: Session, sala: Sala, jogador) -> dict:
    """Sair no meio da partida. Os outros ficam sabendo pelo log."""
    linha = buscar_partida(sessao, sala, bloquear=True)
    try:
        estado = motor.abandonar(_ler(linha), jogador.id)
    except motor.ErroDeRegra as erro:
        raise _erro(erro)

    if estado["fase"] == motor.FASE_FIM:
        _marcar_sala_encerrada(sala, estado)

    _gravar(sessao, linha, estado)
    return _envelope(estado, jogador, sala)


# --------------------------------------------------------------------------

def _envelope(estado: dict, jogador, sala: Sala) -> dict:
    """O que a tela recebe: o estado da partida mais o que ela precisa para
    desenhar — tabuleiro e alguns números do balanceamento."""
    bal = carregar_balanceamento(estado["perfil"])
    return {
        "codigo": sala.codigo,
        "partida": motor.estado_publico(estado, jogador.id),
        "tabuleiro": carregar_tabuleiro(estado["tabuleiro"]).para_dict(),
        "regras": {
            "segundos_por_turno": bal["tempo"]["segundos_por_turno"],
            "dados": bal["dados"],
        },
    }

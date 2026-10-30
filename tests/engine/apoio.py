"""O que os testes do motor repetem: montar uma mesa e controlar o sorteio.

As posições citadas nos testes são índices de data/tabuleiros/vila_original.json.
O peão anda para índices MENORES (`avancar(de, passos) == de - passos`), então
para cair na casa `i` com dois dados de 1 basta partir de `i + 2`.
"""

from __future__ import annotations

import copy
from contextlib import contextmanager
from unittest.mock import patch

from engine import partida
from engine.regras.balanceamento import carregar_balanceamento


class GeradorFalso:
    """Faz as vezes do `Gerador`: dados fixos e sortes na ordem pedida.

    `sortes` é consumida da esquerda para a direita; a última se repete.
    O padrão (0.99) não dispara nada: nem easter egg, nem evento temático,
    nem vitória no Coringa. `escolhas` responde aos `escolher()` do portal.
    """

    def __init__(self, dados=(1, 1), sortes=(0.99,), escolhas=()):
        self.consumidos = 0
        self._dados = list(dados)
        self._sortes = list(sortes)
        self._escolhas = list(escolhas)

    def dados(self, quantidade, faces):
        return list(self._dados)

    def sorte(self):
        return self._sortes.pop(0) if len(self._sortes) > 1 else self._sortes[0]

    def inteiro(self, minimo, maximo):
        return minimo + int(self.sorte() * (maximo - minimo + 1))

    def escolher(self, itens):
        if self._escolhas:
            alvo = self._escolhas.pop(0)
            if alvo in itens:
                return alvo
        return itens[0]


def criar_estado(jogadores=2, caixa=2_000_000, posicao=4):
    """Mesa já sorteada, na vez do primeiro jogador (id 1)."""
    nomes = ["Ana", "Bia", "Caio", "Duda"]
    estado = partida.criar_partida(
        [{"jogador_id": i + 1, "nome": nomes[i]} for i in range(jogadores)],
        semente=123,
    )
    estado["fase"] = partida.FASE_ROLAR
    estado["vez"] = 0
    estado["prazo_vez"] = 4_000_000_000
    for jogador in estado["jogadores"]:
        jogador["caixa"] = caixa
    estado["jogadores"][0]["posicao"] = posicao
    return estado


@contextmanager
def sorteio(gerador):
    with patch.object(partida, "_gerador", return_value=gerador):
        yield gerador


def rolar(estado, jogador_id=1, **gerador):
    with sorteio(GeradorFalso(**gerador)):
        return partida.rolar(estado, jogador_id)


@contextmanager
def balanceamento(**mudancas):
    """O perfil padrão com algumas chaves trocadas: {"portal": {...}}."""
    perfil = copy.deepcopy(carregar_balanceamento("padrao"))
    for secao, valores in mudancas.items():
        perfil[secao] = {**perfil.get(secao, {}), **valores}
    with patch.object(partida, "carregar_balanceamento", return_value=perfil):
        yield perfil


def tipos_do_log(estado):
    return [linha["tipo"] for linha in estado["log"]]


def vez_de(estado):
    return estado["jogadores"][estado["vez"]]["jogador_id"]

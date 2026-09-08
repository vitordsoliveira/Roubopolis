"""Sorteio com semente.

Todo `random` da partida passa por aqui. O motivo é depuração: guardando a
semente, uma partida inteira pode ser repetida jogada por jogada — o que
salva a vida quando alguém disser "o dado veio errado" e for preciso
reproduzir o cenário exato.

O estado da partida guarda dois números: a `semente` e quantos sorteios já
foram consumidos. Recriar o gerador com os dois devolve exatamente o mesmo
ponto da sequência. Guardar o estado interno do `random` seria mais rápido,
mas são 625 inteiros e não cabe bem em JSON; reconsumir alguns poucos
sorteios por jogada é barato e mantém o estado legível.
"""

from __future__ import annotations

import random


class Gerador:
    """Sequência de sorteios reproduzível a partir de (semente, consumidos)."""

    def __init__(self, semente: int, consumidos: int = 0):
        self.semente = int(semente)
        self.consumidos = int(consumidos)
        self._sorteador = random.Random(self.semente)
        # Avança até o ponto em que a partida parou.
        for _ in range(self.consumidos):
            self._sorteador.random()

    # -- primitivas -----------------------------------------------------

    def sorte(self) -> float:
        """Número em [0.0, 1.0). É a única fonte: todo o resto deriva daqui,
        para que a contagem de consumidos seja confiável."""
        self.consumidos += 1
        return self._sorteador.random()

    def inteiro(self, minimo: int, maximo: int) -> int:
        """Inteiro entre `minimo` e `maximo`, ambos incluídos."""
        return minimo + int(self.sorte() * (maximo - minimo + 1))

    def escolher(self, itens):
        return itens[self.inteiro(0, len(itens) - 1)]

    # -- dados ----------------------------------------------------------

    def dado(self, faces: int = 6) -> int:
        return self.inteiro(1, faces)

    def dados(self, quantidade: int = 2, faces: int = 6) -> list[int]:
        return [self.dado(faces) for _ in range(quantidade)]


def gerar_semente() -> int:
    """Semente nova para uma partida. Cabe num INT do MySQL."""
    return random.randint(1, 2_147_483_647)

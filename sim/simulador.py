"""Simula muitas partidas com o motor de verdade para medir a economia.

    python -m sim.simulador                 # 400 partidas, 4 jogadores, 10 rodadas
    python -m sim.simulador --partidas 1000 --rodadas 15

Os bots são simples de propósito: compram tudo o que o caixa permite, e o
jogador 1 aceita a melhoria ao cair na própria casa sempre que sobra uma
reserva (os outros sempre recusam). A
pergunta que o relatório responde é se cada escolha (comprar, melhorar) dá
uma chance justa de vitória — com 4 jogadores, ~25% para cada um.

Usa `engine/partida.py` direto: o que a simulação mede é o que o jogo cobra.
Mudou `data/balanceamento/padrao.json`? Rode de novo antes de publicar.
"""

from __future__ import annotations

import argparse
import statistics
from collections import Counter, defaultdict

from engine import partida as motor
from engine.board.tabuleiro import carregar_tabuleiro

#: Caixa que o bot que melhora casas guarda antes de gastar em melhoria.
RESERVA_PARA_MELHORIA = 300_000


def jogar(semente: int, jogadores: int, rodadas: int, melhoram: set[int], compram_de_jogador: bool):
    estado = motor.criar_partida(
        [{"jogador_id": i, "nome": f"Bot {i}"} for i in range(1, jogadores + 1)], semente
    )
    estado = motor.sortear_ordem(estado)
    tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
    medidas: dict[str, int] = defaultdict(int)

    while estado["fase"] != motor.FASE_FIM and estado["rodada"] <= rodadas:
        jogador = motor._jogador_da_vez(estado)
        jid = jogador["jogador_id"]
        fase = estado["fase"]

        if fase == motor.FASE_ROLAR:
            estado = motor.rolar(estado, jid)
            medidas["salarios"] += estado["ultimo_movimento"]["deu_a_volta"]
        elif fase == motor.FASE_COMPRA:
            comprar = jogador["caixa"] >= estado["compra_pendente"]["preco"]
            medidas["compras_do_banco"] += comprar
            estado = motor.decidir_compra(estado, jid, comprar)
        elif fase == motor.FASE_COMPRA_JOGADOR:
            pendente = estado["compra_pendente"]
            comprar = compram_de_jogador and jogador["caixa"] >= pendente["preco"]
            if comprar:
                medidas["compras_de_jogador"] += 1
            else:
                medidas["alugueis_pagos"] += 1
                medidas["total_de_aluguel"] += pendente["aluguel"]
            estado = motor.decidir_compra_jogador(estado, jid, comprar)
        elif fase == motor.FASE_MELHORIA:
            custo = estado["melhoria_pendente"]["custo"]
            melhorar = jid in melhoram and jogador["caixa"] - custo >= RESERVA_PARA_MELHORIA
            medidas["melhorias"] += melhorar
            estado = motor.decidir_melhoria(estado, jid, melhorar)
        elif fase == motor.FASE_LIQUIDACAO_ALUGUEL:
            medidas["liquidacoes"] += 1
            mais_barata = min(motor._propriedades_de(estado, jid), key=lambda t: tabuleiro.casa(t[0]).preco)
            estado = motor.vender_propriedade_para_aluguel(estado, jid, mais_barata[0])
        else:
            raise RuntimeError(f"O simulador não sabe jogar a fase {fase!r}.")

    ativos = [j for j in estado["jogadores"] if not j["falido"]]
    patrimonios = {j["jogador_id"]: motor._patrimonio(estado, j) for j in ativos}
    medidas["falencias"] = len(estado["jogadores"]) - len(ativos)
    medidas["propriedades_com_dono"] = len(estado["propriedades"])
    medidas["patrimonio_medio"] = int(statistics.mean(patrimonios.values())) if patrimonios else 0
    vencedor = max(patrimonios, key=patrimonios.get) if patrimonios else None
    return medidas, vencedor


def relatorio(titulo: str, partidas: int, **opcoes) -> None:
    somas: dict[str, list[int]] = defaultdict(list)
    vitorias: Counter = Counter()
    for semente in range(partidas):
        medidas, vencedor = jogar(semente, **opcoes)
        for chave, valor in medidas.items():
            somas[chave].append(valor)
        vitorias[vencedor] += 1

    print(f"\n== {titulo} ({partidas} partidas) ==")
    for chave in sorted(somas):
        print(f"  {chave:24s} média {statistics.mean(somas[chave]):>14,.1f}")
    justo = partidas / opcoes["jogadores"]
    for jid in range(1, opcoes["jogadores"] + 1):
        marca = " (melhora casas)" if jid in opcoes["melhoram"] else ""
        print(f"  vitórias do bot {jid}{marca}: {vitorias[jid]} (justo: ~{justo:.0f})")


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--partidas", type=int, default=400)
    argumentos.add_argument("--jogadores", type=int, default=4)
    argumentos.add_argument("--rodadas", type=int, default=10)
    a = argumentos.parse_args()

    base = {"jogadores": a.jogadores, "rodadas": a.rodadas}
    relatorio("Todos só compram", a.partidas, melhoram=set(), compram_de_jogador=True, **base)
    relatorio("Bot 1 melhora casas", a.partidas, melhoram={1}, compram_de_jogador=True, **base)
    relatorio("Bot 1 melhora casas, ninguém compra de jogador", a.partidas,
              melhoram={1}, compram_de_jogador=False, **base)


if __name__ == "__main__":
    main()

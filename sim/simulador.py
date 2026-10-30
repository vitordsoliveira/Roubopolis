"""Simula muitas partidas com o motor de verdade para medir a economia.

    python -m sim.simulador                 # 400 partidas, 4 jogadores, 10 rodadas
    python -m sim.simulador --partidas 1000 --rodadas 15

Os bots são simples de propósito: compram tudo o que o caixa permite, e o
jogador 1 aceita a melhoria ao cair na própria casa sempre que sobra uma
reserva (os outros sempre recusam). Nas casas de evento, arriscam no Coringa
quando a chance é de pelo menos 50%, reformam a primeira propriedade que cabe
no caixa e, no Prejuízo, tiram a mais valiosa do líder. Quem pode leiloar e
está com pouco caixa leiloa a propriedade mais barata; os outros dão o lance
mínimo enquanto ele não passa de 80% do valor investido. A pergunta que o
relatório responde é se cada escolha (comprar, melhorar) dá uma chance justa
de vitória — com 4 jogadores, ~25% para cada um.

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
#: Abaixo deste caixa, o bot que pode leiloar leiloa; acima dele, o bot dá lance.
RESERVA_PARA_LEILAO = 250_000
#: O lance mais alto que um bot dá, em fração do valor investido da casa.
TETO_DO_LANCE = 0.80


def _lance_de_bot(estado: dict, medidas: dict[str, int]) -> dict:
    """Leilão aberto: o primeiro bot que topa cobre o lance; ninguém topando,
    o relógio corre até o fim e o leilão fecha."""
    leilao = estado["leilao"]
    minimo = motor._lance_minimo(leilao)
    lider = motor._lider_do_leilao(leilao)
    for outro in motor._vivos(estado):
        if outro["jogador_id"] in (leilao["vendedor_id"], lider and lider["jogador_id"]):
            continue
        cabe = outro["caixa"] - minimo - leilao["imposto"] >= RESERVA_PARA_LEILAO
        if cabe and minimo <= leilao["valor_investido"] * TETO_DO_LANCE:
            medidas["lances"] += 1
            return motor.dar_lance(estado, outro["jogador_id"], minimo)
    medidas["leiloes"] += 1
    medidas["leiloes_sem_lance"] += not leilao["lances"]
    return motor.atualizar_tempo(estado, agora=estado["prazo_vez"] + 1)


def decidir(
    estado: dict,
    melhoram: frozenset[int] | set[int] = frozenset(),
    compram_de_jogador: bool = True,
    medidas: dict[str, int] | None = None,
) -> dict:
    """Uma jogada do bot da vez, na fase em que a mesa estiver."""
    medidas = medidas if medidas is not None else defaultdict(int)
    tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
    jogador = motor._jogador_da_vez(estado)
    jid = jogador["jogador_id"]
    fase = estado["fase"]

    if fase == motor.FASE_ROLAR:
        if jogador["caixa"] < RESERVA_PARA_LEILAO and motor._por_que_nao_leiloa(estado, jogador) is None:
            mais_barata = min(motor._propriedades_de(estado, jid), key=lambda t: tabuleiro.casa(t[0]).preco)
            return motor.abrir_leilao(estado, jid, mais_barata[0])
        estado = motor.rolar(estado, jid)
        medidas["salarios"] += estado["ultimo_movimento"]["deu_a_volta"]
        medidas["portais"] += bool(estado["ultimo_movimento"]["portal"])
        return estado
    if fase == motor.FASE_COMPRA:
        comprar = jogador["caixa"] >= estado["compra_pendente"]["preco"]
        medidas["compras_do_banco"] += comprar
        return motor.decidir_compra(estado, jid, comprar)
    if fase == motor.FASE_COMPRA_JOGADOR:
        pendente = estado["compra_pendente"]
        comprar = compram_de_jogador and jogador["caixa"] >= pendente["preco"]
        if comprar:
            medidas["compras_de_jogador"] += 1
        else:
            medidas["alugueis_pagos"] += 1
            medidas["total_de_aluguel"] += pendente["aluguel"]
        return motor.decidir_compra_jogador(estado, jid, comprar)
    if fase == motor.FASE_MELHORIA:
        custo = estado["melhoria_pendente"]["custo"]
        melhorar = jid in melhoram and jogador["caixa"] - custo >= RESERVA_PARA_MELHORIA
        medidas["melhorias"] += melhorar
        return motor.decidir_melhoria(estado, jid, melhorar)
    if fase == motor.FASE_LIQUIDACAO_ALUGUEL:
        medidas["liquidacoes"] += 1
        mais_barata = min(motor._propriedades_de(estado, jid), key=lambda t: tabuleiro.casa(t[0]).preco)
        return motor.vender_propriedade_para_aluguel(estado, jid, mais_barata[0])
    if fase == motor.FASE_CORINGA:
        arriscar = estado["coringa_pendente"]["chance"] >= 0.5
        medidas["coringas_arriscados"] += arriscar
        return motor.decidir_coringa(estado, jid, arriscar)
    if fase == motor.FASE_RECONSTRUCAO:
        cabe = [o for o in estado["reconstrucao_pendente"]["opcoes"] if o["custo"] <= jogador["caixa"]]
        medidas["reconstrucoes"] += bool(cabe)
        return motor.decidir_reconstrucao(estado, jid, cabe[0]["casa"] if cabe else None)
    if fase == motor.FASE_PREJUIZO:
        medidas["prejuizos"] += 1
        return motor.escolher_prejuizo(estado, jid, estado["prejuizo_pendente"]["opcoes"][0]["casa"])
    if fase == motor.FASE_BONUS_BANCO:
        mais_barata = min(motor._propriedades_de(estado, jid), key=lambda t: tabuleiro.casa(t[0]).preco)
        medidas["vendas_no_bonus"] += 1
        return motor.vender_no_bonus(estado, jid, mais_barata[0])
    if fase == motor.FASE_LEILAO:
        return _lance_de_bot(estado, medidas)
    raise RuntimeError(f"O simulador não sabe jogar a fase {fase!r}.")


def jogar(semente: int, jogadores: int, rodadas: int, melhoram: set[int], compram_de_jogador: bool):
    estado = motor.criar_partida(
        [{"jogador_id": i, "nome": f"Bot {i}"} for i in range(1, jogadores + 1)], semente
    )
    estado = motor.sortear_ordem(estado)
    medidas: dict[str, int] = defaultdict(int)
    # Contado durante a partida: o log guarda só as últimas linhas.
    eventos_vistos: set[tuple[int, str]] = set()

    while estado["fase"] != motor.FASE_FIM and estado["rodada"] <= rodadas:
        estado = decidir(estado, melhoram, compram_de_jogador, medidas)
        if estado.get("evento"):
            eventos_vistos.add((estado["evento"]["rodada"], estado["evento"]["tipo"]))

    ativos = [j for j in estado["jogadores"] if not j["falido"]]
    patrimonios = {j["jogador_id"]: motor._patrimonio(estado, j) for j in ativos}
    medidas["falencias"] = len(estado["jogadores"]) - len(ativos)
    medidas["propriedades_com_dono"] = len(estado["propriedades"])
    medidas["patrimonio_medio"] = int(statistics.mean(patrimonios.values())) if patrimonios else 0
    medidas["eventos_tematicos"] = len(eventos_vistos)
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

"""Quem pode leiloar: por padrão, qualquer um com propriedade, na própria
vez, uma vez a cada 5 rodadas. O balanceamento pode limitar o leilão a quem
está abaixo de uma fração da média da mesa."""

import unittest

from engine import partida
from tests.engine import apoio

#: O limite que as regras originais traziam: só quem está abaixo de 60%.
LIMITE_DE_60 = {"so_abaixo_de_percentual_da_media": 0.60}


def motivo(estado, jogador=0):
    return partida._por_que_nao_leiloa(estado, estado["jogadores"][jogador])


def mesa(caixa_de_ana):
    """Ana (na vez) com Itaquera (140.000) e o caixa pedido; Bia com 2 milhões."""
    estado = apoio.criar_estado()
    estado["jogadores"][0]["caixa"] = caixa_de_ana
    estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}
    return estado


class QuemPodeLeiloarTestes(unittest.TestCase):
    def test_por_padrao_todo_mundo_pode(self):
        self.assertIsNone(motivo(mesa(caixa_de_ana=5_000_000)))

    def test_limite_configurado_e_sobre_a_media(self):
        # Média de (A + 2.000.000) / 2; o limite cai em A ≈ 857.143.
        with apoio.balanceamento(leilao=LIMITE_DE_60):
            self.assertIsNone(motivo(mesa(caixa_de_ana=700_000)))  # 840.000 de patrimônio
            self.assertIn("você está em 61%", motivo(mesa(caixa_de_ana=730_000)))  # 870.000

    def test_media_conta_so_quem_ainda_joga(self):
        estado = apoio.criar_estado(jogadores=3)
        estado["jogadores"][0]["caixa"] = 700_000
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}
        estado["jogadores"][2]["caixa"] = 0
        with apoio.balanceamento(leilao=LIMITE_DE_60):
            self.assertIn("abaixo de 60%", motivo(estado))  # Caio, quebrado, puxa a média para baixo

            estado["jogadores"][2]["falido"] = True
            self.assertIsNone(motivo(estado))

    def test_sem_propriedade_nao_ha_o_que_leiloar(self):
        estado = mesa(caixa_de_ana=0)
        estado["propriedades"].clear()

        self.assertIn("não tem propriedade", motivo(estado))

    def test_um_leilao_a_cada_cinco_rodadas(self):
        estado = mesa(caixa_de_ana=100_000)
        estado["jogadores"][0]["leiloou_na_rodada"] = 1
        estado["rodada"] = 2
        self.assertIn("rodada 6", motivo(estado))

        estado["rodada"] = 6
        self.assertIsNone(motivo(estado))

        with apoio.balanceamento(leilao={"rodadas_entre_leiloes": 1}):
            estado["rodada"] = 2
            self.assertIsNone(motivo(estado))

    def test_vale_no_meio_de_uma_decisao_da_vez(self):
        estado = mesa(caixa_de_ana=100_000)
        for fase in (partida.FASE_COMPRA, partida.FASE_LIQUIDACAO_ALUGUEL, partida.FASE_CORINGA):
            estado["fase"] = fase
            self.assertIsNone(motivo(estado), fase)

    def test_fora_da_vez_diz_quando_abre(self):
        estado = mesa(caixa_de_ana=100_000)
        estado["vez"] = 1

        self.assertIn("na sua vez", motivo(estado))


if __name__ == "__main__":
    unittest.main()

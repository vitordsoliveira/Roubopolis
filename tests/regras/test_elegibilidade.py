"""Quem pode leiloar: patrimônio abaixo de 60% da média de quem ainda
joga, com propriedade para vender, na própria vez e antes de rolar — e um
leilão por rodada."""

import unittest

from engine import partida
from tests.engine import apoio


def motivo(estado, jogador=0):
    return partida._por_que_nao_leiloa(estado, estado["jogadores"][jogador])


def mesa(caixa_de_ana):
    """Ana (na vez) com Itaquera (140.000) e o caixa pedido; Bia com 2 milhões."""
    estado = apoio.criar_estado()
    estado["jogadores"][0]["caixa"] = caixa_de_ana
    estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}
    return estado


class QuemPodeLeiloarTestes(unittest.TestCase):
    def test_limite_e_60_por_cento_da_media(self):
        # Média de (A + 2.000.000) / 2; o limite cai em A ≈ 857.143.
        self.assertIsNone(motivo(mesa(caixa_de_ana=700_000)))  # 840.000 de patrimônio
        self.assertIn("você está em 61%", motivo(mesa(caixa_de_ana=730_000)))  # 870.000

    def test_media_conta_so_quem_ainda_joga(self):
        estado = apoio.criar_estado(jogadores=3)
        estado["jogadores"][0]["caixa"] = 700_000
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}
        estado["jogadores"][2]["caixa"] = 0
        self.assertIn("abaixo de 60%", motivo(estado))  # Caio, quebrado, puxa a média para baixo

        estado["jogadores"][2]["falido"] = True
        self.assertIsNone(motivo(estado))

    def test_sem_propriedade_nao_ha_o_que_leiloar(self):
        estado = mesa(caixa_de_ana=0)
        estado["propriedades"].clear()

        self.assertIn("não tem propriedade", motivo(estado))

    def test_limite_nulo_libera_para_todo_mundo(self):
        with apoio.balanceamento(leilao={"so_abaixo_de_percentual_da_media": None}):
            self.assertIsNone(motivo(mesa(caixa_de_ana=2_000_000)))

    def test_intervalo_entre_leiloes_vem_do_balanceamento(self):
        estado = mesa(caixa_de_ana=100_000)
        estado["jogadores"][0]["leiloou_na_rodada"] = 1
        estado["rodada"] = 2
        self.assertIsNone(motivo(estado))

        with apoio.balanceamento(leilao={"rodadas_entre_leiloes": 3}):
            self.assertIn("rodada 4", motivo(estado))

    def test_fora_da_vez_diz_quando_abre(self):
        estado = mesa(caixa_de_ana=100_000)
        estado["vez"] = 1

        self.assertIn("na sua vez", motivo(estado))


if __name__ == "__main__":
    unittest.main()

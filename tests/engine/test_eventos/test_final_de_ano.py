import unittest

from engine import partida
from tests.engine import apoio


class FinalDeAnoTestes(unittest.TestCase):
    def test_aluguel_fica_vinte_por_cento_mais_caro_so_na_rodada(self):
        estado = apoio.criar_estado()
        casa = partida.carregar_tabuleiro("vila_original").casa(2)  # Itaquera, 140.000
        antes = partida._valor_aluguel(estado, casa, {"nivel": 0})

        partida._aplicar_evento(estado, "final_de_ano", apoio.GeradorFalso())
        durante = partida._valor_aluguel(estado, casa, {"nivel": 0})
        estado["rodada"] += 1
        depois = partida._valor_aluguel(estado, casa, {"nivel": 0})

        self.assertEqual((antes, durante, depois), (28_000, 33_600, 28_000))

    def test_aluguel_pago_na_rodada_avisa_o_acrescimo(self):
        estado = apoio.criar_estado(caixa=100_000)  # sem caixa para comprar Itaquera
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}
        partida._aplicar_evento(estado, "final_de_ano", apoio.GeradorFalso())

        estado = apoio.rolar(estado)  # Praça (4) -> Itaquera (2)

        linha = next(l for l in estado["log"] if l["tipo"] == "aluguel")
        self.assertEqual(linha["dados"]["valor"], 33_600)
        self.assertEqual(linha["dados"]["final_de_ano"], 0.2)

    def test_solta_os_presos_que_voltam_reincidentes(self):
        estado = apoio.criar_estado()
        estado["jogadores"][1]["preso"] = 1

        partida._aplicar_evento(estado, "final_de_ano", apoio.GeradorFalso())

        self.assertEqual(estado["jogadores"][1]["preso"], 0)
        self.assertTrue(estado["jogadores"][1]["reincidente"])
        self.assertFalse(estado["jogadores"][0]["reincidente"])


if __name__ == "__main__":
    unittest.main()

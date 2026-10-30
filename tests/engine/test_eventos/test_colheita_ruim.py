import unittest

from engine import partida
from tests.engine import apoio


class ColheitaRuimTestes(unittest.TestCase):
    def test_todos_perdem_dez_por_cento_do_caixa(self):
        estado = apoio.criar_estado(jogadores=3)
        estado["jogadores"][1]["caixa"] = 500_000
        estado["jogadores"][2]["falido"] = True

        partida._aplicar_evento(estado, "colheita_ruim", apoio.GeradorFalso())

        self.assertEqual([j["caixa"] for j in estado["jogadores"]], [1_800_000, 450_000, 2_000_000])
        self.assertEqual(estado["evento"]["tipo"], "colheita_ruim")
        self.assertEqual(estado["log"][-1]["tipo"], "evento_tematico")


if __name__ == "__main__":
    unittest.main()

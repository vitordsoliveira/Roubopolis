import unittest

from engine import partida
from tests.engine import apoio


class BaileNaVilaTestes(unittest.TestCase):
    def test_todos_ganham_e_conta_como_arrecadado(self):
        estado = apoio.criar_estado()

        partida._aplicar_evento(estado, "baile_na_vila", apoio.GeradorFalso())

        self.assertEqual([j["caixa"] for j in estado["jogadores"]], [2_160_000, 2_160_000])
        self.assertEqual(estado["jogadores"][0]["placar"]["arrecadado"], 160_000)


if __name__ == "__main__":
    unittest.main()

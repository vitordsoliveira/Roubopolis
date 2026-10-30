import unittest

from tests.engine import apoio


class CasaDoGanhoTestes(unittest.TestCase):
    def test_parar_no_ganho_credita_e_conta_no_placar(self):
        estado = apoio.rolar(apoio.criar_estado(posicao=38))  # 38 -> 36

        ana = estado["jogadores"][0]
        self.assertEqual(ana["posicao"], 36)
        self.assertEqual(ana["caixa"], 2_200_000)
        self.assertEqual(ana["placar"]["arrecadado"], 200_000)
        self.assertIn("ganho", apoio.tipos_do_log(estado))
        self.assertEqual(apoio.vez_de(estado), 2)


if __name__ == "__main__":
    unittest.main()

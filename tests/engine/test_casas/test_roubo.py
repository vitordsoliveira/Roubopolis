import unittest

from tests.engine import apoio


class CasaDoRouboTestes(unittest.TestCase):
    def test_parar_no_roubo_tira_o_valor_do_caixa(self):
        estado = apoio.rolar(apoio.criar_estado(posicao=23))  # 23 -> 21

        self.assertEqual(estado["jogadores"][0]["caixa"], 1_900_000)
        self.assertIn("roubo", apoio.tipos_do_log(estado))
        self.assertEqual(apoio.vez_de(estado), 2)

    def test_roubo_nunca_deixa_o_caixa_negativo(self):
        estado = apoio.rolar(apoio.criar_estado(caixa=30_000, posicao=23))

        self.assertEqual(estado["jogadores"][0]["caixa"], 0)
        self.assertFalse(estado["jogadores"][0]["falido"])


if __name__ == "__main__":
    unittest.main()

import unittest

from tests.engine import apoio


class ColetorDeImpostosTestes(unittest.TestCase):
    def test_quem_pisa_leva_o_acumulado_e_o_contador_zera(self):
        estado = apoio.criar_estado(posicao=5)  # 5 -> 4 (Início) -> 3
        estado["coletor"] = 450_000

        estado = apoio.rolar(estado)

        # Salário do Início mais o Coletor inteiro.
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000_000 + 300_000 + 450_000)
        self.assertEqual(estado["coletor"], 0)
        self.assertIn("coletor", apoio.tipos_do_log(estado))

    def test_coletor_vazio_so_avisa(self):
        estado = apoio.rolar(apoio.criar_estado(posicao=5))

        self.assertEqual(estado["jogadores"][0]["caixa"], 2_300_000)
        linha = next(linha for linha in estado["log"] if linha["tipo"] == "coletor_vazio")
        self.assertIn("vazio", linha["texto"])


if __name__ == "__main__":
    unittest.main()

import unittest

from engine import partida
from tests.engine import apoio


class BonusDoBancoTestes(unittest.TestCase):
    def criar(self, posicao=4):
        estado = apoio.criar_estado(posicao=posicao)
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 1}  # Capão Redondo: 130.000 + 32.500
        estado["evento"] = {"tipo": "bonus_do_banco", "nome": "Bônus do banco", "rodada": 1,
                            "regiao": [4, 3, 2, 1], "usaram": [], "texto": ""}
        return estado

    def test_regiao_sao_casas_seguidas_na_ordem_do_peao(self):
        estado = apoio.criar_estado()
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}

        partida._aplicar_evento(estado, "bonus_do_banco", apoio.GeradorFalso(sortes=(0.1,)))

        self.assertEqual(estado["evento"]["regiao"], [4, 3, 2, 1])

    def test_quem_comeca_a_vez_na_regiao_vende_acima_do_valor_e_continua(self):
        estado = self.criar()
        self.assertTrue(partida.estado_publico(estado, 1)["pode_vender_no_bonus"])

        estado = partida.vender_no_bonus(estado, 1, 1)

        # 35% acima do valor investido (162.500).
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000_000 + 219_375)
        self.assertNotIn("1", estado["propriedades"])
        self.assertEqual(estado["fase"], partida.FASE_ROLAR)
        self.assertEqual(apoio.vez_de(estado), 1)

    def test_vale_uma_vez_por_evento(self):
        estado = self.criar()
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}
        estado = partida.vender_no_bonus(estado, 1, 1)

        with self.assertRaisesRegex(partida.ErroDeRegra, "já usou"):
            partida.vender_no_bonus(estado, 1, 2)

    def test_parar_na_regiao_abre_a_oferta_antes_de_passar_a_vez(self):
        estado = apoio.rolar(self.criar(posicao=6))  # 6 -> 4, dentro da região

        self.assertEqual(estado["fase"], partida.FASE_BONUS_BANCO)
        self.assertEqual(apoio.vez_de(estado), 1)

        estado = partida.vender_no_bonus(estado, 1, None)
        self.assertEqual(apoio.vez_de(estado), 2)

    def test_fora_da_regiao_nao_vende(self):
        estado = self.criar(posicao=20)

        with self.assertRaisesRegex(partida.ErroDeRegra, "região"):
            partida.vender_no_bonus(estado, 1, 1)


if __name__ == "__main__":
    unittest.main()

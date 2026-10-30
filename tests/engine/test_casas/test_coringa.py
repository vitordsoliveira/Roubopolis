import unittest

from engine import partida
from tests.engine import apoio


class CasaCoringaTestes(unittest.TestCase):
    def parar_no_coringa(self, caixa_ana=2_000_000, caixa_bia=2_000_000):
        # Saindo do próprio portal com um passo só: cai na Coringa (11).
        estado = apoio.criar_estado(posicao=12)
        estado["jogadores"][0]["caixa"] = caixa_ana
        estado["jogadores"][1]["caixa"] = caixa_bia
        return apoio.rolar(estado, dados=(1,))

    def test_chance_acompanha_a_posicao_na_mesa(self):
        na_media = self.parar_no_coringa()["coringa_pendente"]
        atras = self.parar_no_coringa(caixa_ana=500_000)["coringa_pendente"]
        frente = self.parar_no_coringa(caixa_ana=4_000_000, caixa_bia=1_000_000)["coringa_pendente"]

        self.assertEqual((na_media["faixa"], na_media["chance"]), ("na_media", 0.50))
        self.assertEqual((atras["faixa"], atras["chance"]), ("atras", 0.60))
        self.assertEqual((frente["faixa"], frente["chance"]), ("frente", 0.20))

    def test_arriscar_e_ganhar(self):
        estado = self.parar_no_coringa()
        with apoio.sorteio(apoio.GeradorFalso(sortes=(0.1, 0.99))):
            estado = partida.decidir_coringa(estado, 1, True)

        self.assertEqual(estado["jogadores"][0]["caixa"], 3_000_000)
        self.assertTrue(estado["ultimo_coringa"]["ganhou"])
        self.assertEqual(apoio.vez_de(estado), 2)

    def test_arriscar_e_perder(self):
        estado = self.parar_no_coringa()
        with apoio.sorteio(apoio.GeradorFalso(sortes=(0.9,))):
            estado = partida.decidir_coringa(estado, 1, True)

        self.assertEqual(estado["jogadores"][0]["caixa"], 1_300_000)
        self.assertFalse(estado["ultimo_coringa"]["ganhou"])

    def test_perda_para_no_caixa(self):
        estado = self.parar_no_coringa(caixa_ana=200_000)
        self.assertEqual(estado["coringa_pendente"]["perda"], 200_000)

        with apoio.sorteio(apoio.GeradorFalso(sortes=(0.9,))):
            estado = partida.decidir_coringa(estado, 1, True)

        self.assertEqual(estado["jogadores"][0]["caixa"], 0)
        self.assertFalse(estado["jogadores"][0]["falido"])

    def test_nao_arriscar_nao_mexe_no_caixa(self):
        estado = partida.decidir_coringa(self.parar_no_coringa(), 1, False)

        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000_000)
        self.assertFalse(estado["ultimo_coringa"]["arriscou"])

    def test_tempo_esgotado_nao_arrisca(self):
        estado = self.parar_no_coringa()
        estado["prazo_vez"] = 100

        estado = partida.atualizar_tempo(estado, agora=100)

        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000_000)
        self.assertIsNone(estado["coringa_pendente"])
        self.assertEqual(apoio.vez_de(estado), 2)

    def test_so_quem_esta_na_vez_decide(self):
        estado = self.parar_no_coringa()

        with self.assertRaisesRegex(partida.ErroDeRegra, "Não é sua vez"):
            partida.decidir_coringa(estado, 2, True)


if __name__ == "__main__":
    unittest.main()

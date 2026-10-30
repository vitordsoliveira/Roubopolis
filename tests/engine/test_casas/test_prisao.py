import unittest

from engine import partida
from tests.engine import apoio


class CasaDaPrisaoTestes(unittest.TestCase):
    def test_preso_perde_a_proxima_vez(self):
        estado = apoio.rolar(apoio.criar_estado(posicao=16))  # 16 -> 14

        self.assertEqual(estado["jogadores"][0]["preso"], 1)
        self.assertEqual(apoio.vez_de(estado), 2)

        # Bia termina a vez; a de Ana é pulada e a vez volta para Bia.
        with apoio.sorteio(apoio.GeradorFalso()):
            estado = partida.passar_turno(estado)

        self.assertEqual(estado["jogadores"][0]["preso"], 0)
        self.assertEqual(apoio.vez_de(estado), 2)
        self.assertEqual(estado["rodada"], 2)
        self.assertIn("perde a vez", estado["log"][-2]["texto"])

        with apoio.sorteio(apoio.GeradorFalso()):
            estado = partida.passar_turno(estado)
        self.assertEqual(apoio.vez_de(estado), 1)

    def test_reincidente_fica_preso_mais_tempo(self):
        estado = apoio.criar_estado(posicao=16)
        estado["jogadores"][0]["reincidente"] = True

        estado = apoio.rolar(estado)

        self.assertEqual(estado["jogadores"][0]["preso"], 3)

    def test_mesa_inteira_presa_nao_trava(self):
        estado = apoio.criar_estado()
        for jogador in estado["jogadores"]:
            jogador["preso"] = 1

        with apoio.sorteio(apoio.GeradorFalso()):
            estado = partida.passar_turno(estado)

        self.assertEqual(estado["fase"], partida.FASE_ROLAR)
        self.assertEqual([j["preso"] for j in estado["jogadores"]], [0, 0])


if __name__ == "__main__":
    unittest.main()

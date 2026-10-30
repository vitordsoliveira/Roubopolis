"""O arquivo se chama prefeito por causa do README antigo; nas regras é o
Presidente Cor de Mel."""

import unittest

from engine import partida
from tests.engine import apoio


class PresidentePassouAquiTestes(unittest.TestCase):
    def test_confisca_o_coletor(self):
        estado = apoio.criar_estado()
        estado["coletor"] = 300_000

        partida._aplicar_evento(estado, "presidente", apoio.GeradorFalso())

        self.assertEqual(estado["coletor"], 0)
        self.assertEqual([j["caixa"] for j in estado["jogadores"]], [2_000_000, 2_000_000])

    def test_com_o_coletor_vazio_nao_e_sorteado(self):
        estado = apoio.criar_estado()

        self.assertFalse(partida._evento_faz_sentido(estado, "presidente"))

    def test_virada_de_rodada_sorteia_o_presidente_e_esvazia_o_coletor(self):
        estado = apoio.criar_estado()
        estado["coletor"] = 47_600
        estado["vez"] = 1  # o último da ordem: passar a vez abre a rodada 2
        # 0,1 < 25%: tem evento. Sem propriedades na mesa, os candidatos são
        # colheita, baile, final de ano e presidente; 0,8 × 4 = 3,2 cai no quarto.
        with apoio.sorteio(apoio.GeradorFalso(sortes=(0.1, 0.8))):
            estado = partida.passar_turno(estado)

        self.assertEqual(estado["rodada"], 2)
        self.assertEqual(estado["evento"]["tipo"], "presidente")
        self.assertEqual(estado["coletor"], 0)
        self.assertEqual([j["caixa"] for j in estado["jogadores"]], [2_000_000, 2_000_000])
        linha = next(l for l in estado["log"] if l["tipo"] == "evento_tematico")
        self.assertIn("Presidente Cor de Mel confiscou os R$ 47.600", linha["texto"])
        publico = partida.estado_publico(estado, 2)
        self.assertEqual(publico["evento"]["resumo"], "Coletor confiscado (R$ 47.600)")
        self.assertEqual(publico["coletor"], 0)


class SorteioDeEventosTestes(unittest.TestCase):
    def test_primeira_rodada_nunca_tem_evento(self):
        estado = apoio.criar_estado()
        with apoio.sorteio(apoio.GeradorFalso(sortes=(0.0,))):
            partida._iniciar_rodada(estado)

        self.assertIsNone(estado["evento"])

    def test_rodada_nova_pode_sortear_evento_pelo_peso(self):
        estado = apoio.criar_estado()
        estado["rodada"] = 2
        # 0.1 < 25%: acontece. Depois, 0.0 escolhe o primeiro com peso.
        with apoio.sorteio(apoio.GeradorFalso(sortes=(0.1, 0.0))):
            partida._iniciar_rodada(estado)

        self.assertEqual(estado["evento"]["tipo"], "colheita_ruim")

    def test_acima_da_chance_nao_acontece_nada(self):
        estado = apoio.criar_estado()
        estado["rodada"] = 2
        with apoio.sorteio(apoio.GeradorFalso(sortes=(0.9,))):
            partida._iniciar_rodada(estado)

        self.assertIsNone(estado["evento"])

    def test_evento_some_na_rodada_seguinte(self):
        estado = apoio.criar_estado()
        estado["rodada"] = 2
        with apoio.sorteio(apoio.GeradorFalso(sortes=(0.1, 0.0))):
            partida._iniciar_rodada(estado)
        estado["rodada"] = 3
        with apoio.sorteio(apoio.GeradorFalso(sortes=(0.9,))):
            partida._iniciar_rodada(estado)

        self.assertIsNone(estado["evento"])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from engine import partida


class DadosFixos:
    consumidos = 0

    def dados(self, quantidade, faces):
        return [1, 1]


class CompraPropriedadeTestes(unittest.TestCase):
    def criar_estado(self, caixa=10_000):
        estado = partida.criar_partida(
            [
                {"jogador_id": 1, "nome": "Ana"},
                {"jogador_id": 2, "nome": "Bia"},
            ],
            semente=123,
        )
        estado["fase"] = partida.FASE_ROLAR
        estado["vez"] = 0
        estado["jogadores"][0]["posicao"] = 4
        estado["jogadores"][0]["caixa"] = caixa
        return estado

    def rolar_dois(self, estado):
        with patch.object(partida, "_gerador", return_value=DadosFixos()):
            return partida.rolar(estado, 1)

    def test_parar_em_propriedade_livre_abre_compra_e_compra_registra_dono(self):
        estado = self.rolar_dois(self.criar_estado())

        self.assertEqual(estado["fase"], partida.FASE_COMPRA)
        self.assertEqual(estado["compra_pendente"]["casa"], 2)
        self.assertEqual(estado["jogadores"][0]["caixa"], 10_000)

        estado = partida.decidir_compra(estado, 1, True)

        self.assertEqual(estado["propriedades"]["2"]["dono"], 1)
        self.assertEqual(estado["jogadores"][0]["caixa"], 9_300)
        self.assertIsNone(estado["compra_pendente"])
        self.assertEqual(estado["fase"], partida.FASE_ROLAR)
        self.assertEqual(estado["jogadores"][estado["vez"]]["jogador_id"], 2)

    def test_recusar_nao_cobra_nem_registra_propriedade(self):
        estado = self.rolar_dois(self.criar_estado())
        estado = partida.decidir_compra(estado, 1, False)

        self.assertEqual(estado["jogadores"][0]["caixa"], 10_000)
        self.assertEqual(estado["propriedades"], {})
        self.assertIsNone(estado["compra_pendente"])
        self.assertEqual(estado["jogadores"][estado["vez"]]["jogador_id"], 2)

    def test_sem_saldo_nao_abre_compra_e_passa_a_vez(self):
        estado = self.rolar_dois(self.criar_estado(caixa=100))

        self.assertEqual(estado["fase"], partida.FASE_ROLAR)
        self.assertIsNone(estado["compra_pendente"])
        self.assertEqual(estado["jogadores"][estado["vez"]]["jogador_id"], 2)

    def test_parar_em_propriedade_com_dono_nao_oferece_nova_compra(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}

        estado = self.rolar_dois(estado)

        self.assertEqual(estado["fase"], partida.FASE_ROLAR)
        self.assertIsNone(estado["compra_pendente"])
        self.assertEqual(estado["propriedades"]["2"]["dono"], 2)
        self.assertEqual(estado["jogadores"][estado["vez"]]["jogador_id"], 2)

    def test_estado_v2_migra_sem_posses_incompativeis(self):
        estado = self.criar_estado()
        estado["versao"] = 2
        estado.pop("propriedades")

        atualizado = partida._atualizar(estado)

        self.assertEqual(atualizado["versao"], partida.VERSAO_DO_ESTADO)
        self.assertEqual(atualizado["propriedades"], {})
        self.assertIsNone(atualizado["compra_pendente"])

    def test_avanco_horario_comeca_na_inicial_e_segue_para_traz(self):
        tabuleiro = partida.carregar_tabuleiro("vila_original")

        self.assertEqual(tabuleiro.indice_inicial, 4)
        self.assertEqual(tabuleiro.avancar(4, 1), 3)
        self.assertEqual(tabuleiro.avancar(4, 2), 2)
        self.assertEqual(tabuleiro.avancar(5, 1), 4)

    def test_novos_jogadores_comecam_na_praca(self):
        estado = self.criar_estado()

        self.assertTrue(all(jogador["posicao"] == 4 for jogador in estado["jogadores"]))

    def test_detecta_cruzamento_da_inicial_no_sentido_horario(self):
        tabuleiro = partida.carregar_tabuleiro("vila_original")

        self.assertFalse(tabuleiro.passou_pelo_inicio(4, 1))
        self.assertTrue(tabuleiro.passou_pelo_inicio(5, 1))
        self.assertTrue(tabuleiro.passou_pelo_inicio(4, len(tabuleiro)))


if __name__ == "__main__":
    unittest.main()

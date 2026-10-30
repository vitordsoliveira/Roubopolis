import unittest

from engine import partida
from tests.engine import apoio


class CasaDaReconstrucaoTestes(unittest.TestCase):
    def criar(self, **kw):
        estado = apoio.criar_estado(posicao=34, **kw)  # 34 -> 32
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}  # Capão Redondo, 130.000
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 3}  # já no máximo
        return estado

    def test_oferece_so_o_que_ainda_sobe_de_nivel_com_desconto(self):
        estado = apoio.rolar(self.criar())

        self.assertEqual(estado["fase"], partida.FASE_RECONSTRUCAO)
        opcoes = estado["reconstrucao_pendente"]["opcoes"]
        self.assertEqual([o["casa"] for o in opcoes], [1])
        # Nível custa 25% de 130.000 = 32.500; com 30% de desconto, 22.750.
        self.assertEqual(opcoes[0]["custo_cheio"], 32_500)
        self.assertEqual(opcoes[0]["custo"], 22_750)

    def test_reformar_cobra_o_preco_com_desconto_e_sobe_o_nivel(self):
        estado = partida.decidir_reconstrucao(apoio.rolar(self.criar()), 1, 1)

        self.assertEqual(estado["propriedades"]["1"]["nivel"], 1)
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000_000 - 22_750)
        self.assertEqual(estado["jogadores"][0]["placar"]["melhorias"], 1)
        self.assertEqual(apoio.vez_de(estado), 2)

    def test_recusar_nao_cobra(self):
        estado = partida.decidir_reconstrucao(apoio.rolar(self.criar()), 1, None)

        self.assertEqual(estado["propriedades"]["1"]["nivel"], 0)
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000_000)

    def test_sem_propriedade_nao_abre_decisao(self):
        estado = apoio.rolar(apoio.criar_estado(posicao=34))

        self.assertEqual(estado["fase"], partida.FASE_ROLAR)
        self.assertEqual(apoio.vez_de(estado), 2)

    def test_tempo_esgotado_recusa(self):
        estado = apoio.rolar(self.criar())
        estado["prazo_vez"] = 100

        estado = partida.atualizar_tempo(estado, agora=100)

        self.assertEqual(estado["propriedades"]["1"]["nivel"], 0)
        self.assertIsNone(estado["reconstrucao_pendente"])
        self.assertEqual(apoio.vez_de(estado), 2)


if __name__ == "__main__":
    unittest.main()

import unittest

from engine import partida
from tests.engine import apoio


class CasaDoPrejuizoTestes(unittest.TestCase):
    def criar(self):
        """Bia lidera e tem duas casas atingíveis e uma cara, que fica de fora."""
        estado = apoio.criar_estado(posicao=30)  # 30 -> 28
        estado["jogadores"][1]["caixa"] = 3_000_000
        estado["propriedades"]["6"] = {"dono": 2, "nivel": 1}  # Mooca, média: 280.000 + 70.000
        estado["propriedades"]["1"] = {"dono": 2, "nivel": 0}  # Capão Redondo, barata: 130.000
        estado["propriedades"]["13"] = {"dono": 2, "nivel": 0}  # Perdizes, cara
        return estado

    def test_quem_pisa_escolhe_entre_as_medias_e_baratas_do_lider(self):
        estado = apoio.rolar(self.criar())

        self.assertEqual(estado["fase"], partida.FASE_PREJUIZO)
        pendente = estado["prejuizo_pendente"]
        self.assertEqual(pendente["alvo_id"], 2)
        self.assertEqual([o["casa"] for o in pendente["opcoes"]], [6, 1])
        self.assertEqual(pendente["opcoes"][0]["ao_coletor"], 175_000)

    def test_a_escolhida_volta_ao_banco_e_metade_vai_ao_coletor(self):
        estado = partida.escolher_prejuizo(apoio.rolar(self.criar()), 1, 1)

        self.assertNotIn("1", estado["propriedades"])
        self.assertIn("6", estado["propriedades"])
        self.assertEqual(estado["coletor"], 65_000)
        self.assertEqual(apoio.vez_de(estado), 2)

    def test_tempo_esgotado_tira_a_mais_valiosa(self):
        estado = apoio.rolar(self.criar())
        estado["prazo_vez"] = 100

        estado = partida.atualizar_tempo(estado, agora=100)

        self.assertNotIn("6", estado["propriedades"])
        self.assertEqual(estado["coletor"], 175_000)

    def test_lider_sem_media_ou_barata_perde_caixa_para_o_coletor(self):
        estado = apoio.criar_estado(posicao=30)
        estado["jogadores"][1]["caixa"] = 3_000_000
        estado["propriedades"]["13"] = {"dono": 2, "nivel": 0}

        estado = apoio.rolar(estado)

        self.assertEqual(estado["jogadores"][1]["caixa"], 3_000_000 - 450_000)
        self.assertEqual(estado["coletor"], 450_000)
        self.assertEqual(apoio.vez_de(estado), 2)

    def test_uma_opcao_so_e_aplicada_sem_perguntar(self):
        estado = apoio.criar_estado(posicao=30)
        estado["jogadores"][1]["caixa"] = 3_000_000
        estado["propriedades"]["1"] = {"dono": 2, "nivel": 0}

        estado = apoio.rolar(estado)

        self.assertNotIn("1", estado["propriedades"])
        self.assertEqual(estado["fase"], partida.FASE_ROLAR)

    def test_lider_que_pisa_tambem_toma_o_golpe(self):
        estado = apoio.criar_estado(posicao=30)
        estado["jogadores"][0]["caixa"] = 3_000_000
        estado["propriedades"]["6"] = {"dono": 1, "nivel": 0}
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}

        estado = apoio.rolar(estado)

        self.assertEqual(estado["prejuizo_pendente"]["alvo_id"], 1)
        self.assertEqual(estado["prejuizo_pendente"]["jogador_id"], 1)


if __name__ == "__main__":
    unittest.main()

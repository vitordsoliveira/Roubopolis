"""O arquivo se chama prefeito por causa do README antigo; nas regras é o
Presidente Cor de Mel."""

import unittest
from collections import defaultdict

from engine import partida
from sim.simulador import decidir
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
        estado["rodada_do_evento"] = 2
        # Sem propriedades na mesa, os candidatos são colheita, baile, final
        # de ano e presidente; 0,8 × 4 = 3,2 cai no quarto.
        with apoio.sorteio(apoio.GeradorFalso(sortes=(0.8,))):
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


class UmEventoPorPartidaTestes(unittest.TestCase):
    """A partida tem um evento temático só, numa rodada sorteada quando ela
    começa — antes, cada rodada tinha 25% de chance, e uma partida de 30
    rodadas via uns 7 eventos."""

    def test_a_rodada_do_evento_sai_quando_a_partida_comeca(self):
        estado = partida.criar_partida([{"jogador_id": 1, "nome": "Ana"}, {"jogador_id": 2, "nome": "Bia"}], semente=7)
        self.assertIsNone(estado["rodada_do_evento"])

        estado = partida.sortear_ordem(estado)

        self.assertIn(estado["rodada_do_evento"], range(2, 11))
        # Ninguém vê quando ele vem.
        self.assertNotIn("rodada_do_evento", partida.estado_publico(estado, 1))

    def test_a_rodada_sorteada_vai_da_segunda_a_decima(self):
        estado = apoio.criar_estado()
        self.assertEqual(partida._sortear_rodada_do_evento(estado, apoio.GeradorFalso(sortes=(0.0,))), 2)
        self.assertEqual(partida._sortear_rodada_do_evento(estado, apoio.GeradorFalso(sortes=(0.999,))), 10)

    def test_o_evento_cai_so_na_rodada_sorteada(self):
        estado = apoio.criar_estado()
        estado["rodada_do_evento"] = 3
        tipos = []
        for rodada in (2, 3, 4, 5):
            estado["rodada"] = rodada
            # 0.0 escolhe o primeiro com peso: a colheita ruim.
            with apoio.sorteio(apoio.GeradorFalso(sortes=(0.0,))):
                partida._iniciar_rodada(estado)
            tipos.append(estado["evento"] and estado["evento"]["tipo"])

        # Na rodada seguinte o evento acaba, e não vem outro.
        self.assertEqual(tipos, [None, "colheita_ruim", None, None])

    def test_partida_inteira_tem_um_evento_so(self):
        for semente in range(8):
            estado = partida.criar_partida(
                [{"jogador_id": i, "nome": f"Robô {i}"} for i in range(1, 5)], semente=semente
            )
            estado = partida.sortear_ordem(estado)
            rodadas_com_evento = set()
            while estado["fase"] != partida.FASE_FIM and estado["rodada"] <= 12:
                estado = decidir(estado, set(), True, defaultdict(int))
                if estado.get("evento"):
                    rodadas_com_evento.add(estado["evento"]["rodada"])
            self.assertEqual(rodadas_com_evento, {estado["rodada_do_evento"]}, f"semente {semente}")

    def test_mesa_de_antes_da_regra_nao_ganha_mais_evento(self):
        antigo = apoio.criar_estado()
        antigo["versao"] = 10
        antigo["rodada"] = 4
        del antigo["rodada_do_evento"]

        atualizado = partida._atualizar(antigo)

        self.assertIsNone(atualizado["rodada_do_evento"])


if __name__ == "__main__":
    unittest.main()

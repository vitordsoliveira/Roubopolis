"""Partidas inteiras, do sorteio ao pódio, com o motor de verdade.

Não confere valor nenhum: confere que nenhuma combinação de casas, eventos e
decisões trava a mesa ou quebra o placar. O sorteio é o de verdade (semente
fixa), e cada semente é uma partida diferente.
"""

import unittest

from engine import partida
from sim.simulador import decidir


class PartidaCompletaTestes(unittest.TestCase):
    def jogar(self, semente, jogadores=4, limite=3000):
        estado = partida.criar_partida(
            [{"jogador_id": i, "nome": f"Bot {i}"} for i in range(1, jogadores + 1)], semente
        )
        estado = partida.sortear_ordem(estado)
        # Sem relógio de partida: quem encerra é o limite de rodadas abaixo.
        estado["prazo_partida"] = None
        for _ in range(limite):
            if estado["fase"] == partida.FASE_FIM:
                break
            if estado["rodada"] > 25 and estado["encerrar_apos_rodada"] is None:
                estado["encerrar_apos_rodada"] = estado["rodada"]
            estado = decidir(estado)
        return estado

    def test_partidas_terminam_com_podio_coerente(self):
        for semente in range(40):
            with self.subTest(semente=semente):
                estado = self.jogar(semente)

                self.assertEqual(estado["fase"], partida.FASE_FIM)
                classificacao = estado["classificacao"]
                self.assertEqual(len(classificacao), 4)
                primeiros = {c["jogador_id"] for c in classificacao if c["posicao"] == 1}
                self.assertEqual(primeiros, set(estado["vencedores"]))
                for jogador in estado["jogadores"]:
                    self.assertGreaterEqual(jogador["caixa"], 0)
                    self.assertGreaterEqual(jogador["placar"]["arrecadado"], 0)

    def test_estado_publico_serve_em_qualquer_fase(self):
        estado = self.jogar(7, limite=60)
        publico = partida.estado_publico(estado, 1)

        self.assertIn("coletor", publico)
        self.assertEqual(len(publico["jogadores"]), 4)


if __name__ == "__main__":
    unittest.main()

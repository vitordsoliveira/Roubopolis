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
        estado["prazo_vez"] = 4_000_000_000
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

    def test_cair_em_propriedade_alheia_oferece_compra_e_transfere_pagamento(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 1}
        estado["jogadores"][0]["caixa"] = 2_000
        estado["jogadores"][1]["caixa"] = 3_000

        estado = self.rolar_dois(estado)

        self.assertEqual(estado["fase"], partida.FASE_COMPRA_JOGADOR)
        self.assertEqual(estado["compra_pendente"]["casa"], 2)
        self.assertEqual(estado["compra_pendente"]["vendedor_id"], 2)
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000)
        self.assertEqual(estado["jogadores"][1]["caixa"], 3_000)

        atualizado = partida.decidir_compra_jogador(estado, 1, True)

        self.assertEqual(atualizado["propriedades"]["2"], {"dono": 1, "nivel": 1})
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 1_300)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 3_700)
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000)
        self.assertIsNone(atualizado["compra_pendente"])
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)
        self.assertTrue(any(log["tipo"] == "compra_jogador" for log in atualizado["log"]))
        self.assertFalse(any(log["tipo"] == "aluguel" for log in atualizado["log"]))

    def test_recusar_compra_de_propriedade_alheia_paga_aluguel(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 1}
        estado = self.rolar_dois(estado)
        estado = partida.decidir_compra_jogador(estado, 1, False)

        self.assertEqual(estado["propriedades"]["2"]["dono"], 2)
        self.assertEqual(estado["jogadores"][0]["caixa"], 9_839)
        self.assertEqual(estado["jogadores"][1]["caixa"], 10_161)
        self.assertIsNone(estado["compra_pendente"])
        self.assertTrue(any(log["tipo"] == "aluguel" for log in estado["log"]))

    def test_tempo_esgotado_na_oferta_de_propriedade_alheia_cobra_aluguel(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}
        estado = self.rolar_dois(estado)
        estado["prazo_vez"] = 100

        atualizado = partida.atualizar_tempo(estado, agora=100)

        self.assertEqual(atualizado["propriedades"]["2"]["dono"], 2)
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 9_860)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 10_140)
        self.assertIsNone(atualizado["compra_pendente"])
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)
        self.assertTrue(any("não comprou a propriedade" in log["texto"] for log in atualizado["log"]))
        self.assertTrue(any(log["tipo"] == "aluguel" for log in atualizado["log"]))

    def test_cair_em_propriedade_alheia_sem_dinheiro_e_sem_ativos_fali(self):
        estado = self.criar_estado(caixa=100)
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}

        atualizado = self.rolar_dois(estado)

        self.assertEqual(atualizado["fase"], partida.FASE_FIM)
        self.assertIsNone(atualizado["compra_pendente"])
        self.assertEqual(atualizado["propriedades"]["2"]["dono"], 2)
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 0)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 10_100)
        self.assertTrue(atualizado["jogadores"][0]["falido"])
        self.assertTrue(any(log["tipo"] == "falencia" for log in atualizado["log"]))

    def test_aluguel_sem_saldo_abre_liquidacao_e_venda_paga_a_divida(self):
        estado = self.criar_estado(caixa=100)
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}

        estado = self.rolar_dois(estado)

        self.assertEqual(estado["fase"], partida.FASE_LIQUIDACAO_ALUGUEL)
        self.assertEqual(estado["aluguel_pendente"]["divida"], 140)
        self.assertEqual(estado["jogadores"][0]["caixa"], 100)
        self.assertEqual(estado["jogadores"][1]["caixa"], 10_000)

        atualizado = partida.vender_propriedade_para_aluguel(estado, 1, 1)

        self.assertNotIn("1", atualizado["propriedades"])
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 188)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 10_140)
        self.assertIsNone(atualizado["aluguel_pendente"])
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)

    def test_pode_escolher_varias_propriedades_ate_cobrir_aluguel(self):
        estado = self.criar_estado(caixa=0)
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 10}
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}
        estado["propriedades"]["26"] = {"dono": 1, "nivel": 0}
        estado = self.rolar_dois(estado)

        primeira_venda = partida.vender_propriedade_para_aluguel(estado, 1, 1)

        self.assertEqual(primeira_venda["fase"], partida.FASE_LIQUIDACAO_ALUGUEL)
        self.assertEqual(primeira_venda["jogadores"][0]["caixa"], 228)
        self.assertEqual(primeira_venda["jogadores"][1]["caixa"], 10_000)

        atualizado = partida.vender_propriedade_para_aluguel(primeira_venda, 1, 26)

        self.assertEqual(atualizado["jogadores"][0]["caixa"], 858)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 10_350)
        self.assertNotIn("1", atualizado["propriedades"])
        self.assertNotIn("26", atualizado["propriedades"])
        self.assertIsNone(atualizado["aluguel_pendente"])
        self.assertEqual(atualizado["fase"], partida.FASE_ROLAR)

    def test_se_vendas_nao_cobrirem_divida_fali_e_outros_seguem(self):
        estado = partida.criar_partida(
            [
                {"jogador_id": 1, "nome": "Ana"},
                {"jogador_id": 2, "nome": "Bia"},
                {"jogador_id": 3, "nome": "Caio"},
            ],
            semente=123,
        )
        estado["fase"] = partida.FASE_ROLAR
        estado["vez"] = 0
        estado["jogadores"][0]["posicao"] = 4
        estado["jogadores"][0]["caixa"] = 0
        estado["jogadores"][1]["caixa"] = 5_000
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 10}
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}
        estado["prazo_vez"] = 4_000_000_000
        estado = self.rolar_dois(estado)

        self.assertEqual(estado["fase"], partida.FASE_LIQUIDACAO_ALUGUEL)
        atualizado = partida.vender_propriedade_para_aluguel(estado, 1, 1)

        self.assertEqual(atualizado["fase"], partida.FASE_ROLAR)
        self.assertTrue(atualizado["jogadores"][0]["falido"])
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 0)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 5_228)
        self.assertNotIn("1", atualizado["propriedades"])
        self.assertEqual(atualizado["propriedades"]["2"]["dono"], 2)
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)
        self.assertTrue(any(log["tipo"] == "falencia" for log in atualizado["log"]))

    def test_nao_pode_vender_propriedade_de_outro_na_liquidacao(self):
        estado = self.criar_estado(caixa=100)
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}
        estado = self.rolar_dois(estado)

        with self.assertRaisesRegex(partida.ErroDeRegra, "não é sua"):
            partida.vender_propriedade_para_aluguel(estado, 1, 2)

    def test_expirar_prazo_de_liquidacao_fali_e_passa_a_vez(self):
        estado = self.criar_estado(caixa=100)
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}
        estado = self.rolar_dois(estado)
        estado["prazo_vez"] = 100

        atualizado = partida.atualizar_tempo(estado, agora=100)

        self.assertTrue(atualizado["jogadores"][0]["falido"])
        self.assertNotIn("1", atualizado["propriedades"])
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 10_100)
        self.assertEqual(atualizado["fase"], partida.FASE_FIM)
        self.assertFalse(atualizado["jogadores"][1]["falido"])

    def test_cair_na_propria_propriedade_nao_abre_oferta_de_compra(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}

        atualizado = self.rolar_dois(estado)

        self.assertEqual(atualizado["fase"], partida.FASE_ROLAR)
        self.assertIsNone(atualizado["compra_pendente"])
        self.assertEqual(atualizado["propriedades"]["2"]["dono"], 1)

    def test_nao_pode_comprar_propriedade_sem_ter_a_oferta_do_turno(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}

        with self.assertRaisesRegex(partida.ErroDeRegra, "Não há uma oferta"):
            partida.decidir_compra_jogador(estado, 1, True)

    def test_estado_v2_migra_sem_posses_incompativeis(self):
        estado = self.criar_estado()
        estado["versao"] = 2
        estado.pop("propriedades")

        atualizado = partida._atualizar(estado)

        self.assertEqual(atualizado["versao"], partida.VERSAO_DO_ESTADO)
        self.assertEqual(atualizado["propriedades"], {})
        self.assertIsNone(atualizado["compra_pendente"])

    def test_estado_ativo_antigo_recebe_novo_prazo_sem_encerrar_imediatamente(self):
        estado = self.criar_estado()
        estado["versao"] = 6
        estado.pop("minutos_de_partida")
        estado.pop("prazo_partida")
        estado["encerrar_apos_rodada"] = None

        with patch("engine.partida.time.time", return_value=1_000):
            atualizado = partida._atualizar(estado)

        self.assertEqual(atualizado["versao"], partida.VERSAO_DO_ESTADO)
        self.assertEqual(atualizado["prazo_partida"], 1_900)
        self.assertIsNone(atualizado["encerrar_apos_rodada"])
        self.assertEqual(atualizado["fase"], partida.FASE_ROLAR)

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

    def test_prazo_padrao_e_trinta_segundos(self):
        estado = self.criar_estado()

        self.assertEqual(estado["segundos_por_turno"], 30)

    def test_sorteio_inicia_cronometro_de_trinta_segundos(self):
        estado = partida.criar_partida(
            [
                {"jogador_id": 1, "nome": "Ana"},
                {"jogador_id": 2, "nome": "Bia"},
            ],
            semente=123,
        )
        with patch("engine.partida.time.time", return_value=1_000):
            estado = partida.sortear_ordem(estado)

        self.assertEqual(estado["prazo_vez"], 1_030)

    def test_sorteio_inicia_cronometro_total_de_quinze_minutos(self):
        estado = partida.criar_partida(
            [
                {"jogador_id": 1, "nome": "Ana"},
                {"jogador_id": 2, "nome": "Bia"},
            ],
            semente=123,
        )

        with patch("engine.partida.time.time", return_value=1_000):
            estado = partida.sortear_ordem(estado)

        self.assertEqual(estado["minutos_de_partida"], 15)
        self.assertEqual(estado["prazo_partida"], 1_900)

    def test_prazo_total_marca_rodada_final_mas_deixa_todos_jogarem(self):
        estado = partida.criar_partida(
            [
                {"jogador_id": 1, "nome": "Ana"},
                {"jogador_id": 2, "nome": "Bia"},
                {"jogador_id": 3, "nome": "Caio"},
            ],
            semente=123,
        )
        estado["fase"] = partida.FASE_ROLAR
        estado["prazo_vez"] = 10_000
        estado["prazo_partida"] = 100
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}
        estado["jogadores"][0]["caixa"] = 11_000

        atualizado = partida.atualizar_tempo(estado, agora=100)
        primeiro = partida.passar_turno(atualizado, agora=101)
        primeiro_id = primeiro["jogadores"][primeiro["vez"]]["jogador_id"]
        self.assertEqual(primeiro["fase"], partida.FASE_ROLAR)
        segundo = partida.passar_turno(primeiro, agora=102)
        segundo_id = segundo["jogadores"][segundo["vez"]]["jogador_id"]
        self.assertEqual(segundo["fase"], partida.FASE_ROLAR)

        self.assertEqual(atualizado["encerrar_apos_rodada"], 1)
        self.assertEqual(primeiro_id, 2)
        self.assertEqual(segundo_id, 3)

        final = partida.passar_turno(segundo, agora=103)

        self.assertEqual(final["fase"], partida.FASE_FIM)
        self.assertEqual(final["motivo_fim"], "tempo")
        self.assertEqual(final["vencedores"], [1])
        self.assertEqual(final["patrimonios_finais"], {"1": 11_000, "2": 10_700, "3": 10_000})
        self.assertEqual(final["rodada"], 1)

    def test_tempo_esgotado_entre_turnos_finaliza_apos_rodada_corrente(self):
        estado = partida.criar_partida(
            [
                {"jogador_id": 1, "nome": "Ana"},
                {"jogador_id": 2, "nome": "Bia"},
            ],
            semente=123,
        )
        estado["fase"] = partida.FASE_ROLAR
        estado["vez"] = 1
        estado["prazo_vez"] = 10_000
        estado["prazo_partida"] = 100
        estado["rodada"] = 4

        atualizado = partida.atualizar_tempo(estado, agora=100)
        final = partida.passar_turno(atualizado, agora=101)

        self.assertEqual(final["fase"], partida.FASE_FIM)
        self.assertEqual(final["rodada"], 4)
        self.assertEqual(final["vencedores"], [1, 2])
        self.assertIn("empatado", final["log"][-1]["texto"])

    def test_oferta_de_compra_reinicia_prazo_completo(self):
        estado = self.criar_estado()
        with (
            patch.object(partida, "_gerador", return_value=DadosFixos()),
            patch("engine.partida.time.time", return_value=1_000),
        ):
            estado = partida.rolar(estado, 1)

        self.assertEqual(estado["fase"], partida.FASE_COMPRA)
        self.assertEqual(estado["prazo_vez"], 1_030)

    def test_tempo_esgotado_passa_a_vez_e_inicia_novo_prazo(self):
        estado = self.criar_estado()
        estado["prazo_vez"] = 100

        atualizado = partida.atualizar_tempo(estado, agora=100)

        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)
        self.assertEqual(atualizado["prazo_vez"], 130)
        self.assertTrue(any(log["tipo"] == "tempo" for log in atualizado["log"]))

    def test_tempo_esgotado_na_compra_recusa_e_nao_cobra(self):
        estado = self.rolar_dois(self.criar_estado())
        estado["prazo_vez"] = 100

        atualizado = partida.atualizar_tempo(estado, agora=100)

        self.assertEqual(atualizado["propriedades"], {})
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 10_000)
        self.assertIsNone(atualizado["compra_pendente"])
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from engine import partida


class DadosFixos:
    consumidos = 0

    def dados(self, quantidade, faces):
        return [1, 1]

    def sorte(self):
        # Alto de propósito: nenhum easter egg nem evento temático acontece.
        return 0.99


class CompraPropriedadeTestes(unittest.TestCase):
    def criar_estado(self, caixa=2_000_000):
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
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000_000)

        estado = partida.decidir_compra(estado, 1, True)

        self.assertEqual(estado["propriedades"]["2"]["dono"], 1)
        self.assertEqual(estado["jogadores"][0]["caixa"], 1_860_000)
        self.assertIsNone(estado["compra_pendente"])
        # Logo depois da compra vem a oferta de construir.
        self.assertEqual(estado["fase"], partida.FASE_MELHORIA)
        self.assertEqual(estado["melhoria_pendente"]["origem"], "compra")

        estado = partida.decidir_melhoria(estado, 1, False)

        self.assertEqual(estado["fase"], partida.FASE_ROLAR)
        self.assertEqual(estado["jogadores"][estado["vez"]]["jogador_id"], 2)

    def test_comprar_e_construir_na_mesma_jogada(self):
        estado = partida.decidir_compra(self.rolar_dois(self.criar_estado()), 1, True)
        estado = partida.decidir_melhoria(estado, 1, True)

        self.assertEqual(estado["propriedades"]["2"], {"dono": 1, "nivel": 1})
        self.assertEqual(estado["jogadores"][0]["caixa"], 1_825_000)
        self.assertEqual(estado["jogadores"][estado["vez"]]["jogador_id"], 2)

    def test_compra_sem_caixa_para_construir_passa_a_vez(self):
        estado = partida.decidir_compra(self.rolar_dois(self.criar_estado(caixa=150_000)), 1, True)

        self.assertIsNone(estado["melhoria_pendente"])
        self.assertEqual(estado["fase"], partida.FASE_ROLAR)
        self.assertEqual(estado["jogadores"][estado["vez"]]["jogador_id"], 2)

    def test_recusar_nao_cobra_nem_registra_propriedade(self):
        estado = self.rolar_dois(self.criar_estado())
        estado = partida.decidir_compra(estado, 1, False)

        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000_000)
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
        estado["jogadores"][0]["caixa"] = 200_000
        estado["jogadores"][1]["caixa"] = 300_000

        estado = self.rolar_dois(estado)

        self.assertEqual(estado["fase"], partida.FASE_COMPRA_JOGADOR)
        self.assertEqual(estado["compra_pendente"]["casa"], 2)
        self.assertEqual(estado["compra_pendente"]["vendedor_id"], 2)
        self.assertEqual(estado["jogadores"][0]["caixa"], 200_000)
        self.assertEqual(estado["jogadores"][1]["caixa"], 300_000)

        # Tabela 140.000 + uma melhoria de 35.000: o vendedor recebe pelas duas.
        self.assertEqual(estado["compra_pendente"]["preco"], 175_000)

        atualizado = partida.decidir_compra_jogador(estado, 1, True)

        self.assertEqual(atualizado["propriedades"]["2"], {"dono": 1, "nivel": 1})
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 25_000)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 475_000)
        self.assertEqual(estado["jogadores"][0]["caixa"], 200_000)
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
        # Nível 1: 20% de 140.000 = 28.000, mais 50% disso.
        self.assertEqual(estado["jogadores"][0]["caixa"], 1_958_000)
        self.assertEqual(estado["jogadores"][1]["caixa"], 2_042_000)
        self.assertIsNone(estado["compra_pendente"])
        self.assertTrue(any(log["tipo"] == "aluguel" for log in estado["log"]))

    def test_tempo_esgotado_na_oferta_de_propriedade_alheia_cobra_aluguel(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}
        estado = self.rolar_dois(estado)
        estado["prazo_vez"] = 100

        atualizado = partida.atualizar_tempo(estado, agora=100)

        self.assertEqual(atualizado["propriedades"]["2"]["dono"], 2)
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 1_972_000)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 2_028_000)
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
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 2_000_100)
        self.assertTrue(atualizado["jogadores"][0]["falido"])
        self.assertTrue(any(log["tipo"] == "falencia" for log in atualizado["log"]))

    def test_aluguel_sem_saldo_abre_liquidacao_e_venda_paga_a_divida(self):
        estado = self.criar_estado(caixa=100)
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}

        estado = self.rolar_dois(estado)

        self.assertEqual(estado["fase"], partida.FASE_LIQUIDACAO_ALUGUEL)
        self.assertEqual(estado["aluguel_pendente"]["divida"], 28_000)
        self.assertEqual(estado["jogadores"][0]["caixa"], 100)
        self.assertEqual(estado["jogadores"][1]["caixa"], 2_000_000)

        atualizado = partida.vender_propriedade_para_aluguel(estado, 1, 1)

        self.assertNotIn("1", atualizado["propriedades"])
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 17_600)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 2_028_000)
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
        self.assertEqual(primeira_venda["jogadores"][0]["caixa"], 45_500)
        self.assertEqual(primeira_venda["jogadores"][1]["caixa"], 2_000_000)

        atualizado = partida.vender_propriedade_para_aluguel(primeira_venda, 1, 26)

        self.assertEqual(atualizado["jogadores"][0]["caixa"], 73_500)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 2_168_000)
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
        estado["jogadores"][1]["caixa"] = 5_000_000
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 10}
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}
        estado["prazo_vez"] = 4_000_000_000
        estado = self.rolar_dois(estado)

        self.assertEqual(estado["fase"], partida.FASE_LIQUIDACAO_ALUGUEL)
        atualizado = partida.vender_propriedade_para_aluguel(estado, 1, 1)

        self.assertEqual(atualizado["fase"], partida.FASE_ROLAR)
        self.assertTrue(atualizado["jogadores"][0]["falido"])
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 0)
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 5_045_500)
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
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 2_000_100)
        self.assertEqual(atualizado["fase"], partida.FASE_FIM)
        self.assertFalse(atualizado["jogadores"][1]["falido"])

    def test_cair_na_propria_propriedade_oferece_melhoria_e_nao_compra(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}

        atualizado = self.rolar_dois(estado)

        self.assertEqual(atualizado["fase"], partida.FASE_MELHORIA)
        self.assertIsNone(atualizado["compra_pendente"])
        self.assertEqual(
            atualizado["melhoria_pendente"],
            {
                "casa": 2, "jogador_id": 1, "origem": "visita", "nivel": 0,
                "custo": 35_000, "aluguel_atual": 28_000, "aluguel_novo": 42_000,
            },
        )
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 1)

    def test_aceitar_melhoria_cobra_sobe_nivel_e_passa_a_vez(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 1}
        estado = self.rolar_dois(estado)

        atualizado = partida.decidir_melhoria(estado, 1, True)

        self.assertEqual(atualizado["propriedades"]["2"]["nivel"], 2)
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 1_965_000)
        self.assertIsNone(atualizado["melhoria_pendente"])
        self.assertEqual(atualizado["fase"], partida.FASE_ROLAR)
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)

    def test_recusar_melhoria_nao_cobra_e_passa_a_vez(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}
        estado = self.rolar_dois(estado)

        atualizado = partida.decidir_melhoria(estado, 1, False)

        self.assertEqual(atualizado["propriedades"]["2"]["nivel"], 0)
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 2_000_000)
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)

    def test_tempo_esgotado_na_melhoria_recusa(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}
        estado = self.rolar_dois(estado)
        estado["prazo_vez"] = 100

        atualizado = partida.atualizar_tempo(estado, agora=100)

        self.assertEqual(atualizado["propriedades"]["2"]["nivel"], 0)
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 2_000_000)
        self.assertIsNone(atualizado["melhoria_pendente"])
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)

    def test_nivel_maximo_nao_oferece_melhoria(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 3}

        atualizado = self.rolar_dois(estado)

        self.assertIsNone(atualizado["melhoria_pendente"])
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)

    def test_sem_caixa_nao_oferece_melhoria(self):
        estado = self.criar_estado(caixa=1_000)
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}

        atualizado = self.rolar_dois(estado)

        self.assertIsNone(atualizado["melhoria_pendente"])
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)

    def test_nao_decide_melhoria_sem_oferta(self):
        estado = self.criar_estado()

        with self.assertRaisesRegex(partida.ErroDeRegra, "Não há uma melhoria"):
            partida.decidir_melhoria(estado, 1, True)

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
        self.assertEqual(atualizado["prazo_partida"], 2_500)
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
        self.assertTrue(all(jogador["caixa"] == 2_000_000 for jogador in estado["jogadores"]))

    def test_passar_pelo_inicio_paga_salario_uma_vez(self):
        estado = self.criar_estado()
        estado["jogadores"][0]["posicao"] = 6

        atualizado = self.rolar_dois(estado)

        self.assertEqual(atualizado["jogadores"][0]["posicao"], 4)
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 2_300_000)
        self.assertTrue(any(log["tipo"] == "salario_inicio" for log in atualizado["log"]))

    def test_nao_paga_salario_se_nao_passou_pelo_inicio(self):
        estado = self.criar_estado()

        atualizado = self.rolar_dois(estado)

        self.assertEqual(atualizado["jogadores"][0]["caixa"], 2_000_000)
        self.assertFalse(any(log["tipo"] == "salario_inicio" for log in atualizado["log"]))

    def test_custo_de_upgrade_e_um_quarto_do_preco_da_propriedade(self):
        tabuleiro = partida.carregar_tabuleiro("vila_original")
        casa = tabuleiro.casa(1)
        estado = self.criar_estado()

        self.assertEqual(partida._valor_upgrade(estado, casa), 32_500)

    def test_aluguel_no_nivel_maximo_e_metade_da_tabela(self):
        estado = self.criar_estado()
        casa = partida.carregar_tabuleiro("vila_original").casa(37)

        self.assertEqual(partida._valor_aluguel(estado, casa, {"nivel": 0}), 200_000)
        self.assertEqual(partida._valor_aluguel(estado, casa, {"nivel": 3}), 500_000)

    def test_melhoria_conta_no_patrimonio(self):
        estado = self.criar_estado()
        estado["propriedades"]["2"] = {"dono": 1, "nivel": 0}

        antes = partida._patrimonio(estado, estado["jogadores"][0])
        depois = partida.decidir_melhoria(self.rolar_dois(estado), 1, True)

        self.assertEqual(depois["propriedades"]["2"]["nivel"], 1)
        self.assertEqual(partida._patrimonio(depois, depois["jogadores"][0]), antes)

    def test_venda_ao_banco_inclui_melhorias(self):
        estado = self.criar_estado(caixa=0)
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 10}
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 2}
        estado = self.rolar_dois(estado)

        atualizado = partida.vender_propriedade_para_aluguel(estado, 1, 1)

        # 35% de (130.000 + 2 x 32.500). Não cobre a dívida: o jogador fali e
        # o valor da venda vai inteiro para o credor.
        self.assertEqual(atualizado["jogadores"][1]["caixa"], 2_068_250)

    def test_estado_publico_traz_valores_calculados(self):
        estado = self.criar_estado()
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 1}

        publica = partida.estado_publico(estado, 1)["propriedades"]["1"]

        self.assertEqual(publica["dono"], 1)
        self.assertEqual(publica["aluguel"], 39_000)
        self.assertEqual(publica["aluguel_proximo_nivel"], 52_000)
        self.assertEqual(publica["custo_melhoria"], 32_500)
        self.assertEqual(publica["preco_compra"], 162_500)
        self.assertEqual(publica["valor_banco"], 56_875)
        self.assertEqual(publica["nivel_maximo"], 3)

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

    def test_sorteio_inicia_cronometro_total_de_vinte_e_cinco_minutos(self):
        estado = partida.criar_partida(
            [
                {"jogador_id": 1, "nome": "Ana"},
                {"jogador_id": 2, "nome": "Bia"},
            ],
            semente=123,
        )

        with patch("engine.partida.time.time", return_value=1_000):
            estado = partida.sortear_ordem(estado)

        self.assertEqual(estado["minutos_de_partida"], 25)
        self.assertEqual(estado["prazo_partida"], 2_500)

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
        estado["jogadores"][0]["caixa"] = 2_300_000

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
        self.assertEqual(final["patrimonios_finais"], {"1": 2_300_000, "2": 2_140_000, "3": 2_000_000})
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
        self.assertEqual(atualizado["jogadores"][0]["caixa"], 2_000_000)
        self.assertIsNone(atualizado["compra_pendente"])
        self.assertEqual(atualizado["jogadores"][atualizado["vez"]]["jogador_id"], 2)


if __name__ == "__main__":
    unittest.main()

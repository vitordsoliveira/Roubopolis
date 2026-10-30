"""Leilão: quem está bem atrás põe uma propriedade em leilão no começo da
vez; os outros dão lances contra o relógio; o maior leva, pagando 2% da
TABELA de imposto ao Coletor. Sem lance, o banco compra por 35% do valor
investido.

Itaquera (índice 2) vale 140.000: o banco paga 49.000 sem lance, o imposto
é 2.800, o lance sobe de 10.000 em 10.000 e o primeiro é 50.000.
"""

import unittest

from engine import partida
from tests.engine import apoio

T0 = 1_000_000.0
ITAQUERA = 2


def mesa_com_alguem_atras(nivel=0):
    """Ana (1) está na vez, com 100.000 em caixa e Itaquera; Bia (2) e Caio
    (3) têm 2 milhões cada. Ana tem 240.000 contra uma média de ~1,4 milhão."""
    estado = apoio.criar_estado(jogadores=3)
    estado["jogadores"][0]["caixa"] = 100_000
    estado["propriedades"][str(ITAQUERA)] = {"dono": 1, "nivel": nivel}
    return estado


def aberto(nivel=0):
    return partida.abrir_leilao(mesa_com_alguem_atras(nivel), 1, ITAQUERA, agora=T0)


def fechar(estado):
    return partida.atualizar_tempo(estado, agora=estado["prazo_vez"] + 1)


class AbrirLeilaoTestes(unittest.TestCase):
    def test_quem_esta_atras_poe_a_propriedade_em_leilao(self):
        estado = aberto()

        self.assertEqual(estado["fase"], partida.FASE_LEILAO)
        self.assertEqual(estado["prazo_vez"], T0 + 12)
        leilao = estado["leilao"]
        self.assertEqual(leilao["vendedor_id"], 1)
        self.assertEqual(leilao["oferta_do_banco"], 49_000)
        self.assertEqual(leilao["imposto"], 2_800)
        self.assertEqual(leilao["passo"], 10_000)
        self.assertEqual(partida._lance_minimo(leilao), 50_000)
        self.assertEqual(estado["jogadores"][0]["leiloou_na_rodada"], 1)
        self.assertIn("leilao_aberto", apoio.tipos_do_log(estado))

    def test_quem_nao_esta_atras_nao_leiloa(self):
        estado = mesa_com_alguem_atras()
        estado["jogadores"][0]["caixa"] = 2_000_000

        with self.assertRaisesRegex(partida.ErroDeRegra, "abaixo de 60% da média"):
            partida.abrir_leilao(estado, 1, ITAQUERA, agora=T0)

    def test_so_na_propria_vez_e_antes_de_rolar(self):
        estado = mesa_com_alguem_atras()
        estado["propriedades"]["20"] = {"dono": 2, "nivel": 0}
        with self.assertRaisesRegex(partida.ErroDeRegra, "Não é sua vez"):
            partida.abrir_leilao(estado, 2, 20, agora=T0)

        estado["fase"] = partida.FASE_COMPRA
        with self.assertRaisesRegex(partida.ErroDeRegra, "antes de rolar"):
            partida.abrir_leilao(estado, 1, ITAQUERA, agora=T0)

    def test_so_propriedade_propria(self):
        estado = mesa_com_alguem_atras()
        estado["propriedades"]["20"] = {"dono": 2, "nivel": 0}

        with self.assertRaisesRegex(partida.ErroDeRegra, "não é sua"):
            partida.abrir_leilao(estado, 1, 20, agora=T0)

    def test_um_leilao_por_rodada(self):
        estado = fechar(aberto())
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}

        with self.assertRaisesRegex(partida.ErroDeRegra, "já leiloou nesta rodada"):
            partida.abrir_leilao(estado, 1, 1, agora=T0 + 20)

    def test_nao_da_para_rolar_com_o_leilao_aberto(self):
        # Relógio de verdade: `rolar` confere o prazo com a hora atual.
        estado = partida.abrir_leilao(mesa_com_alguem_atras(), 1, ITAQUERA)

        with self.assertRaisesRegex(partida.ErroDeRegra, "rolar"):
            partida.rolar(estado, 1)


class LanceTestes(unittest.TestCase):
    def test_lance_precisa_passar_do_minimo(self):
        with self.assertRaisesRegex(partida.ErroDeRegra, "mínimo agora é R\\$ 50.000"):
            partida.dar_lance(aberto(), 2, 49_000, agora=T0 + 1)

    def test_lance_mais_imposto_precisa_caber_no_caixa(self):
        estado = aberto()
        estado["jogadores"][1]["caixa"] = 52_000

        with self.assertRaisesRegex(partida.ErroDeRegra, "não cobre"):
            partida.dar_lance(estado, 2, 50_000, agora=T0 + 1)

    def test_quem_vende_nao_da_lance(self):
        with self.assertRaisesRegex(partida.ErroDeRegra, "próprio leilão"):
            partida.dar_lance(aberto(), 1, 50_000, agora=T0 + 1)

    def test_quem_lidera_nao_cobre_o_proprio_lance(self):
        estado = partida.dar_lance(aberto(), 2, 50_000, agora=T0 + 1)

        with self.assertRaisesRegex(partida.ErroDeRegra, "já é o maior"):
            partida.dar_lance(estado, 2, 60_000, agora=T0 + 2)

    def test_cada_lance_sobe_o_minimo(self):
        estado = partida.dar_lance(aberto(), 2, 50_000, agora=T0 + 1)
        estado = partida.dar_lance(estado, 3, 75_000, agora=T0 + 2)

        self.assertEqual(partida._lance_minimo(estado["leilao"]), 85_000)
        with self.assertRaisesRegex(partida.ErroDeRegra, "R\\$ 85.000"):
            partida.dar_lance(estado, 2, 80_000, agora=T0 + 3)

    def test_lance_no_fim_estica_o_relogio(self):
        estado = partida.dar_lance(aberto(), 2, 50_000, agora=T0 + 2)
        self.assertEqual(estado["prazo_vez"], T0 + 12)

        estado = partida.dar_lance(estado, 3, 60_000, agora=T0 + 11)
        self.assertEqual(estado["prazo_vez"], T0 + 16)

    def test_lance_depois_do_fim_nao_entra(self):
        estado = aberto()

        with self.assertRaisesRegex(partida.ErroDeRegra, "Não há leilão"):
            partida.dar_lance(estado, 2, 50_000, agora=T0 + 13)


class FecharLeilaoTestes(unittest.TestCase):
    def test_maior_lance_leva_e_paga_imposto_sobre_a_tabela(self):
        estado = partida.dar_lance(aberto(), 2, 50_000, agora=T0 + 1)
        estado = partida.dar_lance(estado, 3, 60_000, agora=T0 + 2)
        estado = partida.dar_lance(estado, 2, 70_000, agora=T0 + 3)
        estado = fechar(estado)

        ana, bia, caio = estado["jogadores"]
        self.assertEqual(bia["caixa"], 2_000_000 - 70_000 - 2_800)
        self.assertEqual(ana["caixa"], 100_000 + 70_000)
        self.assertEqual(caio["caixa"], 2_000_000)
        self.assertEqual(estado["coletor"], 2_800)
        self.assertEqual(estado["propriedades"][str(ITAQUERA)]["dono"], 2)
        self.assertEqual(bia["placar"]["compras"], 1)
        self.assertEqual(ana["placar"]["arrecadado"], 70_000)

        # A vez volta para quem vendeu, com o prazo recomeçado.
        self.assertEqual(estado["fase"], partida.FASE_ROLAR)
        self.assertEqual(apoio.vez_de(estado), 1)
        self.assertIsNone(estado["leilao"])
        resultado = estado["ultimo_leilao"]
        self.assertEqual(
            {k: resultado[k] for k in ("comprador_id", "lance", "imposto", "coletor", "banco", "lances")},
            {"comprador_id": 2, "lance": 70_000, "imposto": 2_800, "coletor": 2_800, "banco": None, "lances": 3},
        )

    def test_sem_lance_o_banco_compra(self):
        estado = fechar(aberto())

        self.assertEqual(estado["jogadores"][0]["caixa"], 100_000 + 49_000)
        self.assertNotIn(str(ITAQUERA), estado["propriedades"])
        self.assertEqual(estado["coletor"], 0)
        self.assertEqual(estado["ultimo_leilao"]["banco"], 49_000)
        self.assertIsNone(estado["ultimo_leilao"]["comprador_id"])
        self.assertEqual(estado["fase"], partida.FASE_ROLAR)

    def test_melhorias_vao_junto_com_a_casa(self):
        estado = aberto(nivel=2)
        # Valor investido: 140.000 + 2 × 35.000. O imposto continua na tabela.
        self.assertEqual(estado["leilao"]["oferta_do_banco"], 73_500)
        self.assertEqual(estado["leilao"]["imposto"], 2_800)

        estado = fechar(partida.dar_lance(estado, 3, 80_000, agora=T0 + 1))

        self.assertEqual(estado["propriedades"][str(ITAQUERA)], {"dono": 3, "nivel": 2})

    def test_morro_arrematado_avisa_o_bonus(self):
        estado = mesa_com_alguem_atras()
        estado["propriedades"]["1"] = {"dono": 2, "nivel": 0}  # Bia já tem Capão Redondo
        estado = partida.abrir_leilao(estado, 1, ITAQUERA, agora=T0)
        estado = fechar(partida.dar_lance(estado, 2, 50_000, agora=T0 + 1))

        self.assertIn("morro", apoio.tipos_do_log(estado))


class SaidaDuranteLeilaoTestes(unittest.TestCase):
    def test_quem_vende_sai_e_o_leilao_acaba(self):
        estado = partida.dar_lance(aberto(), 2, 50_000, agora=T0 + 1)
        estado = partida.abandonar(estado, 1)

        self.assertIsNone(estado["leilao"])
        self.assertNotIn(str(ITAQUERA), estado["propriedades"])
        self.assertEqual(estado["jogadores"][1]["caixa"], 2_000_000)
        self.assertEqual(estado["fase"], partida.FASE_ROLAR)
        self.assertEqual(apoio.vez_de(estado), 2)
        self.assertIn("leilao_cancelado", apoio.tipos_do_log(estado))

    def test_quem_lidera_sai_e_o_lance_anterior_volta_a_valer(self):
        estado = partida.dar_lance(aberto(), 2, 50_000, agora=T0 + 1)
        estado = partida.dar_lance(estado, 3, 60_000, agora=T0 + 2)
        estado = partida.abandonar(estado, 3)

        self.assertEqual(partida._lance_minimo(estado["leilao"]), 60_000)
        estado = fechar(estado)
        self.assertEqual(estado["propriedades"][str(ITAQUERA)]["dono"], 2)
        self.assertEqual(estado["ultimo_leilao"]["lance"], 50_000)


class LeilaoNaTelaTestes(unittest.TestCase):
    def test_estado_publico_do_leilao(self):
        estado = partida.abrir_leilao(mesa_com_alguem_atras(), 1, ITAQUERA)
        estado = partida.dar_lance(estado, 3, 50_000)

        leilao = partida.estado_publico(estado, 2)["leilao"]

        self.assertEqual(leilao["lider_id"], 3)
        self.assertEqual(leilao["lance_atual"], 50_000)
        self.assertEqual(leilao["minimo"], 60_000)
        self.assertGreater(leilao["ms_restantes"], 10_000)

    def test_quem_pode_leiloar_e_por_que_nao(self):
        estado = mesa_com_alguem_atras()

        self.assertEqual(partida.estado_publico(estado, 1)["leilao_disponivel"], {"pode": True, "motivo": None})
        bia = partida.estado_publico(estado, 2)["leilao_disponivel"]
        self.assertFalse(bia["pode"])
        self.assertIn("não tem propriedade", bia["motivo"])

    def test_estado_antigo_ganha_os_campos_do_leilao(self):
        estado = mesa_com_alguem_atras()
        estado["versao"] = 9
        for chave in ("leilao", "ultimo_leilao"):
            del estado[chave]
        for jogador in estado["jogadores"]:
            del jogador["leiloou_na_rodada"]

        estado = partida.abrir_leilao(estado, 1, ITAQUERA, agora=T0)

        self.assertEqual(estado["versao"], partida.VERSAO_DO_ESTADO)
        self.assertEqual(estado["fase"], partida.FASE_LEILAO)


if __name__ == "__main__":
    unittest.main()

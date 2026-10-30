"""Modo dev: definir o próprio caixa, andar quantas casas quiser e ir direto
a uma casa. O servidor só deixa usar com MODO_DEV ligado; aqui é o motor."""

import unittest

from engine import partida
from tests.engine import apoio


class CaixaDevTestes(unittest.TestCase):
    def test_define_o_caixa_e_avisa_a_mesa(self):
        estado = partida.definir_caixa(apoio.criar_estado(), 1, 7_500_000)

        self.assertEqual(estado["jogadores"][0]["caixa"], 7_500_000)
        self.assertEqual(estado["jogadores"][0]["placar"]["arrecadado"], 0)
        linha = estado["log"][-1]
        self.assertEqual(linha["tipo"], "dev")
        self.assertIn("[dev]", linha["texto"])

    def test_vale_fora_da_vez(self):
        estado = partida.definir_caixa(apoio.criar_estado(), 2, 10)

        self.assertEqual(estado["jogadores"][1]["caixa"], 10)

    def test_valor_invalido_e_recusado(self):
        for valor in (-1, "100", True, partida.CAIXA_DEV_MAXIMO + 1):
            with self.subTest(valor=valor), self.assertRaises(partida.ErroDeRegra):
                partida.definir_caixa(apoio.criar_estado(), 1, valor)

    def test_caixa_novo_quita_o_aluguel_em_liquidacao(self):
        estado = apoio.criar_estado(caixa=100)
        estado["propriedades"]["2"] = {"dono": 2, "nivel": 0}
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}
        estado = apoio.rolar(estado)  # cai em Itaquera sem caixa: liquidação
        self.assertEqual(estado["fase"], partida.FASE_LIQUIDACAO_ALUGUEL)

        estado = partida.definir_caixa(estado, 1, 500_000)

        self.assertIsNone(estado["aluguel_pendente"])
        self.assertEqual(estado["jogadores"][0]["caixa"], 500_000 - 28_000)
        self.assertEqual(apoio.vez_de(estado), 2)


class AndarDevTestes(unittest.TestCase):
    def test_anda_o_numero_escolhido_e_resolve_a_casa(self):
        estado = partida.rolar(apoio.criar_estado(posicao=10), 1, passos=7)  # 10 -> 3, Casa do Imposto

        self.assertEqual(estado["jogadores"][0]["posicao"], 3)
        movimento = estado["ultimo_movimento"]
        self.assertTrue(movimento["dev"])
        self.assertEqual((movimento["dados"], movimento["passos"]), ([], 7))
        # Passou pelo Início (4) no caminho: salário.
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_300_000)
        linha = next(l for l in estado["log"] if l["tipo"] == "dado")
        self.assertIn("[dev]", linha["texto"])
        self.assertIn("andou 7 casas", linha["texto"])

    def test_numero_fora_do_limite_e_recusado(self):
        for passos in (0, partida.PASSOS_DEV_MAXIMOS + 1, 2.5):
            with self.subTest(passos=passos), self.assertRaises(partida.ErroDeRegra):
                partida.rolar(apoio.criar_estado(), 1, passos=passos)

    def test_so_na_propria_vez_e_antes_de_rolar(self):
        with self.assertRaisesRegex(partida.ErroDeRegra, "Não é sua vez"):
            partida.rolar(apoio.criar_estado(), 2, passos=3)


class IrDevTestes(unittest.TestCase):
    def test_vai_direto_e_resolve_a_casa_sem_salario(self):
        estado = partida.rolar(apoio.criar_estado(posicao=10), 1, destino=36)  # Casa do Ganho

        self.assertEqual(estado["jogadores"][0]["posicao"], 36)
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000_000 + 200_000)
        movimento = estado["ultimo_movimento"]
        self.assertFalse(movimento["deu_a_volta"])
        # O feixe do portal leva o peão na tela, mas não é o Portal de verdade.
        self.assertEqual(movimento["portal"]["destino"], 36)
        self.assertNotIn("portal", apoio.tipos_do_log(estado))
        self.assertIn("foi direto para Casa do Ganho", next(l for l in estado["log"] if l["tipo"] == "dado")["texto"])

    def test_ir_para_terreno_livre_abre_a_compra(self):
        estado = partida.rolar(apoio.criar_estado(), 1, destino=2)  # Itaquera

        self.assertEqual(estado["fase"], partida.FASE_COMPRA)
        self.assertEqual(estado["compra_pendente"]["casa"], 2)

    def test_casa_inexistente_e_recusada(self):
        for destino in (-1, 40, "3"):
            with self.subTest(destino=destino), self.assertRaises(partida.ErroDeRegra):
                partida.rolar(apoio.criar_estado(), 1, destino=destino)


if __name__ == "__main__":
    unittest.main()

import unittest

from tests.engine import apoio

AO_PASSAR = {"portal": {"dispara_ao_passar": True}}


class CasaPortalTestes(unittest.TestCase):
    def test_parar_no_portal_teleporta_para_a_casa_sorteada(self):
        estado = apoio.rolar(apoio.criar_estado(posicao=14), escolhas=[30])  # 14 -> 13 -> 12

        movimento = estado["ultimo_movimento"]
        self.assertEqual(movimento["portal"], {"casa": 12, "apos": 2, "destino": 30, "passou_pelo_inicio": True})
        self.assertEqual(estado["jogadores"][0]["posicao"], 30)
        self.assertIn("portal", apoio.tipos_do_log(estado))

    def test_destino_depois_do_inicio_paga_o_salario(self):
        # Do Portal (12) para a frente: 11, 10... o Início (4)... e a casa 0.
        estado = apoio.rolar(apoio.criar_estado(posicao=14), escolhas=[0])

        self.assertTrue(estado["ultimo_movimento"]["deu_a_volta"])
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_300_000)
        linha = next(l for l in estado["log"] if l["tipo"] == "portal")
        self.assertIn("depois do Início: R$ 300.000 de salário", linha["texto"])

    def test_destino_no_proprio_inicio_paga_o_salario(self):
        estado = apoio.rolar(apoio.criar_estado(posicao=14), escolhas=[4])

        self.assertEqual(estado["jogadores"][0]["posicao"], 4)
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_300_000)

    def test_destino_antes_do_inicio_nao_paga_salario(self):
        # Casa 5 fica entre o Portal e o Início: o salto não cruza a largada.
        estado = apoio.rolar(apoio.criar_estado(posicao=14), escolhas=[5])

        self.assertFalse(estado["ultimo_movimento"]["deu_a_volta"])
        self.assertFalse(estado["ultimo_movimento"]["portal"]["passou_pelo_inicio"])
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_000_000)
        linha = next(l for l in estado["log"] if l["tipo"] == "portal")
        self.assertNotIn("salário", linha["texto"])

    def test_por_padrao_quem_so_passa_pelo_portal_nao_e_teleportado(self):
        estado = apoio.rolar(apoio.criar_estado(posicao=14), dados=(1, 2), escolhas=[30])

        self.assertIsNone(estado["ultimo_movimento"]["portal"])
        self.assertEqual(estado["jogadores"][0]["posicao"], 11)


class PortalAoPassarTestes(unittest.TestCase):
    """A regra escrita ao pé da letra: `portal.dispara_ao_passar` ligado."""

    def test_passar_pelo_portal_anda_dali_os_passos_que_faltavam(self):
        with apoio.balanceamento(**AO_PASSAR):
            estado = apoio.rolar(apoio.criar_estado(posicao=14), dados=(1, 2), escolhas=[30])

        self.assertEqual(estado["ultimo_movimento"]["portal"]["apos"], 2)
        self.assertEqual(estado["jogadores"][0]["posicao"], 29)

    def test_um_teleporte_por_jogada(self):
        # Sai do portal em 13 e o passo que falta cai no portal de novo: fica.
        with apoio.balanceamento(**AO_PASSAR):
            estado = apoio.rolar(apoio.criar_estado(posicao=14), dados=(1, 2), escolhas=[13])

        self.assertEqual(estado["jogadores"][0]["posicao"], 12)
        self.assertEqual(apoio.tipos_do_log(estado).count("portal"), 1)

    def test_salario_conta_o_trecho_depois_do_portal(self):
        with apoio.balanceamento(**AO_PASSAR):
            estado = apoio.rolar(apoio.criar_estado(posicao=14), dados=(1, 2), escolhas=[5])

        self.assertEqual(estado["jogadores"][0]["posicao"], 4)
        self.assertTrue(estado["ultimo_movimento"]["deu_a_volta"])
        self.assertEqual(estado["jogadores"][0]["caixa"], 2_300_000)


if __name__ == "__main__":
    unittest.main()

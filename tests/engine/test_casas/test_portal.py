import unittest

from tests.engine import apoio

AO_PASSAR = {"portal": {"dispara_ao_passar": True}}


class CasaPortalTestes(unittest.TestCase):
    def test_parar_no_portal_teleporta_para_a_casa_sorteada(self):
        estado = apoio.rolar(apoio.criar_estado(posicao=14), escolhas=[30])  # 14 -> 13 -> 12

        movimento = estado["ultimo_movimento"]
        self.assertEqual(movimento["portal"], {"casa": 12, "apos": 2, "destino": 30})
        self.assertEqual(estado["jogadores"][0]["posicao"], 30)
        self.assertIn("portal", apoio.tipos_do_log(estado))

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

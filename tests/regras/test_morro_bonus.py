"""Bônus do Morro: as casas de favela (o grupo barato) cobram mais aluguel
quanto mais delas o mesmo dono tem — 2 casas 1,2×, 3 casas 1,4×, 4 casas
1,8× e 5 casas 2,0×, em todas elas."""

import unittest

from engine import partida
from tests.engine import apoio

#: As cinco casas do Morro no tabuleiro, Itaquera (aluguel-base 28.000) primeiro.
MORRO = [2, 1, 20, 38, 39]
ITAQUERA = "2"


def com_morro(casas, dono=2, caixa_de_quem_cai=2_000_000):
    estado = apoio.criar_estado(caixa=2_000_000)
    estado["jogadores"][0]["caixa"] = caixa_de_quem_cai
    for indice in MORRO[:casas]:
        estado["propriedades"][str(indice)] = {"dono": dono, "nivel": 0}
    return estado


class BonusDoMorroTestes(unittest.TestCase):
    def test_aluguel_cresce_com_as_casas_do_morro(self):
        esperado = {1: 28_000, 2: 33_600, 3: 39_200, 4: 50_400, 5: 56_000}
        for casas, aluguel in esperado.items():
            with self.subTest(casas=casas):
                publico = partida.estado_publico(com_morro(casas), 1)
                self.assertEqual(publico["propriedades"][ITAQUERA]["aluguel"], aluguel)

    def test_quem_cai_paga_o_aluguel_com_o_bonus(self):
        # Sem caixa para comprar Itaquera (140.000), paga o aluguel de 3 casas.
        estado = apoio.rolar(com_morro(3, caixa_de_quem_cai=100_000))  # Praça (4) -> Itaquera (2)

        self.assertEqual(estado["jogadores"][0]["caixa"], 100_000 - 39_200)
        self.assertEqual(estado["jogadores"][1]["caixa"], 2_000_000 + 39_200)
        # A janela do aluguel conta que o Morro encareceu a conta.
        linha = next(l for l in estado["log"] if l["tipo"] == "aluguel")
        self.assertEqual(linha["dados"]["morro"], 1.4)

    def test_casa_fora_do_morro_nao_ganha_bonus(self):
        estado = com_morro(5)
        estado["propriedades"]["6"] = {"dono": 2, "nivel": 0}  # Mooca, média: 280.000

        publico = partida.estado_publico(estado, 1)

        self.assertEqual(publico["propriedades"]["6"]["aluguel"], 56_000)
        self.assertIsNone(publico["propriedades"]["6"]["morro"])

    def test_cada_dono_conta_as_proprias_casas(self):
        estado = com_morro(2)  # Itaquera e Capão Redondo do jogador 2
        for indice in (20, 38, 39):
            estado["propriedades"][str(indice)] = {"dono": 1, "nivel": 0}

        publico = partida.estado_publico(estado, 1)

        self.assertEqual(publico["propriedades"][ITAQUERA]["morro"], {"casas": 2, "multiplicador": 1.2})
        self.assertEqual(publico["propriedades"]["20"]["morro"], {"casas": 3, "multiplicador": 1.4})

    def test_bonus_multiplica_o_aluguel_com_melhorias(self):
        estado = com_morro(3)
        estado["propriedades"][ITAQUERA]["nivel"] = 2

        # 28.000 × (1 + 0,5 × 2) = 56.000, vezes 1,4.
        self.assertEqual(partida.estado_publico(estado, 1)["propriedades"][ITAQUERA]["aluguel"], 78_400)

    def test_final_de_ano_soma_ao_bonus(self):
        estado = com_morro(3)
        estado["evento"] = {"tipo": "final_de_ano", "nome": "Evento de final de ano", "rodada": 1, "texto": ""}

        # 39.200 com mais 20%.
        self.assertEqual(partida.estado_publico(estado, 1)["propriedades"][ITAQUERA]["aluguel"], 47_040)

    def test_comprar_a_segunda_casa_do_morro_avisa_a_mesa(self):
        estado = apoio.criar_estado()
        estado["propriedades"]["1"] = {"dono": 1, "nivel": 0}  # já tem Capão Redondo
        estado = apoio.rolar(estado)  # cai em Itaquera, livre
        estado = partida.decidir_compra(estado, 1, True)

        linha = next(l for l in estado["log"] if l["tipo"] == "morro")
        self.assertIn("2 casas do Morro", linha["texto"])
        self.assertIn("1,2×", linha["texto"])

    def test_primeira_casa_do_morro_nao_avisa(self):
        estado = partida.decidir_compra(apoio.rolar(apoio.criar_estado()), 1, True)

        self.assertNotIn("morro", apoio.tipos_do_log(estado))

    def test_tabela_e_grupo_vem_do_balanceamento(self):
        with apoio.balanceamento(morro={"grupo": "media", "2": 3.0}):
            estado = apoio.criar_estado()
            estado["propriedades"]["6"] = {"dono": 2, "nivel": 0}
            estado["propriedades"]["7"] = {"dono": 2, "nivel": 0}
            estado["propriedades"][ITAQUERA] = {"dono": 2, "nivel": 0}
            publico = partida.estado_publico(estado, 1)

        self.assertEqual(publico["propriedades"]["6"]["aluguel"], 56_000 * 3)
        self.assertEqual(publico["propriedades"][ITAQUERA]["aluguel"], 28_000)


if __name__ == "__main__":
    unittest.main()

"""Quando um amigo aparece "em partida" (com o botão de assistir): partida
andando, com ele ainda na mesa e com a tela dela aberta agora. Partida
largada (ninguém consultando, o prazo da vez lá atrás), abandonada por ele ou
cuja tela ele fechou não conta."""

import json
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from engine import partida as motor
from server.social.amigos import JANELA_PRESENCA, PARTIDA_PARADA_SEGUNDOS, _jogando_nela, _presente

AGORA = 1_000_000.0


def linha(prazo_vez=AGORA + 20, fase=motor.FASE_ROLAR, abandonou=False):
    estado = {
        "fase": fase,
        "prazo_vez": prazo_vez,
        "jogadores": [
            {"jogador_id": 1, "abandonou": abandonou},
            {"jogador_id": 2, "abandonou": False},
        ],
    }
    return SimpleNamespace(estado=json.dumps(estado))


class AmigoEmPartidaTestes(unittest.TestCase):
    def test_partida_andando_com_ele_na_mesa(self):
        self.assertTrue(_jogando_nela(linha(), 1, agora=AGORA))

    def test_prazo_vencido_ha_pouco_ainda_conta(self):
        # A vez venceu e a próxima consulta ainda não chegou: segue andando.
        self.assertTrue(_jogando_nela(linha(prazo_vez=AGORA - 30), 1, agora=AGORA))

    def test_partida_largada_nao_conta(self):
        parada = linha(prazo_vez=AGORA - PARTIDA_PARADA_SEGUNDOS - 1)
        self.assertFalse(_jogando_nela(parada, 1, agora=AGORA))

    def test_partida_encerrada_nao_conta(self):
        self.assertFalse(_jogando_nela(linha(fase=motor.FASE_FIM), 1, agora=AGORA))

    def test_quem_abandonou_nao_esta_mais_nela(self):
        self.assertFalse(_jogando_nela(linha(abandonou=True), 1, agora=AGORA))
        self.assertTrue(_jogando_nela(linha(abandonou=True), 2, agora=AGORA))

    def test_sem_partida_nao_conta(self):
        self.assertFalse(_jogando_nela(None, 1, agora=AGORA))



class PresencaNaSalaTestes(unittest.TestCase):
    AGORA = datetime(2026, 10, 30, 12, 0, 0)

    def sala(self, visto_em):
        return SimpleNamespace(participantes=[SimpleNamespace(jogador_id=1, visto_em=visto_em)])

    def test_com_a_tela_aberta_esta_na_sala(self):
        self.assertTrue(_presente(self.sala(self.AGORA - timedelta(seconds=8)), 1, agora=self.AGORA))

    def test_fechou_a_tela_ha_mais_que_a_janela_nao_esta(self):
        antiga = self.AGORA - JANELA_PRESENCA - timedelta(seconds=1)
        self.assertFalse(_presente(self.sala(antiga), 1, agora=self.AGORA))

    def test_sem_presenca_gravada_ou_sem_cadeira_nao_esta(self):
        self.assertFalse(_presente(self.sala(None), 1, agora=self.AGORA))
        self.assertFalse(_presente(self.sala(self.AGORA), 2, agora=self.AGORA))


if __name__ == "__main__":
    unittest.main()

"""Perfil: o nome que a mesa vê pode repetir; o nome de usuário (login), com
o qual se entra na conta e se acha um amigo, não."""

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from server.db.models import Jogador
from server.db.session import Base
from server.salas.gerenciador import ErroDeSala, atualizar_perfil, jogador_por_login


class PerfilTestes(unittest.TestCase):
    def setUp(self):
        self.motor = create_engine("sqlite://")
        Base.metadata.create_all(self.motor)
        self.sessao = Session(self.motor)
        self.ana = Jogador(nome="Ana", login="ana", token="t-ana")
        self.bia = Jogador(nome="Bia", login="bia", token="t-bia")
        self.sessao.add_all([self.ana, self.bia])
        self.sessao.commit()

    def tearDown(self):
        self.sessao.close()
        self.motor.dispose()

    def test_troca_o_nome_de_usuario(self):
        atualizar_perfil(self.sessao, self.ana, login="Ana_Nova")
        # Guardado em minúsculas: é assim que o login e a busca de amigo comparam.
        self.assertEqual(self.ana.login, "ana_nova")
        self.assertIs(jogador_por_login(self.sessao, "ANA_NOVA"), self.ana)
        self.assertIsNone(jogador_por_login(self.sessao, "ana"))

    def test_nome_de_usuario_de_outra_pessoa_e_recusado(self):
        with self.assertRaises(ErroDeSala) as erro:
            atualizar_perfil(self.sessao, self.ana, login="BIA")
        self.assertEqual(erro.exception.http, 409)
        self.assertEqual(self.ana.login, "ana")

    def test_mandar_o_proprio_nome_de_usuario_nao_e_erro(self):
        atualizar_perfil(self.sessao, self.ana, login="ana", nome="Aninha")
        self.assertEqual((self.ana.login, self.ana.nome), ("ana", "Aninha"))

    def test_nome_de_usuario_invalido_e_recusado(self):
        with self.assertRaises(ErroDeSala):
            atualizar_perfil(self.sessao, self.ana, login="a b")
        self.assertEqual(self.ana.login, "ana")

    def test_nome_para_jogadores_pode_repetir(self):
        atualizar_perfil(self.sessao, self.ana, nome="Bia")
        self.assertEqual(self.ana.nome, self.bia.nome)

    def test_sem_login_no_corpo_o_nome_de_usuario_fica(self):
        atualizar_perfil(self.sessao, self.ana, nome="Ana Clara")
        self.assertEqual(self.ana.login, "ana")


if __name__ == "__main__":
    unittest.main()

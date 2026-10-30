"""Convite para a sala: só o dono convida, só amigo é convidado, e o convite
some quando é respondido ou deixa de valer."""

import unittest
from datetime import datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from server.db.models import Amizade, ConviteSala, Jogador, Sala, SalaJogador, StatusAmizade, StatusSala
from server.db.session import Base
from server.salas.gerenciador import ErroDeSala
from server.social import convites_de_sala as convites


class ConviteDeSalaTestes(unittest.TestCase):
    def setUp(self):
        self.motor = create_engine("sqlite://")
        Base.metadata.create_all(self.motor)
        self.sessao = Session(self.motor)
        self.dono = Jogador(nome="Dono", login="dono", token="t-dono")
        self.amigo = Jogador(nome="Amigo", login="amigo", token="t-amigo")
        self.estranho = Jogador(nome="Estranho", login="estranho", token="t-estranho")
        self.sessao.add_all([self.dono, self.amigo, self.estranho])
        self.sessao.flush()
        self.sessao.add(Amizade(de_id=self.dono.id, para_id=self.amigo.id, status=StatusAmizade.ACEITA))
        self.sala = self.sala_de(self.dono, "SALA22")
        self.sessao.commit()

    def tearDown(self):
        self.sessao.close()
        self.motor.dispose()

    def sala_de(self, dono, codigo, lugares=4):
        sala = Sala(codigo=codigo, dono_id=dono.id, max_jogadores=lugares, seed=1)
        self.sessao.add(sala)
        self.sessao.flush()
        self.sessao.add(SalaJogador(sala_id=sala.id, jogador_id=dono.id, ordem=0))
        self.sessao.flush()
        self.sessao.refresh(sala)
        return sala

    def convites_do_amigo(self):
        return convites.notificacoes(self.sessao, self.amigo)["convites"]

    def test_convite_aparece_para_o_amigo(self):
        convites.convidar(self.sessao, self.sala, self.dono, self.amigo.id)
        [cartao] = self.convites_do_amigo()
        self.assertEqual(cartao["sala"], "SALA22")
        self.assertEqual(cartao["de"]["nome"], "Dono")
        self.assertEqual((cartao["jogadores"], cartao["lugares"]), (1, 4))

    def test_aceitar_entra_na_sala_e_o_convite_some(self):
        convites.convidar(self.sessao, self.sala, self.dono, self.amigo.id)
        [cartao] = self.convites_do_amigo()
        resposta = convites.aceitar(self.sessao, self.amigo, cartao["id"])
        self.assertEqual(resposta["codigo"], "SALA22")
        self.assertIn(self.amigo.id, [p.jogador_id for p in self.sala.participantes])
        self.assertEqual(self.convites_do_amigo(), [])

    def test_recusar_apaga_o_convite(self):
        convites.convidar(self.sessao, self.sala, self.dono, self.amigo.id)
        [cartao] = self.convites_do_amigo()
        convites.recusar(self.sessao, self.amigo, cartao["id"])
        self.assertEqual(self.convites_do_amigo(), [])
        self.assertNotIn(self.amigo.id, [p.jogador_id for p in self.sala.participantes])

    def test_so_o_dono_convida(self):
        self.sessao.add(Amizade(de_id=self.estranho.id, para_id=self.amigo.id, status=StatusAmizade.ACEITA))
        self.sessao.add(SalaJogador(sala_id=self.sala.id, jogador_id=self.estranho.id, ordem=1))
        self.sessao.commit()
        self.sessao.refresh(self.sala)
        with self.assertRaises(ErroDeSala) as erro:
            convites.convidar(self.sessao, self.sala, self.estranho, self.amigo.id)
        self.assertEqual(erro.exception.http, 403)

    def test_so_amigo_e_convidado(self):
        with self.assertRaises(ErroDeSala) as erro:
            convites.convidar(self.sessao, self.sala, self.dono, self.estranho.id)
        self.assertEqual(erro.exception.http, 403)

    def test_pedido_de_amizade_pendente_nao_vale_como_amigo(self):
        self.sessao.add(Amizade(de_id=self.dono.id, para_id=self.estranho.id))
        self.sessao.commit()
        with self.assertRaises(ErroDeSala):
            convites.convidar(self.sessao, self.sala, self.dono, self.estranho.id)

    def test_convidar_de_novo_renova_sem_duplicar(self):
        convites.convidar(self.sessao, self.sala, self.dono, self.amigo.id)
        convite = self.sessao.scalar(select(ConviteSala))
        convite.criado_em = datetime.now() - convites.VALIDADE / 2
        self.sessao.commit()
        [primeiro] = self.convites_do_amigo()
        convites.convidar(self.sessao, self.sala, self.dono, self.amigo.id)
        [segundo] = self.convites_do_amigo()
        self.assertEqual(primeiro["id"], segundo["id"])
        # A chave nova é o que faz o cartão fechado voltar à tela.
        self.assertNotEqual(primeiro["chave"], segundo["chave"])

    def test_convite_vencido_some(self):
        convites.convidar(self.sessao, self.sala, self.dono, self.amigo.id)
        convite = self.sessao.scalar(select(ConviteSala))
        convite_id = convite.id
        convite.criado_em = datetime.now() - convites.VALIDADE - convites.VALIDADE / 10
        self.sessao.commit()
        self.assertEqual(self.convites_do_amigo(), [])
        with self.assertRaises(ErroDeSala) as erro:
            convites.aceitar(self.sessao, self.amigo, convite_id)
        self.assertEqual(erro.exception.http, 404)

    def test_partida_comecou_o_convite_nao_vale(self):
        convites.convidar(self.sessao, self.sala, self.dono, self.amigo.id)
        [cartao] = self.convites_do_amigo()
        self.sala.status = StatusSala.EM_PARTIDA
        self.sessao.commit()
        with self.assertRaises(ErroDeSala) as erro:
            convites.aceitar(self.sessao, self.amigo, cartao["id"])
        self.assertEqual(erro.exception.mensagem, "A partida dessa sala já começou.")
        self.assertEqual(self.convites_do_amigo(), [])

    def test_quem_convidou_saiu_o_convite_some(self):
        convites.convidar(self.sessao, self.sala, self.dono, self.amigo.id)
        self.sessao.add(SalaJogador(sala_id=self.sala.id, jogador_id=self.estranho.id, ordem=1))
        self.sessao.commit()
        self.sessao.refresh(self.sala)
        assento = next(p for p in self.sala.participantes if p.jogador_id == self.dono.id)
        self.sala.participantes.remove(assento)
        self.sala.dono_id = self.estranho.id
        self.sessao.commit()
        self.assertEqual(self.convites_do_amigo(), [])

    def test_convite_de_outro_jogador_nao_e_meu(self):
        convites.convidar(self.sessao, self.sala, self.dono, self.amigo.id)
        [cartao] = self.convites_do_amigo()
        with self.assertRaises(ErroDeSala) as erro:
            convites.aceitar(self.sessao, self.estranho, cartao["id"])
        self.assertEqual(erro.exception.http, 404)

    def test_aceitar_sai_do_lobby_em_que_estava(self):
        outra = self.sala_de(self.amigo, "SALA33")
        self.sessao.commit()
        convites.convidar(self.sessao, self.sala, self.dono, self.amigo.id)
        [cartao] = self.convites_do_amigo()
        convites.aceitar(self.sessao, self.amigo, cartao["id"])
        self.sessao.refresh(outra)
        self.assertEqual(outra.participantes, [])

    def test_pedido_de_amizade_recebido_vira_notificacao(self):
        self.sessao.add(Amizade(de_id=self.estranho.id, para_id=self.amigo.id))
        self.sessao.commit()
        [pedido] = convites.notificacoes(self.sessao, self.amigo)["pedidos"]
        self.assertEqual((pedido["id"], pedido["login"]), (self.estranho.id, "estranho"))
        # Quem pediu não vê o próprio pedido como notificação.
        self.assertEqual(convites.notificacoes(self.sessao, self.estranho)["pedidos"], [])


if __name__ == "__main__":
    unittest.main()

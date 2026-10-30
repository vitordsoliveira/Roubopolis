"""Ponte entre o lobby (banco) e o motor (`engine/`).

Este módulo é o único lugar que conhece os dois lados. Ele lê o estado do
banco, entrega ao motor, e grava o que voltou. O motor continua sem saber
que existe banco; o banco continua sem saber que existe regra de jogo.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from engine import partida as motor
from engine.board.tabuleiro import carregar_tabuleiro
from engine.regras.balanceamento import carregar_balanceamento, grupo_do_morro
from engine.rng.gerador import gerar_semente
from server.config import Config
from server.db.models import Partida, Sala, StatusSala
from server.salas.gerenciador import ErroDeSala
from server.social import amigos, loja


@lru_cache(maxsize=1)
def frases_dos_eventos() -> dict:
    """As frases de sátira das janelas de evento (data/eventos/): as dos
    eventos temáticos e as das casas, por tipo de linha do log. Só texto — a
    tela busca uma vez ao abrir a partida, em vez de a cada consulta."""
    pasta = Config.DIR_DADOS / "eventos"
    frases = {}
    for chave, arquivo in (("tematicos", "tematicos.json"), ("casas", "mensagens_casas.json")):
        dados = json.loads((pasta / arquivo).read_text(encoding="utf-8"))
        frases[chave] = {tipo: lista for tipo, lista in dados.items() if not tipo.startswith("_")}
    return frases


def _erro(erro: motor.ErroDeRegra) -> ErroDeSala:
    """Traduz o erro do motor para o erro que as rotas já sabem devolver."""
    return ErroDeSala(erro.mensagem, http=erro.http)


def buscar_partida(sessao: Session, sala: Sala, *, bloquear: bool = False) -> Partida:
    consulta = select(Partida).where(Partida.sala_id == sala.id)
    if bloquear:
        # Serializa ações que leem e substituem o JSON completo da partida.
        consulta = consulta.with_for_update()
    linha = sessao.scalar(consulta)
    if linha is None:
        raise ErroDeSala("Esta sala ainda não começou a partida.", http=404)
    return linha


def _ler(linha: Partida) -> dict:
    return json.loads(linha.estado)


def _gravar(sessao: Session, linha: Partida, estado: dict) -> None:
    linha.estado = json.dumps(estado, ensure_ascii=False)
    sessao.commit()


def _encerrar_se_acabou(sessao: Session, sala: Sala, estado: dict) -> None:
    """Partida no fim: fecha a sala e paga créditos e estatísticas.

    O UPDATE condicional é o que garante que isso acontece UMA vez. Várias
    telas consultam o mesmo fim de partida, às vezes em processos diferentes
    do Passenger; só a primeira encontra a sala ainda em partida, e só ela
    premia. Vai na mesma transação que grava o estado.
    """
    if estado["fase"] != motor.FASE_FIM:
        return
    resultado = sessao.execute(
        update(Sala)
        .where(Sala.id == sala.id, Sala.status == StatusSala.EM_PARTIDA)
        .values(status=StatusSala.ENCERRADA, encerrada_em=datetime.now())
    )
    if resultado.rowcount == 1:
        loja.premiar(sessao, estado)


def _atualizar_tempo(sessao: Session, linha: Partida) -> dict:
    original = _ler(linha)
    estado = motor.atualizar_tempo(original)
    if estado == original:
        return estado
    # O prazo venceu e a consulta vai gravar: relê a linha travada antes. Um
    # lance de leilão pode ter entrado entre a leitura e aqui; gravar o
    # fechamento calculado sem ele apagaria o lance.
    sessao.refresh(linha, with_for_update=True)
    original = _ler(linha)
    estado = motor.atualizar_tempo(original)
    if estado != original:
        _gravar(sessao, linha, estado)
    return estado


def _exigir_lugar_ou_amizade(sessao: Session, sala: Sala, jogador) -> bool:
    """Quem não está sentado na mesa só assiste, e só se for amigo de alguém
    dela. Devolve se é espectador."""
    ids = [p.jogador_id for p in sala.participantes]
    if jogador.id in ids:
        return False
    if amigos.pode_assistir(sessao, jogador.id, ids):
        return True
    raise ErroDeSala("Só amigos de quem está na mesa podem assistir a esta partida.", http=403)


# --------------------------------------------------------------------------

def iniciar(sessao: Session, sala: Sala, jogador) -> dict:
    """Começa a partida. Só o dono, e só com todo mundo pronto."""
    if jogador.id != sala.dono_id:
        raise ErroDeSala("Só quem criou a sala pode começar.", http=403)

    if sala.status is StatusSala.EM_PARTIDA:
        # Clicar duas vezes não pode criar duas partidas.
        return estado_para(sessao, sala, jogador)

    if sala.status is not StatusSala.AGUARDANDO:
        raise ErroDeSala("Esta sala não está mais aguardando.", http=409)

    if len(sala.participantes) < Config.MIN_JOGADORES:
        raise ErroDeSala(f"Precisa de pelo menos {Config.MIN_JOGADORES} jogadores.")

    faltando = [p.jogador.nome for p in sala.participantes if not (p.pronto and p.personagem_id)]
    if faltando:
        raise ErroDeSala("Ainda não está todo mundo pronto: " + ", ".join(faltando))

    jogadores = [
        {
            "jogador_id": p.jogador_id,
            "nome": p.jogador.nome,
            "personagem": p.personagem.para_dict() if p.personagem else None,
            "foto": p.jogador.foto,
            # O dado e a casa da loja entram aqui: a partida inteira usa o
            # que cada um tinha equipado quando ela começou.
            "visual": loja.visual_do_jogador(sessao, p.jogador),
        }
        for p in sala.participantes
    ]

    # A semente da sala foi sorteada quando ela nasceu: guardá-la é o que
    # permite repetir a partida inteira depois.
    semente = sala.seed or gerar_semente()
    try:
        estado = motor.criar_partida(
            jogadores, semente=semente, tabuleiro=sala.tabuleiro, perfil=sala.perfil
        )
        # O sorteio da ordem acontece já: a tela mostra o resultado como
        # abertura da partida, e ninguém precisa clicar para isso.
        estado = motor.sortear_ordem(estado)
    except motor.ErroDeRegra as erro:
        raise _erro(erro)

    linha = sessao.scalar(select(Partida).where(Partida.sala_id == sala.id))
    if linha is None:
        linha = Partida(sala_id=sala.id, estado="{}")
        sessao.add(linha)

    sala.status = StatusSala.EM_PARTIDA
    _gravar(sessao, linha, estado)
    return _envelope(estado, jogador, sala)


def estado_para(sessao: Session, sala: Sala, jogador) -> dict:
    espectador = _exigir_lugar_ou_amizade(sessao, sala, jogador)
    linha = buscar_partida(sessao, sala)
    estado = _atualizar_tempo(sessao, linha)
    _encerrar_se_acabou(sessao, sala, estado)
    sessao.commit()
    return _envelope(estado, jogador, sala, espectador=espectador)


def _agir(sessao: Session, sala: Sala, jogador, fases: tuple[str, ...], acao) -> dict:
    """Uma ação do jogador da vez: trava a linha, aplica o prazo vencido e a
    ação do motor, e grava.

    Se o prazo venceu antes de a resposta chegar, a ação padrão já resolveu a
    decisão (recusou a compra, não arriscou...): a tela recebe o estado novo
    em vez de um erro sobre uma pergunta que não existe mais.
    """
    linha = buscar_partida(sessao, sala, bloquear=True)
    original = _ler(linha)
    estado_atual = motor.atualizar_tempo(original)
    if estado_atual != original and estado_atual["fase"] not in fases:
        _encerrar_se_acabou(sessao, sala, estado_atual)
        _gravar(sessao, linha, estado_atual)
        return _envelope(estado_atual, jogador, sala)
    try:
        estado = acao(estado_atual)
    except motor.ErroDeRegra as erro:
        raise _erro(erro)
    _encerrar_se_acabou(sessao, sala, estado)
    _gravar(sessao, linha, estado)
    return _envelope(estado, jogador, sala)


def rolar(sessao: Session, sala: Sala, jogador) -> dict:
    return _agir(sessao, sala, jogador, (motor.FASE_ROLAR,), lambda e: motor.rolar(e, jogador.id))


def decidir_compra(sessao: Session, sala: Sala, jogador, comprar: bool) -> dict:
    return _agir(sessao, sala, jogador, (motor.FASE_COMPRA,),
                 lambda e: motor.decidir_compra(e, jogador.id, comprar))


def decidir_compra_jogador(sessao: Session, sala: Sala, jogador, comprar: bool) -> dict:
    """Decide a compra oferecida ao jogador ao cair numa propriedade alheia."""
    return _agir(sessao, sala, jogador, (motor.FASE_COMPRA_JOGADOR,),
                 lambda e: motor.decidir_compra_jogador(e, jogador.id, comprar))


def decidir_melhoria(sessao: Session, sala: Sala, jogador, melhorar: bool) -> dict:
    """Decide a melhoria oferecida ao jogador ao cair na própria casa."""
    return _agir(sessao, sala, jogador, (motor.FASE_MELHORIA,),
                 lambda e: motor.decidir_melhoria(e, jogador.id, melhorar))


def vender_propriedade_para_aluguel(sessao: Session, sala: Sala, jogador, casa_indice: int) -> dict:
    return _agir(sessao, sala, jogador, (motor.FASE_LIQUIDACAO_ALUGUEL,),
                 lambda e: motor.vender_propriedade_para_aluguel(e, jogador.id, casa_indice))


def decidir_coringa(sessao: Session, sala: Sala, jogador, arriscar: bool) -> dict:
    return _agir(sessao, sala, jogador, (motor.FASE_CORINGA,),
                 lambda e: motor.decidir_coringa(e, jogador.id, arriscar))


def decidir_reconstrucao(sessao: Session, sala: Sala, jogador, casa_indice: int | None) -> dict:
    return _agir(sessao, sala, jogador, (motor.FASE_RECONSTRUCAO,),
                 lambda e: motor.decidir_reconstrucao(e, jogador.id, casa_indice))


def escolher_prejuizo(sessao: Session, sala: Sala, jogador, casa_indice: int) -> dict:
    return _agir(sessao, sala, jogador, (motor.FASE_PREJUIZO,),
                 lambda e: motor.escolher_prejuizo(e, jogador.id, casa_indice))


def vender_no_bonus(sessao: Session, sala: Sala, jogador, casa_indice: int | None) -> dict:
    return _agir(sessao, sala, jogador, (motor.FASE_ROLAR, motor.FASE_BONUS_BANCO),
                 lambda e: motor.vender_no_bonus(e, jogador.id, casa_indice))


def abrir_leilao(sessao: Session, sala: Sala, jogador, casa_indice: int) -> dict:
    return _agir(sessao, sala, jogador, (motor.FASE_ROLAR,),
                 lambda e: motor.abrir_leilao(e, jogador.id, casa_indice))


def dar_lance(sessao: Session, sala: Sala, jogador, valor: int) -> dict:
    """Lance no leilão aberto — de qualquer um da mesa, não só de quem tem a
    vez. Se o relógio fechou o leilão antes do lance chegar, a tela recebe o
    resultado em vez de um erro."""
    return _agir(sessao, sala, jogador, (motor.FASE_LEILAO,),
                 lambda e: motor.dar_lance(e, jogador.id, valor))


def _exigir_modo_dev() -> None:
    if not Config.MODO_DEV:
        raise ErroDeSala("O modo dev está desligado neste servidor (MODO_DEV em server/config.py).", http=403)


def dev_definir_caixa(sessao: Session, sala: Sala, jogador, valor: int) -> dict:
    """Trapaça de teste: o caixa vira `valor`, a qualquer momento da partida."""
    _exigir_modo_dev()
    fases = motor.FASES_QUE_ACEITAM_LEILAO + (motor.FASE_LEILAO,)
    return _agir(sessao, sala, jogador, fases, lambda e: motor.definir_caixa(e, jogador.id, valor))


def dev_andar(sessao: Session, sala: Sala, jogador, passos: int) -> dict:
    """Trapaça de teste: anda `passos` casas no lugar dos dados."""
    _exigir_modo_dev()
    return _agir(sessao, sala, jogador, (motor.FASE_ROLAR,), lambda e: motor.rolar(e, jogador.id, passos=passos))


def dev_ir(sessao: Session, sala: Sala, jogador, casa_indice: int) -> dict:
    """Trapaça de teste: vai direto à casa, que se resolve como numa parada."""
    _exigir_modo_dev()
    return _agir(sessao, sala, jogador, (motor.FASE_ROLAR,), lambda e: motor.rolar(e, jogador.id, destino=casa_indice))


def abandonar(sessao: Session, sala: Sala, jogador) -> dict:
    """Sair no meio da partida. Os outros ficam sabendo pelo log."""
    linha = buscar_partida(sessao, sala, bloquear=True)
    try:
        estado = motor.abandonar(_ler(linha), jogador.id)
    except motor.ErroDeRegra as erro:
        raise _erro(erro)

    _encerrar_se_acabou(sessao, sala, estado)
    _gravar(sessao, linha, estado)
    return _envelope(estado, jogador, sala)


# --------------------------------------------------------------------------

def _envelope(estado: dict, jogador, sala: Sala, *, espectador: bool = False) -> dict:
    """O que a tela recebe: o estado da partida mais o que ela precisa para
    desenhar — tabuleiro, alguns números do balanceamento e as cores dos
    itens da loja que a mesa está usando."""
    bal = carregar_balanceamento(estado["perfil"])
    acabou = estado["fase"] == motor.FASE_FIM
    return {
        "codigo": sala.codigo,
        "espectador": espectador,
        "partida": motor.estado_publico(estado, jogador.id),
        "tabuleiro": carregar_tabuleiro(estado["tabuleiro"]).para_dict(),
        "regras": {
            "segundos_por_turno": bal["tempo"]["segundos_por_turno"],
            "dados": bal["dados"],
            # Para a tela explicar cada casa com o número que o motor cobra.
            "casas": {
                "ganho": bal["casas"]["ganho"],
                "roubo": bal["casas"]["roubo"],
                "coringa_ganho": bal["coringa"]["ganho"],
                "coringa_perda": bal["coringa"]["perda"],
                "reconstrucao_desconto": bal["reconstrucao"]["desconto"],
                "prejuizo_ao_coletor": bal["prejuizo"]["ao_coletor"],
                "prejuizo_do_caixa": bal["prejuizo"]["sem_propriedade_perde_do_caixa"],
                "prisao_rodadas": bal["prisao"]["rodadas_presas"],
                "portal_ao_passar": bool(bal.get("portal", {}).get("dispara_ao_passar", False)),
                "salario": bal["dinheiro"]["salario_ao_passar_inicio"],
            },
            "morro": {
                "grupo": grupo_do_morro(bal),
                # Quantas casas do Morro -> multiplicador, para as regras da tela.
                "multiplicadores": {k: v for k, v in bal.get("morro", {}).items() if k.isdigit()},
            },
            "leilao": {
                "segundos": bal["tempo"]["segundos_de_leilao"],
                "imposto_sobre_tabela": bal["leilao"]["imposto_sobre_tabela"],
                "compra_do_banco": bal["leilao"]["compra_do_banco_sem_lance"],
                "so_abaixo_de": bal["leilao"].get("so_abaixo_de_percentual_da_media"),
                "rodadas_entre": bal["leilao"].get("rodadas_entre_leiloes", 1),
            },
        },
        "cosmeticos": loja.visuais_da_partida(estado),
        # Se o /dev on do chat vale neste servidor (MODO_DEV em server/config.py).
        "modo_dev": Config.MODO_DEV,
        # Os créditos que esta pessoa ganhou — a comemoração mostra.
        "recompensa": loja.recompensa(estado, jogador.id) if acabou and not espectador else None,
    }

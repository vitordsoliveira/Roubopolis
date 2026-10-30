"""Loja de visuais e os créditos que pagam por eles.

O catálogo — preço, nome, cores — é dado (data/loja/catalogo.json). O banco
só guarda o que cada um comprou (`ItemDoJogador`) e o que está equipado
(colunas `dado_equipado` e `casa_equipada` do jogador).

Os créditos entram no fim de cada partida (`premiar`) e saem numa compra.
O visual equipado vai para dentro da partida quando ela começa, e aí a mesa
inteira vê o dado e as casas de cada um.
"""

from __future__ import annotations

import json
from functools import lru_cache

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.config import Config
from server.db.models import ItemDoJogador, Jogador
from server.salas.gerenciador import ErroDeSala

ARQUIVO_CATALOGO = Config.DIR_DADOS / "loja" / "catalogo.json"

#: Tipo do item -> coluna do jogador que guarda o equipado.
COLUNA_EQUIPADA = {"dado": "dado_equipado", "casa": "casa_equipada"}


def _sem_comentarios(valor):
    if isinstance(valor, dict):
        return {k: _sem_comentarios(v) for k, v in valor.items() if not k.startswith("_")}
    if isinstance(valor, list):
        return [_sem_comentarios(v) for v in valor]
    return valor


@lru_cache(maxsize=1)
def catalogo() -> dict:
    dados = _sem_comentarios(json.loads(ARQUIVO_CATALOGO.read_text(encoding="utf-8")))
    slugs = [item["slug"] for item in dados["itens"]]
    if len(slugs) != len(set(slugs)):
        raise ValueError(f"{ARQUIVO_CATALOGO.name}: há slug repetido no catálogo.")
    return dados


def item(slug: str | None) -> dict | None:
    return next((i for i in catalogo()["itens"] if i["slug"] == slug), None)


def recompensa(estado: dict, jogador_id: int) -> int:
    """Créditos do fim da partida: vitória ou participação. Quem abandonou
    não leva nada — sair no meio não pode compensar."""
    jogador = next((j for j in estado.get("jogadores", []) if j["jogador_id"] == jogador_id), None)
    if jogador is None or jogador.get("abandonou"):
        return 0
    tabela = catalogo().get("recompensas", {})
    if jogador_id in estado.get("vencedores", []):
        return int(tabela.get("vitoria", 0))
    return int(tabela.get("participacao", 0))


def premiar(sessao: Session, estado: dict) -> None:
    """Conta a partida no perfil de cada jogador e paga os créditos.

    Quem chama garante que isto roda uma vez só por partida (ver
    `server/salas/partida.py`). As somas são feitas no banco, e não em
    Python, para não brigar com uma compra na loja feita no mesmo instante.
    """
    vencedores = set(estado.get("vencedores", []))
    for jogador in estado.get("jogadores", []):
        jid = jogador["jogador_id"]
        venceu = jid in vencedores
        sessao.execute(
            update(Jogador)
            .where(Jogador.id == jid)
            .values(
                partidas_jogadas=Jogador.partidas_jogadas + 1,
                vitorias=Jogador.vitorias + (1 if venceu else 0),
                derrotas=Jogador.derrotas + (0 if venceu else 1),
                coins=Jogador.coins + recompensa(estado, jid),
            )
            .execution_options(synchronize_session=False)
        )


def _comprados(sessao: Session, jogador: Jogador) -> set[str]:
    return set(sessao.scalars(select(ItemDoJogador.item).where(ItemDoJogador.jogador_id == jogador.id)))


def _tem(sessao: Session, jogador: Jogador, dados_item: dict) -> bool:
    return dados_item["preco"] <= 0 or dados_item["slug"] in _comprados(sessao, jogador)


def estado_da_loja(sessao: Session, jogador: Jogador) -> dict:
    """O que a tela da loja desenha: créditos, catálogo e o que é de quem."""
    comprados = _comprados(sessao, jogador)
    equipados = {tipo: getattr(jogador, coluna) for tipo, coluna in COLUNA_EQUIPADA.items()}
    itens = []
    for dados_item in catalogo()["itens"]:
        tipo = dados_item["tipo"]
        meu = dados_item["preco"] <= 0 or dados_item["slug"] in comprados
        equipado = equipados.get(tipo) == dados_item["slug"] or (
            dados_item.get("padrao") and not item(equipados.get(tipo))
        )
        itens.append({**dados_item, "meu": meu, "equipado": bool(equipado)})
    return {
        "creditos": jogador.coins,
        "recompensas": catalogo().get("recompensas", {}),
        "itens": itens,
    }


def comprar(sessao: Session, jogador: Jogador, slug: str) -> dict:
    dados_item = item(slug)
    if dados_item is None:
        raise ErroDeSala("Esse item não está à venda.", http=404)
    if _tem(sessao, jogador, dados_item):
        raise ErroDeSala("Você já tem esse item.", http=409)

    # Desconto condicional no banco: dois cliques seguidos não compram com o
    # mesmo crédito, e o saldo nunca fica negativo.
    resultado = sessao.execute(
        update(Jogador)
        .where(Jogador.id == jogador.id, Jogador.coins >= dados_item["preco"])
        .values(coins=Jogador.coins - dados_item["preco"])
        .execution_options(synchronize_session=False)
    )
    if resultado.rowcount != 1:
        sessao.rollback()
        faltam = dados_item["preco"] - jogador.coins
        raise ErroDeSala(f"Faltam {max(faltam, 1)} créditos. Ganhe partidas para juntar mais.", http=409)
    sessao.add(ItemDoJogador(jogador_id=jogador.id, item=slug))
    try:
        sessao.commit()
    except IntegrityError:
        sessao.rollback()
        raise ErroDeSala("Você já tem esse item.", http=409)
    sessao.refresh(jogador)
    return estado_da_loja(sessao, jogador)


def equipar(sessao: Session, jogador: Jogador, slug: str) -> dict:
    dados_item = item(slug)
    if dados_item is None:
        raise ErroDeSala("Esse item não existe.", http=404)
    if not _tem(sessao, jogador, dados_item):
        raise ErroDeSala("Compre o item antes de equipar.", http=403)
    # O padrão vira nulo: se o catálogo trocar de padrão, quem nunca escolheu
    # nada acompanha.
    valor = None if dados_item.get("padrao") else slug
    setattr(jogador, COLUNA_EQUIPADA[dados_item["tipo"]], valor)
    sessao.commit()
    return estado_da_loja(sessao, jogador)


def visual_do_jogador(sessao: Session, jogador: Jogador) -> dict:
    """O que o jogador leva para dentro da partida: só item que existe e é dele."""
    visual = {}
    for tipo, coluna in COLUNA_EQUIPADA.items():
        dados_item = item(getattr(jogador, coluna))
        valido = dados_item and dados_item["tipo"] == tipo and _tem(sessao, jogador, dados_item)
        visual[tipo] = dados_item["slug"] if valido else None
    return visual


def resumo_visual(jogador: Jogador) -> dict:
    """Nome e cores do que o jogador está usando — para os amigos verem."""
    resumo = {}
    for tipo, coluna in COLUNA_EQUIPADA.items():
        dados_item = item(getattr(jogador, coluna)) or next(
            (i for i in catalogo()["itens"] if i["tipo"] == tipo and i.get("padrao")), None
        )
        resumo[tipo] = (
            {"slug": dados_item["slug"], "nome": dados_item["nome"], "visual": dados_item["visual"]}
            if dados_item else None
        )
    return resumo


def visuais_da_partida(estado: dict) -> dict:
    """Cores de cada item usado na mesa, por slug. A tela da partida não
    conhece o catálogo: recebe só o que vai desenhar."""
    usados = {
        slug
        for jogador in estado.get("jogadores", [])
        for slug in (jogador.get("visual") or {}).values()
        if slug
    }
    return {slug: {"tipo": i["tipo"], "nome": i["nome"], "visual": i["visual"]} for slug in usados if (i := item(slug))}

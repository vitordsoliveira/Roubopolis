"""Cria as tabelas (colunas) e popula os dados fixos (linhas).

Uso, a partir da raiz do projeto:

    python -m server.db.criar_banco              # cria o que falta e popula
    python -m server.db.criar_banco --listar     # só mostra o que já existe
    python -m server.db.criar_banco --so-linhas  # não mexe em tabela, só popula
    python -m server.db.criar_banco --recriar    # APAGA TUDO e cria de novo

`create_all` só cria o que ainda não existe: rodar duas vezes é seguro e não
apaga nada. As linhas de `personagem` saem de data/personagens/personagens.json
e são atualizadas pelo slug, então editar o JSON e rodar de novo sincroniza.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# Permite rodar como `python server/db/criar_banco.py`, sem o -m.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from server.config import Config
from server.db.models import TODOS_OS_MODELOS, Personagem
from server.db.session import Base, descrever_alvo, obter_engine, obter_fabrica

ARQUIVO_PERSONAGENS = Config.DIR_DADOS / "personagens" / "personagens.json"


# --------------------------------------------------------------------------
# diagnóstico
# --------------------------------------------------------------------------

def _explicar_erro_de_conexao(erro: Exception) -> str:
    """Traduz o erro cru do driver para o que de fato precisa ser feito."""
    texto = str(erro)
    codigo = None
    args = getattr(getattr(erro, "orig", None), "args", None)
    if args and isinstance(args[0], int):
        codigo = args[0]

    if codigo == 1130 or "is not allowed to connect" in texto:
        return (
            "O banco recusou ESTE computador (erro 1130).\n"
            "  O usuário e a senha estão certos — o que falta é liberar o IP.\n"
            "  No painel da hospedagem, procure 'MySQL Remoto' / 'Remote MySQL'\n"
            "  e adicione o IP público desta máquina (veja em https://meuip.com.br).\n"
            "  Durante o desenvolvimento dá para liberar '%' (qualquer IP)."
        )
    if codigo == 1045 or "Access denied" in texto:
        return (
            "Usuário ou senha recusados (erro 1045).\n"
            "  Confira a DATABASE_URL no .env. Caractere especial na senha precisa\n"
            "  de percent-encoding: @ vira %40, # vira %23, : vira %3A, / vira %2F."
        )
    if codigo == 1049 or "Unknown database" in texto:
        return "O banco informado na DATABASE_URL não existe. Crie-o no painel primeiro."
    if codigo in (2003, 2002) or "Can't connect" in texto:
        return (
            "Não consegui alcançar o host na porta indicada.\n"
            "  Verifique se o endereço e a porta estão certos e se a hospedagem\n"
            "  aceita conexão externa ao MySQL (muitas bloqueiam a 3306 por padrão)."
        )
    return texto


def conferir_conexao() -> bool:
    print(f"Alvo: {descrever_alvo()}")
    try:
        engine = obter_engine()
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
            versao = ".".join(str(n) for n in (engine.dialect.server_version_info or ()))
        print(f"Conectado. {engine.dialect.name} {versao}\n".rstrip() + "\n")
        return True
    except (OperationalError, SQLAlchemyError) as erro:
        print("\nNÃO FOI POSSÍVEL CONECTAR\n")
        print(_explicar_erro_de_conexao(erro))
        print()
        return False


# --------------------------------------------------------------------------
# colunas
# --------------------------------------------------------------------------

def garantir_tabelas() -> None:
    """Cria tabelas ausentes e completa colunas antigas sem apagar dados."""
    engine = obter_engine()
    Base.metadata.create_all(engine)
    _atualizar_colunas_jogador(engine)


def criar_tabelas(recriar: bool = False) -> None:
    engine = obter_engine()

    if recriar:
        print("--recriar: apagando as tabelas do Roubodopolis...")
        Base.metadata.drop_all(engine)
        print("  tabelas apagadas.")

    antes = set(inspect(engine).get_table_names())
    garantir_tabelas()
    depois = set(inspect(engine).get_table_names())

    for modelo in TODOS_OS_MODELOS:
        nome = modelo.__tablename__
        marca = "criada" if nome in depois - antes else "já existia"
        colunas = len(modelo.__table__.columns)
        print(f"  [{marca:>10}] {nome:<14} {colunas} colunas")


def garantir_colunas() -> None:
    """Adiciona colunas novas em tabelas que já existem.

    `create_all` só cria tabela que falta — ele NÃO mexe em tabela existente.
    Sem isto, acrescentar um campo ao model funcionaria numa base nova e
    falharia em produção com "Unknown column", que é o pior momento para
    descobrir. Roda a cada `criar_banco` e é seguro repetir: só age no que
    está faltando.
    """
    engine = obter_engine()
    inspetor = inspect(engine)
    tabelas = set(inspetor.get_table_names())

    for modelo in TODOS_OS_MODELOS:
        nome = modelo.__tablename__
        if nome not in tabelas:
            continue  # acabou de ser criada pelo create_all, já veio completa

        existentes = {coluna["name"] for coluna in inspetor.get_columns(nome)}
        for coluna in modelo.__table__.columns:
            if coluna.name in existentes:
                continue

            tipo = coluna.type.compile(engine.dialect)
            # Coluna nova em tabela com linhas não pode ser NOT NULL sem
            # default: as linhas antigas não teriam o que gravar ali.
            padrao = getattr(coluna.server_default, "arg", None)
            trecho_padrao = f" DEFAULT {padrao}" if isinstance(padrao, str) else ""
            nulo = "NULL" if coluna.nullable or not trecho_padrao else "NOT NULL"

            ddl = f"ALTER TABLE `{nome}` ADD COLUMN `{coluna.name}` {tipo} {nulo}{trecho_padrao}"
            with engine.begin() as conexao:
                conexao.execute(text(ddl))
            print(f"  [{'+ coluna':>10}] {nome}.{coluna.name} ({tipo})")


def _atualizar_colunas_jogador(engine) -> None:
    """Completa instalações antigas sem apagar jogadores ou partidas."""
    colunas = {coluna["name"] for coluna in inspect(engine).get_columns("jogador")}
    faltantes = {
        "login": "VARCHAR(64)",
        "senha_hash": "VARCHAR(256)",
        "partidas_jogadas": "INTEGER NOT NULL DEFAULT 0",
        "vitorias": "INTEGER NOT NULL DEFAULT 0",
        "derrotas": "INTEGER NOT NULL DEFAULT 0",
    }
    with engine.begin() as conexao:
        for nome, tipo in faltantes.items():
            if nome not in colunas:
                conexao.execute(text(f"ALTER TABLE jogador ADD COLUMN {nome} {tipo}"))
                print(f"  [     criada] jogador.{nome}")
        if "login" not in colunas:
            if engine.dialect.name == "sqlite":
                conexao.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_jogador_login ON jogador (login)"))
            else:
                conexao.execute(text("CREATE UNIQUE INDEX uq_jogador_login ON jogador (login)"))


# --------------------------------------------------------------------------
# linhas
# --------------------------------------------------------------------------

def popular_personagens() -> None:
    if not ARQUIVO_PERSONAGENS.exists():
        print(f"  AVISO: {ARQUIVO_PERSONAGENS} não encontrado, pulando personagens.")
        return

    dados = json.loads(ARQUIVO_PERSONAGENS.read_text(encoding="utf-8"))
    lista = dados.get("personagens", [])

    with obter_fabrica()() as sessao:
        existentes = {p.slug: p for p in sessao.scalars(select(Personagem))}
        vistos = set()

        for item in lista:
            slug = item["slug"]
            vistos.add(slug)
            alvo = existentes.get(slug)
            acao = "atualizado" if alvo else "inserido"
            if alvo is None:
                alvo = Personagem(slug=slug)
                sessao.add(alvo)

            alvo.nome = item["nome"]
            alvo.descricao = item.get("descricao")
            alvo.cor = item.get("cor", "#ffd93d")
            alvo.sprite = item.get("sprite")
            alvo.passiva = item.get("passiva")
            alvo.ordem = item.get("ordem", 0)
            alvo.ativo = True
            print(f"  [{acao:>10}] personagem  {slug}")

        # Quem saiu do JSON é desativado, nunca apagado: pode haver partida
        # antiga apontando para ele.
        for slug, antigo in existentes.items():
            if slug not in vistos and antigo.ativo:
                antigo.ativo = False
                print(f"  [{'desativado':>10}] personagem  {slug}")

        sessao.commit()


def popular() -> None:
    popular_personagens()


# --------------------------------------------------------------------------
# relatório
# --------------------------------------------------------------------------

def listar() -> None:
    engine = obter_engine()
    tabelas = set(inspect(engine).get_table_names())
    print("Tabelas do Roubodopolis:")
    with engine.connect() as conexao:
        for modelo in TODOS_OS_MODELOS:
            nome = modelo.__tablename__
            if nome not in tabelas:
                print(f"  {nome:<14} NÃO EXISTE")
                continue
            total = conexao.execute(text(f"SELECT COUNT(*) FROM `{nome}`")).scalar()
            print(f"  {nome:<14} {total} linha(s)")


def gerar_seed() -> int:
    """Semente para o rng do engine. Aqui só para deixar o import explícito."""
    return random.randint(1, 2_147_483_647)


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cria as tabelas e popula os dados fixos.")
    parser.add_argument("--recriar", action="store_true", help="APAGA as tabelas e cria de novo")
    parser.add_argument("--so-linhas", action="store_true", help="não mexe em tabela, só popula")
    parser.add_argument("--listar", action="store_true", help="só mostra o que já existe")
    args = parser.parse_args(argv)

    print("=" * 62)
    print("  ROUBODOPOLIS — preparação do banco")
    print("=" * 62)

    if not conferir_conexao():
        return 1

    if args.listar:
        listar()
        return 0

    if args.recriar:
        alvo = descrever_alvo()
        print(f"Isto vai APAGAR as tabelas de {alvo} e perder os dados.")
        if input("Digite APAGAR para confirmar: ").strip() != "APAGAR":
            print("Cancelado.")
            return 1

    if not args.so_linhas:
        print("Colunas:")
        criar_tabelas(recriar=args.recriar)
        garantir_colunas()
        print()

    print("Linhas:")
    popular()
    print()

    listar()
    print("\nPronto. Agora rode:  python run.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

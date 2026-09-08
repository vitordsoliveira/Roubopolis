"""O tabuleiro: lê o JSON e responde perguntas sobre as casas.

O motor não sabe desenhar nada. Ele só sabe que existem N casas em ordem,
que cada uma tem um tipo, e como andar de uma para outra. As coordenadas
`x`/`y` vêm junto porque a tela precisa delas, mas o motor as ignora.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_TABULEIROS = RAIZ / "data" / "tabuleiros"


@dataclass(frozen=True)
class Casa:
    indice: int
    x: int
    y: int
    tipo: str
    nome: str
    grupo: str | None = None
    preco: int | None = None
    easter_egg: str | None = None

    @property
    def e_propriedade(self) -> bool:
        return self.tipo == "propriedade"

    def para_dict(self) -> dict:
        d = {
            "i": self.indice,
            "x": self.x,
            "y": self.y,
            "tipo": self.tipo,
            "nome": self.nome,
        }
        if self.grupo:
            d["grupo"] = self.grupo
        if self.preco is not None:
            d["preco"] = self.preco
        if self.easter_egg:
            d["easter_egg"] = self.easter_egg
        return d


@dataclass(frozen=True)
class Tabuleiro:
    nome: str
    largura: int
    altura: int
    casas: tuple[Casa, ...]
    grupos: dict

    def __len__(self) -> int:
        return len(self.casas)

    def casa(self, indice: int) -> Casa:
        return self.casas[indice % len(self.casas)]

    def avancar(self, de: int, passos: int) -> int:
        """Nova posição depois de andar `passos`, dando a volta no tabuleiro."""
        return (de + passos) % len(self.casas)

    def passou_pelo_inicio(self, de: int, passos: int) -> bool:
        """Se o trajeto cruzou a casa 0. Ainda não há prêmio por isso — a
        especificação não define salário de volta —, mas o motor já sabe
        responder quando a regra existir."""
        return de + passos >= len(self.casas)

    def propriedades_do_grupo(self, grupo: str) -> tuple[Casa, ...]:
        return tuple(c for c in self.casas if c.grupo == grupo)

    def para_dict(self) -> dict:
        return {
            "nome": self.nome,
            "largura": self.largura,
            "altura": self.altura,
            "grupos": self.grupos,
            "casas": [c.para_dict() for c in self.casas],
        }


@lru_cache(maxsize=8)
def carregar_tabuleiro(nome: str = "vila_original") -> Tabuleiro:
    arquivo = DIR_TABULEIROS / f"{nome}.json"
    if not arquivo.exists():
        raise FileNotFoundError(f"Tabuleiro não encontrado: {arquivo}")

    dados = json.loads(arquivo.read_text(encoding="utf-8"))

    casas = []
    for bruto in dados["casas"]:
        casas.append(
            Casa(
                indice=bruto["i"],
                x=bruto["x"],
                y=bruto["y"],
                tipo=bruto["tipo"],
                nome=bruto["nome"],
                grupo=bruto.get("grupo"),
                preco=bruto.get("preco"),
                easter_egg=bruto.get("easter_egg"),
            )
        )

    # A ordem do arquivo é a ordem de caminhada. Se alguém reordenar as casas
    # sem reordenar os índices, o peão anda errado — melhor falhar aqui.
    for esperado, casa in enumerate(casas):
        if casa.indice != esperado:
            raise ValueError(
                f"{arquivo.name}: casa na posição {esperado} tem i={casa.indice}. "
                "Os índices precisam ser 0,1,2… na ordem em que o peão anda."
            )

    return Tabuleiro(
        nome=dados["nome"],
        largura=dados["largura"],
        altura=dados["altura"],
        casas=tuple(casas),
        grupos={k: v for k, v in dados.get("grupos", {}).items() if not k.startswith("_")},
    )

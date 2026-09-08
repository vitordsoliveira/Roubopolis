"""Carrega os números do jogo de `data/balanceamento/`.

Devolve o JSON como dicionário mesmo, de propósito: assim acrescentar um
valor novo ao arquivo não exige mexer aqui. Quem lê escreve
`bal["dinheiro"]["caixa_inicial"]`, que diz de onde o número veio.

As chaves começadas com `_` são comentários do arquivo e são descartadas.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DIR_BALANCEAMENTO = RAIZ / "data" / "balanceamento"


def _sem_comentarios(valor):
    """Tira as chaves de documentação (`_sobre`, `_leia_isto`, …)."""
    if isinstance(valor, dict):
        return {k: _sem_comentarios(v) for k, v in valor.items() if not k.startswith("_")}
    if isinstance(valor, list):
        return [_sem_comentarios(v) for v in valor]
    return valor


@lru_cache(maxsize=8)
def carregar_balanceamento(perfil: str = "padrao") -> dict:
    arquivo = DIR_BALANCEAMENTO / f"{perfil}.json"
    if not arquivo.exists():
        raise FileNotFoundError(f"Perfil de balanceamento não encontrado: {arquivo}")
    return _sem_comentarios(json.loads(arquivo.read_text(encoding="utf-8")))


def multiplicador_do_morro(bal: dict, quantidade: int) -> float:
    """1,0 até ter 2 becos; daí em diante segue a tabela, e o maior degrau
    vale para tudo acima dele."""
    # As chaves do morro são a quantidade de becos; `grupo` é texto e fica
    # de fora da tabela numérica.
    tabela = {
        int(k): float(v)
        for k, v in bal.get("morro", {}).items()
        if k.isdigit()
    }
    if not tabela or quantidade < min(tabela):
        return 1.0
    degrau = max(k for k in tabela if k <= quantidade)
    return tabela[degrau]


def grupo_do_morro(bal: dict) -> str:
    return bal.get("morro", {}).get("grupo", "barata")

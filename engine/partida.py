"""Motor da partida: sorteio, rolagem, movimento, compra e casas de evento.

Regras deste arquivo:

- Ele não conhece Flask, banco nem rede. Recebe o estado (um dicionário
  puro, que vira JSON sem tradução) e devolve o estado novo.
- Todo sorteio passa pelo `Gerador`, e o estado guarda em que ponto da
  sequência a partida está. Com a semente, a partida inteira se repete.
- Toda regra recusa em voz alta: ação fora de hora levanta `ErroDeRegra`
  com uma mensagem que pode ir direto para a tela.

O jogador pode comprar um terreno livre onde parou ou, ao cair numa propriedade
de outro jogador, comprá-la dele pelo valor investido (tabela + melhorias) ou
pagar aluguel. Ao cair na própria casa, o dono pode subir um nível, e quem
passa pelo Início recebe salário. As casas de evento (Ganho, Roubo, Coletor,
Portal, Prisão, Reconstrução, Prejuízo e Coringa), os eventos temáticos,
sorteados no começo das rodadas, o bônus do Morro e o leilão também moram
aqui. Todos os valores vêm do perfil de balanceamento. O desafio ainda não
faz parte do motor.
"""

from __future__ import annotations

import copy
import time

from engine.board.tabuleiro import carregar_tabuleiro
from engine.regras.balanceamento import carregar_balanceamento, grupo_do_morro, multiplicador_do_morro
from engine.rng.gerador import Gerador

#: v10: leilão (e quem já leiloou em que rodada).
VERSAO_DO_ESTADO = 10

FASE_SORTEIO = "sorteio_ordem"
FASE_ROLAR = "aguardando_rolagem"
FASE_COMPRA = "decidindo_compra"
FASE_COMPRA_JOGADOR = "decidindo_compra_jogador"
FASE_LIQUIDACAO_ALUGUEL = "liquidando_para_aluguel"
FASE_MELHORIA = "decidindo_melhoria"
FASE_CORINGA = "decidindo_coringa"
FASE_RECONSTRUCAO = "decidindo_reconstrucao"
FASE_PREJUIZO = "escolhendo_prejuizo"
FASE_BONUS_BANCO = "decidindo_bonus_banco"
FASE_LEILAO = "leiloando"
FASE_FIM = "encerrada"

#: Decisões em aberto. Passar a vez limpa todas: nenhuma sobrevive ao turno.
PENDENCIAS = (
    "compra_pendente",
    "aluguel_pendente",
    "melhoria_pendente",
    "coringa_pendente",
    "reconstrucao_pendente",
    "prejuizo_pendente",
    "leilao",
)

#: O que o placar do fim de partida conta de cada jogador.
PLACAR_VAZIO = {"arrecadado": 0, "aluguel_recebido": 0, "aluguel_pago": 0, "compras": 0, "melhorias": 0}

#: Os eventos temáticos, na ordem das regras, com o nome que a mesa lê.
EVENTOS_TEMATICOS = {
    "colheita_ruim": "A colheita foi ruim",
    "baile_na_vila": "Baile na vila",
    "final_de_ano": "Evento de final de ano",
    "presidente": "O Presidente passou aqui",
    "bonus_do_banco": "Bônus do banco",
}


class ErroDeRegra(Exception):
    """Ação que a regra não permite. A mensagem vai direto ao jogador."""

    def __init__(self, mensagem: str, http: int = 400):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.http = http


# --------------------------------------------------------------------------
# apoio
# --------------------------------------------------------------------------

def _reais(valor: float) -> str:
    return "R$ " + f"{int(round(valor)):,}".replace(",", ".")


def _porcento(fracao: float) -> str:
    return f"{round(fracao * 100)}%"


def _vezes(multiplicador: float) -> str:
    return f"{multiplicador:.1f}".replace(".", ",") + "×"


def _gerador(estado: dict) -> Gerador:
    return Gerador(estado["semente"], estado.get("consumidos", 0))


def _guardar_gerador(estado: dict, gerador: Gerador) -> None:
    estado["consumidos"] = gerador.consumidos


def _log(estado: dict, tipo: str, texto: str, jogador_id: int | None = None, dados: dict | None = None) -> None:
    # O número de cada linha é o que deixa a tela saber o que é novidade: o
    # log chega cortado, então contar linhas não serve.
    estado["log_n"] = estado.get("log_n", 0) + 1
    linha = {"n": estado["log_n"], "tipo": tipo, "texto": texto, "jogador_id": jogador_id}
    if dados:
        # O que a tela precisa para contar a linha do ponto de vista de quem
        # olha, sem ter de ler o texto.
        linha["dados"] = dados
    estado["log"].append(linha)
    # O log só serve para a tela contar o que aconteceu; manter os últimos
    # basta e evita o estado crescer sem limite dentro do banco.
    del estado["log"][:-80]


def _jogador_da_vez(estado: dict) -> dict:
    return estado["jogadores"][estado["vez"]]


def _jogador_por_id(estado: dict, jogador_id: int) -> dict:
    for j in estado["jogadores"]:
        if j["jogador_id"] == jogador_id:
            return j
    raise ErroDeRegra("Você não está nesta partida.", http=403)


def _exigir_vez(estado: dict, jogador_id: int) -> dict:
    jogador = _jogador_por_id(estado, jogador_id)
    if _jogador_da_vez(estado)["jogador_id"] != jogador_id:
        raise ErroDeRegra(f"Não é sua vez — quem joga é {_jogador_da_vez(estado)['nome']}.", http=409)
    return jogador


def _vivos(estado: dict) -> list[dict]:
    return [j for j in estado["jogadores"] if not j["falido"]]


def _placar(jogador: dict) -> dict:
    return jogador.setdefault("placar", dict(PLACAR_VAZIO))


def _creditar(jogador: dict, valor: int, *, aluguel: bool = False) -> None:
    """Toda entrada de dinheiro passa por aqui: é o que o placar do fim de
    partida conta como arrecadado."""
    valor = int(valor)
    jogador["caixa"] += valor
    placar = _placar(jogador)
    placar["arrecadado"] += valor
    if aluguel:
        placar["aluguel_recebido"] += valor


def _debitar_ate_o_caixa(jogador: dict, valor: int) -> int:
    """Tira até `valor` do caixa, sem deixar negativo, e devolve quanto saiu.

    Casas e eventos que tiram dinheiro (Roubo, Coringa, colheita) param no
    que há em caixa: não abrem liquidação nem levam à falência. Só dívida
    com outro jogador — o aluguel — faz isso."""
    tirado = max(0, min(int(valor), jogador["caixa"]))
    jogador["caixa"] -= tirado
    return tirado


def _definir_prazo(estado: dict, agora: float | None = None) -> None:
    duracao = int(estado.get("segundos_por_turno", 0))
    estado["prazo_vez"] = (agora if agora is not None else time.time()) + duracao if duracao > 0 else None


def _observar_prazo_partida(estado: dict, agora: float | None = None) -> None:
    prazo = estado.get("prazo_partida")
    if prazo is None or estado.get("encerrar_apos_rodada") is not None:
        return
    instante = time.time() if agora is None else agora
    if instante >= prazo and estado["fase"] not in (FASE_SORTEIO, FASE_FIM):
        estado["encerrar_apos_rodada"] = estado["rodada"]
        _log(
            estado,
            "tempo_partida",
            f"O tempo da partida acabou. A rodada {estado['rodada']} será concluída antes do resultado.",
        )


def _patrimonio(estado: dict, jogador: dict) -> int:
    """Caixa mais o valor investido em cada propriedade (tabela + melhorias).

    Melhoria é investimento, não despesa: se ela saísse do patrimônio, quem
    melhorasse uma casa perderia pontos no placar final — e a simulação
    mostrou que ninguém ganhava fazendo isso.
    """
    tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
    valor_propriedades = sum(
        _valor_investido(estado, tabuleiro.casa(int(indice)), propriedade)
        for indice, propriedade in estado["propriedades"].items()
        if propriedade["dono"] == jogador["jogador_id"]
    )
    return int(jogador["caixa"] + valor_propriedades)


def _media_patrimonio(estado: dict) -> float:
    vivos = _vivos(estado)
    if not vivos:
        return 0.0
    return sum(_patrimonio(estado, j) for j in vivos) / len(vivos)


def _classificar(estado: dict) -> list[dict]:
    """A ordem do pódio: quem ficou de pé por patrimônio, depois quem saiu —
    quem saiu por último fica na frente. Patrimônio igual divide a posição."""
    ativos = sorted(_vivos(estado), key=lambda j: -_patrimonio(estado, j))
    fora = sorted(
        (j for j in estado["jogadores"] if j["falido"]),
        key=lambda j: -(j.get("saiu_em") or 0),
    )
    classificacao: list[dict] = []
    for i, jogador in enumerate(ativos):
        patrimonio = _patrimonio(estado, jogador)
        empatado = classificacao and classificacao[-1]["patrimonio"] == patrimonio
        classificacao.append({
            "jogador_id": jogador["jogador_id"],
            "posicao": classificacao[-1]["posicao"] if empatado else i + 1,
            "patrimonio": patrimonio,
            "fora": False,
        })
    for k, jogador in enumerate(fora):
        classificacao.append({
            "jogador_id": jogador["jogador_id"],
            "posicao": len(ativos) + k + 1,
            "patrimonio": 0,
            "fora": True,
        })
    return classificacao


def _encerrar_partida(estado: dict, motivo: str) -> dict:
    ativos = _vivos(estado)
    patrimonios = {str(j["jogador_id"]): _patrimonio(estado, j) for j in ativos}
    maior = max(patrimonios.values(), default=None)
    vencedores = [int(jogador_id) for jogador_id, valor in patrimonios.items() if valor == maior]
    estado["fase"] = FASE_FIM
    estado["prazo_vez"] = None
    estado["prazo_partida"] = None
    estado["encerrar_apos_rodada"] = None
    estado["motivo_fim"] = motivo
    estado["patrimonios_finais"] = patrimonios
    estado["vencedores"] = vencedores
    estado["evento"] = None
    for chave in PENDENCIAS:
        estado[chave] = None
    if motivo == "tempo":
        if len(vencedores) == 1:
            vencedor = next(j for j in ativos if j["jogador_id"] == vencedores[0])
            _log(estado, "fim", f"O tempo acabou. {vencedor['nome']} venceu com patrimônio de {_reais(maior or 0)}.", vencedor["jogador_id"])
        elif vencedores:
            nomes = ", ".join(j["nome"] for j in ativos if j["jogador_id"] in vencedores)
            _log(estado, "fim", f"O tempo acabou empatado entre {nomes}, com {_reais(maior or 0)} de patrimônio.")
        else:
            _log(estado, "fim", "O tempo acabou. Não há jogadores ativos.")
    else:
        if len(ativos) == 1:
            vencedor = ativos[0]
            vencedores = [vencedor["jogador_id"]]
            estado["vencedores"] = vencedores
            _log(estado, "fim", f"{vencedor['nome']} ficou de pé sozinho.", vencedor["jogador_id"])
        else:
            _log(estado, "fim", "A partida acabou sem jogadores ativos.")
    estado["classificacao"] = _classificar(estado)
    return estado


def _evento_ativo(estado: dict) -> dict | None:
    """O evento temático vale só na rodada em que foi sorteado."""
    evento = estado.get("evento")
    if evento and evento.get("rodada") == estado.get("rodada"):
        return evento
    return None


def _config_evento(estado: dict, tipo: str) -> dict:
    return carregar_balanceamento(estado["perfil"]).get("eventos", {}).get(tipo, {})


def _bonus_do_morro(estado: dict, casa, dono_id: int | None) -> tuple[float, int]:
    """Multiplicador do aluguel de uma casa do Morro, e quantas o dono tem.

    O Morro são as casas de favela: o grupo de `morro.grupo` no
    balanceamento (o barato). Quanto mais delas o mesmo dono junta, mais caro
    fica o aluguel de TODAS — 2 casas 1,2×, 3 casas 1,4×... De 5 para cima
    vale a última faixa da tabela. Fora do Morro, (1.0, 0).
    """
    bal = carregar_balanceamento(estado["perfil"])
    if dono_id is None or not casa.grupo or casa.grupo != grupo_do_morro(bal):
        return 1.0, 0
    tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
    quantidade = sum(
        1
        for indice, propriedade in estado["propriedades"].items()
        if propriedade["dono"] == dono_id and tabuleiro.casa(int(indice)).grupo == casa.grupo
    )
    return multiplicador_do_morro(bal, quantidade), quantidade


def _avisar_morro(estado: dict, jogador: dict, casa) -> None:
    """Conta à mesa quando a compra de uma casa do Morro liga ou aumenta o
    bônus de quem comprou."""
    multiplicador, quantidade = _bonus_do_morro(estado, casa, jogador["jogador_id"])
    if multiplicador > 1:
        _log(
            estado,
            "morro",
            f"{jogador['nome']} tem {quantidade} casas do Morro: o aluguel de todas elas é multiplicado por {_vezes(multiplicador)}.",
            jogador["jogador_id"],
        )


def _valor_aluguel(estado: dict, casa, propriedade: dict) -> int:
    """Aluguel-base sobre a tabela, mais um acréscimo linear por nível de
    melhoria, vezes o bônus do Morro. No evento de final de ano, a rodada
    inteira paga mais."""
    aluguel = carregar_balanceamento(estado["perfil"])["aluguel"]
    nivel = max(0, int(propriedade.get("nivel", 0)))
    valor = casa.preco * aluguel["base"] * (1 + aluguel["por_nivel_de_upgrade"] * nivel)
    valor *= _bonus_do_morro(estado, casa, propriedade.get("dono"))[0]
    evento = _evento_ativo(estado)
    if evento and evento["tipo"] == "final_de_ano":
        valor *= 1 + float(_config_evento(estado, "final_de_ano").get("aluguel_extra", 0))
    return int(round(valor))


def _valor_upgrade(estado: dict, casa) -> int:
    balanceamento = carregar_balanceamento(estado["perfil"])
    fracao = float(balanceamento.get("upgrade", {}).get("custo_por_nivel", 0))
    return int(round((casa.preco or 0) * fracao))


def _valor_investido(estado: dict, casa, propriedade: dict) -> int:
    """Preço de tabela mais o que já foi pago em melhorias.

    É o preço de quem compra a propriedade de outro jogador: as melhorias vão
    junto com a casa, então quem as pagou precisa receber por elas.
    """
    nivel = max(0, int(propriedade.get("nivel", 0)))
    return (casa.preco or 0) + nivel * _valor_upgrade(estado, casa)


def _niveis_maximos(estado: dict) -> int:
    return int(carregar_balanceamento(estado["perfil"])["aluguel"]["niveis_maximos"])


def _oferecer_melhoria(estado: dict, jogador: dict, casa, propriedade: dict, origem: str) -> bool:
    """Abre a decisão de subir um nível na casa onde o jogador está.

    Como no Business Tour, melhoria só acontece com o peão na casa: logo
    depois de comprá-la (`origem="compra"`) ou ao cair nela de novo
    (`origem="visita"`). Amarrada ao tabuleiro, ela vira a escolha "investir
    agora ou guardar o caixa", em vez de um botão que se aperta a qualquer vez
    em qualquer casa. Oferecida só na visita, seria rara demais: cada jogador
    cai na própria casa menos de uma vez por partida.
    """
    nivel = int(propriedade.get("nivel", 0))
    custo = _valor_upgrade(estado, casa)
    if nivel >= _niveis_maximos(estado) or custo <= 0 or jogador["caixa"] < custo:
        # Depois da compra o silêncio basta; na visita, a tela conta por que
        # não houve oferta.
        if origem == "visita":
            motivo = "já está no nível máximo" if nivel >= _niveis_maximos(estado) else "não tem caixa para melhorar"
            _log(estado, "melhoria", f"{casa.nome}: {motivo}.", jogador["jogador_id"])
        return False

    estado["fase"] = FASE_MELHORIA
    _definir_prazo(estado)
    estado["melhoria_pendente"] = {
        "casa": casa.indice,
        "jogador_id": jogador["jogador_id"],
        "origem": origem,
        "nivel": nivel,
        "custo": custo,
        "aluguel_atual": _valor_aluguel(estado, casa, propriedade),
        "aluguel_novo": _valor_aluguel(estado, casa, {**propriedade, "nivel": nivel + 1}),
    }
    _log(
        estado,
        "melhoria",
        f"{jogador['nome']} pode melhorar {casa.nome} para o nível {nivel + 1} por {_reais(custo)}.",
        jogador["jogador_id"],
    )
    return True


def decidir_melhoria(estado: dict, jogador_id: int, melhorar: bool) -> dict:
    """Aceita ou recusa subir um nível na casa própria onde o jogador parou."""
    estado = atualizar_tempo(estado)
    if estado["fase"] != FASE_MELHORIA or not estado.get("melhoria_pendente"):
        raise ErroDeRegra("Não há uma melhoria para decidir agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)
    pendente = estado["melhoria_pendente"]
    if pendente["jogador_id"] != jogador_id:
        raise ErroDeRegra("Essa melhoria pertence a outro jogador.", http=403)

    casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
    if melhorar:
        propriedade = estado["propriedades"].get(str(pendente["casa"]))
        if propriedade is None or propriedade["dono"] != jogador_id:
            raise ErroDeRegra("Essa propriedade não é mais sua.", http=409)
        if int(propriedade.get("nivel", 0)) != pendente["nivel"]:
            raise ErroDeRegra("Essa propriedade já mudou de nível.", http=409)
        if jogador["caixa"] < pendente["custo"]:
            raise ErroDeRegra(f"Você precisa de {_reais(pendente['custo'])} para essa melhoria.", http=409)
        jogador["caixa"] -= pendente["custo"]
        propriedade["nivel"] = pendente["nivel"] + 1
        _placar(jogador)["melhorias"] += 1
        _log(
            estado,
            "melhoria",
            f"{jogador['nome']} melhorou {casa.nome} para o nível {propriedade['nivel']} por {_reais(pendente['custo'])}.",
            jogador_id,
        )
    else:
        _log(estado, "melhoria", f"{jogador['nome']} deixou {casa.nome} como está.", jogador_id)

    return _concluir_jogada(estado, jogador)


def _valor_venda_banco(estado: dict, casa, propriedade: dict) -> int:
    """O banco paga uma fração do valor investido (tabela + melhorias)."""
    fracao = carregar_balanceamento(estado["perfil"])["banco"]["venda_ao_banco"]
    return int(round(_valor_investido(estado, casa, propriedade) * fracao))


def _cobrar_aluguel(estado: dict, pagador: dict, dono: dict, casa, propriedade: dict) -> int:
    aluguel = _valor_aluguel(estado, casa, propriedade)
    pagador["caixa"] -= aluguel
    _placar(pagador)["aluguel_pago"] += aluguel
    _creditar(dono, aluguel, aluguel=True)
    multiplicador = _bonus_do_morro(estado, casa, dono["jogador_id"])[0]
    evento = _evento_ativo(estado)
    final_de_ano = evento and evento["tipo"] == "final_de_ano"
    _log(
        estado,
        "aluguel",
        f"{pagador['nome']} pagou {_reais(aluguel)} de aluguel a {dono['nome']} por {casa.nome}.",
        pagador["jogador_id"],
        # A janela do aluguel muda com quem olha: quem pagou, quem recebeu
        # ou quem só viu. E conta por que ficou mais caro, quando ficou.
        dados={
            "dono_id": dono["jogador_id"],
            "casa": casa.indice,
            "valor": aluguel,
            "morro": multiplicador if multiplicador > 1 else None,
            "final_de_ano": (
                float(_config_evento(estado, "final_de_ano").get("aluguel_extra", 0)) if final_de_ano else None
            ),
        },
    )
    return aluguel


def _propriedades_de(estado: dict, jogador_id: int) -> list[tuple[int, dict]]:
    return [
        (int(indice), propriedade)
        for indice, propriedade in estado["propriedades"].items()
        if propriedade["dono"] == jogador_id
    ]


def _devolver_ao_banco(estado: dict, jogador_id: int) -> int:
    """Tira do jogador tudo o que é dele no tabuleiro. Devolve quantas eram."""
    devolvidas = [indice for indice, prop in estado["propriedades"].items() if prop["dono"] == jogador_id]
    for indice in devolvidas:
        del estado["propriedades"][indice]
    return len(devolvidas)


def _tirar_da_mesa(estado: dict, jogador: dict) -> None:
    """Marca quem saiu (falência ou abandono) e em que ordem: o pódio põe na
    frente quem durou mais."""
    jogador["falido"] = True
    jogador["preso"] = 0
    estado["saidas"] = estado.get("saidas", 0) + 1
    jogador["saiu_em"] = estado["saidas"]


def _falir(estado: dict, jogador: dict, credor: dict, divida: int) -> dict:
    """Aplica o caixa restante à dívida, devolve os imóveis ao banco e elimina."""
    pagamento_parcial = min(max(0, jogador["caixa"]), divida)
    jogador["caixa"] -= pagamento_parcial
    _placar(jogador)["aluguel_pago"] += pagamento_parcial
    if pagamento_parcial:
        _creditar(credor, pagamento_parcial, aluguel=True)
    devolvidas = _devolver_ao_banco(estado, jogador["jogador_id"])
    _tirar_da_mesa(estado, jogador)
    estado["aluguel_pendente"] = None
    estado["compra_pendente"] = None
    _log(
        estado,
        "falencia",
        f"{jogador['nome']} faliu sem conseguir pagar {_reais(divida)} de aluguel a {credor['nome']}. "
        f"Pagamento parcial: {_reais(pagamento_parcial)}; {devolvidas} propriedade(s) voltou(aram) ao banco.",
        jogador["jogador_id"],
    )
    return passar_turno(estado)


def _resolver_aluguel(estado: dict, pagador: dict, dono: dict, casa, propriedade: dict) -> dict:
    """Paga o aluguel, abre liquidação ou declara falência se não há ativos."""
    aluguel = _valor_aluguel(estado, casa, propriedade)
    if pagador["caixa"] >= aluguel:
        _cobrar_aluguel(estado, pagador, dono, casa, propriedade)
        return estado

    estado["compra_pendente"] = None
    ativos = _propriedades_de(estado, pagador["jogador_id"])
    if not ativos:
        return _falir(estado, pagador, dono, aluguel)

    estado["fase"] = FASE_LIQUIDACAO_ALUGUEL
    estado["aluguel_pendente"] = {
        "casa": casa.indice,
        "jogador_id": pagador["jogador_id"],
        "dono_id": dono["jogador_id"],
        "aluguel": aluguel,
        "divida": aluguel,
    }
    _definir_prazo(estado)
    _log(
        estado,
        "liquidacao",
        f"{pagador['nome']} precisa levantar {_reais(aluguel - max(0, pagador['caixa']))} para pagar o aluguel de {casa.nome}.",
        pagador["jogador_id"],
    )
    return estado


def _encerrar_liquidacao(estado: dict) -> dict:
    """Conclui a dívida se já há dinheiro ou declara falência sem ativos."""
    pendente = estado["aluguel_pendente"]
    pagador = _jogador_por_id(estado, pendente["jogador_id"])
    dono = _jogador_por_id(estado, pendente["dono_id"])
    if dono["falido"]:
        # O credor saiu da mesa no meio da cobrança: não há a quem pagar.
        _log(estado, "liquidacao", f"{dono['nome']} saiu da partida e a dívida de {pagador['nome']} foi perdoada.", pagador["jogador_id"])
        estado["aluguel_pendente"] = None
        return _concluir_jogada(estado, pagador)
    if pagador["caixa"] >= pendente["divida"]:
        casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
        propriedade = estado["propriedades"].get(str(pendente["casa"]))
        if propriedade is None or propriedade["dono"] != dono["jogador_id"]:
            raise ErroDeRegra("O dono desta propriedade mudou durante a liquidação.", http=409)
        _cobrar_aluguel(estado, pagador, dono, casa, propriedade)
        estado["aluguel_pendente"] = None
        return _concluir_jogada(estado, pagador)

    if not _propriedades_de(estado, pagador["jogador_id"]):
        return _falir(estado, pagador, dono, pendente["divida"])
    return estado


def vender_propriedade_para_aluguel(estado: dict, jogador_id: int, casa_indice: int) -> dict:
    """Vende ao banco uma propriedade escolhida para quitar aluguel pendente."""
    estado = atualizar_tempo(estado)
    if estado["fase"] != FASE_LIQUIDACAO_ALUGUEL or not estado.get("aluguel_pendente"):
        raise ErroDeRegra("Você não precisa vender propriedades agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)
    if estado["aluguel_pendente"]["jogador_id"] != jogador_id:
        raise ErroDeRegra("Essa dívida pertence a outro jogador.", http=403)
    if isinstance(casa_indice, bool) or not isinstance(casa_indice, int):
        raise ErroDeRegra("Escolha uma propriedade válida.")
    indice = str(casa_indice)
    propriedade = estado["propriedades"].get(indice)
    if propriedade is None or propriedade["dono"] != jogador_id:
        raise ErroDeRegra("Essa propriedade não é sua ou já foi vendida.", http=409)

    casa = carregar_tabuleiro(estado["tabuleiro"]).casa(casa_indice)
    if not casa.e_propriedade or casa.preco is None:
        raise ErroDeRegra("Essa casa não pode ser vendida ao banco.")

    valor = _valor_venda_banco(estado, casa, propriedade)
    _creditar(jogador, valor)
    del estado["propriedades"][indice]
    _log(estado, "venda", f"{jogador['nome']} vendeu {casa.nome} ao banco por {_reais(valor)} para pagar aluguel.", jogador_id)
    return _encerrar_liquidacao(estado)


# --------------------------------------------------------------------------
# estado gravado por uma versão anterior
# --------------------------------------------------------------------------

def _atualizar(estado: dict) -> dict:
    """Traz para o formato atual um estado gravado por um motor mais velho.

    A partida mora no banco como JSON: uma mesa que começou antes de uma
    mudança aqui volta com o formato antigo. Sem esta conversão, quem
    estava decidindo uma compra quando a compra saiu do jogo ficaria preso
    para sempre numa fase que não existe mais.
    """
    versao = estado.get("versao", 1)
    if versao >= VERSAO_DO_ESTADO:
        return estado

    estado = copy.deepcopy(estado)

    estava_comprando = False
    if versao < 3:
        # v1 -> v2: o tabuleiro encolheu; posse antiga não é compatível por índice.
        estava_comprando = estado.get("fase") == "decidindo_compra"
        for chave in ("propriedades", "compra_pendente", "ultimo_aluguel"):
            estado.pop(chave, None)

        total = len(carregar_tabuleiro(estado["tabuleiro"]))
        for jogador in estado["jogadores"]:
            jogador.pop("propriedades", None)
            jogador["posicao"] %= total

        # Estados anteriores à v3 não guardavam posse compatível com o mapa atual.
        estado["propriedades"] = {}
        estado["compra_pendente"] = None

    if versao < 4:
        bal = carregar_balanceamento(estado.get("perfil", "padrao"))
        estado["segundos_por_turno"] = int(
            estado.get("segundos_por_turno", bal["tempo"]["segundos_por_turno"])
        )
        _definir_prazo(estado)

    if versao < 6:
        estado.setdefault("aluguel_pendente", None)
        pendente = estado.get("compra_pendente")
        if estado.get("fase") == FASE_COMPRA_JOGADOR and pendente:
            pendente.setdefault("tipo", "jogador")
            if "aluguel" not in pendente:
                casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
                propriedade = estado.get("propriedades", {}).get(str(pendente["casa"]), {})
                pendente["aluguel"] = _valor_aluguel(estado, casa, propriedade)

    if versao < 7:
        bal = carregar_balanceamento(estado.get("perfil", "padrao"))
        estado["minutos_de_partida"] = int(
            estado.get("minutos_de_partida", bal["tempo"].get("minutos_de_partida", 0))
        )
        ativa = estado.get("fase") not in (FASE_SORTEIO, FASE_FIM)
        if "prazo_partida" not in estado:
            duracao = estado["minutos_de_partida"] * 60
            estado["prazo_partida"] = time.time() + duracao if ativa and duracao > 0 else None
        estado.setdefault("encerrar_apos_rodada", None)
        estado.setdefault("motivo_fim", None)
        estado.setdefault("vencedores", [])
        estado.setdefault("patrimonios_finais", {})

    if versao < 8:
        estado.setdefault("melhoria_pendente", None)

    if versao < 9:
        # Mesa que começou sem as casas de evento: o Coletor nasce vazio e o
        # placar conta só daqui para a frente.
        for chave in PENDENCIAS:
            estado.setdefault(chave, None)
        estado.setdefault("coletor", 0)
        estado.setdefault("evento", None)
        estado.setdefault("ultimo_coringa", None)
        estado.setdefault("classificacao", [])
        estado.setdefault("saidas", 0)
        estado.setdefault("log_n", 0)
        for jogador in estado["jogadores"]:
            jogador.setdefault("preso", 0)
            jogador.setdefault("reincidente", False)
            jogador.setdefault("placar", dict(PLACAR_VAZIO))
            jogador.setdefault("abandonou", False)
            jogador.setdefault("saiu_em", None)
            jogador.setdefault("visual", None)
        if estado.get("fase") == FASE_FIM and not estado["classificacao"]:
            estado["classificacao"] = _classificar(estado)

    if versao < 10:
        # Mesa que começou antes do leilão: ninguém leiloou ainda.
        estado.setdefault("leilao", None)
        estado.setdefault("ultimo_leilao", None)
        for jogador in estado["jogadores"]:
            jogador.setdefault("leiloou_na_rodada", None)

    estado["versao"] = VERSAO_DO_ESTADO
    if estava_comprando:
        # Quem decidia a compra já tinha andado: a vez segue adiante.
        estado = passar_turno(estado)
    return estado


# --------------------------------------------------------------------------
# criar
# --------------------------------------------------------------------------

def criar_partida(
    jogadores: list[dict],
    semente: int,
    tabuleiro: str = "vila_original",
    perfil: str = "padrao",
) -> dict:
    """`jogadores` vem do lobby: jogador_id, nome, personagem e o visual
    (dado e casa) que cada um equipou na loja.

    A ordem de jogada ainda NÃO está definida aqui — a partida nasce na fase
    de sorteio, e é o dado que decide quem começa.
    """
    if len(jogadores) < 2:
        raise ErroDeRegra("Precisa de pelo menos 2 jogadores para começar.")

    bal = carregar_balanceamento(perfil)
    caixa = bal["dinheiro"]["caixa_inicial"]
    indice_inicial = carregar_tabuleiro(tabuleiro).indice_inicial

    estado = {
        "versao": VERSAO_DO_ESTADO,
        "semente": int(semente),
        "consumidos": 0,
        "tabuleiro": tabuleiro,
        "perfil": perfil,
        "segundos_por_turno": int(bal["tempo"]["segundos_por_turno"]),
        "minutos_de_partida": int(bal["tempo"].get("minutos_de_partida", 0)),
        "prazo_vez": None,
        "prazo_partida": None,
        "encerrar_apos_rodada": None,
        "motivo_fim": None,
        "vencedores": [],
        "patrimonios_finais": {},
        "classificacao": [],
        "fase": FASE_SORTEIO,
        "rodada": 1,
        "vez": 0,
        "jogadores": [
            {
                "jogador_id": j["jogador_id"],
                "nome": j["nome"],
                "personagem": j.get("personagem"),
                "visual": j.get("visual"),
                "caixa": caixa,
                "posicao": indice_inicial,
                "falido": False,
                "abandonou": False,
                "saiu_em": None,
                "preso": 0,
                "reincidente": False,
                "placar": dict(PLACAR_VAZIO),
                "leiloou_na_rodada": None,
            }
            for j in jogadores
        ],
        "sorteio": [],
        "propriedades": {},
        **{chave: None for chave in PENDENCIAS},
        #: O que os impostos da partida juntaram. Quem pisa no Coletor leva.
        "coletor": 0,
        #: Evento temático da rodada (ver `_iniciar_rodada`).
        "evento": None,
        "ultimo_coringa": None,
        #: O último leilão que fechou, para a tela mostrar o resultado.
        "ultimo_leilao": None,
        "saidas": 0,
        #: Contador de rolagens. A tela usa para saber o que já encenou.
        "lances": 0,
        "ultimo_movimento": None,
        "log_n": 0,
        "log": [],
    }

    _log(estado, "inicio", f"A partida começou. Todo mundo com {_reais(caixa)} em caixa.")
    _log(estado, "sorteio", "Rolem os dados para ver quem começa.")
    return estado


# --------------------------------------------------------------------------
# 1. sorteio da ordem de jogada
# --------------------------------------------------------------------------

def _desempatar(grupo: list[dict], gerador: Gerador, faces: int, tentativa: int = 0) -> list[dict]:
    """Empate no sorteio: os empatados rolam UM dado, e só entre eles."""
    if len(grupo) == 1 or tentativa >= 5:
        return grupo

    for tirada in grupo:
        tirada["desempates"].append(gerador.dado(faces))

    por_valor: dict[int, list[dict]] = {}
    for tirada in grupo:
        por_valor.setdefault(tirada["desempates"][-1], []).append(tirada)

    saida: list[dict] = []
    for valor in sorted(por_valor, reverse=True):
        sub = por_valor[valor]
        saida.extend(sub if len(sub) == 1 else _desempatar(sub, gerador, faces, tentativa + 1))
    return saida


def sortear_ordem(estado: dict) -> dict:
    """Cada jogador rola os dados; o maior começa e o menor joga por último.

    Os do meio ficam em ordem decrescente entre eles — isto é, cada um fica
    mais perto do primeiro quanto maior tiver tirado.
    """
    if estado["fase"] != FASE_SORTEIO:
        raise ErroDeRegra("A ordem de jogada já foi sorteada.")

    estado = copy.deepcopy(estado)
    bal = carregar_balanceamento(estado["perfil"])
    quantidade = bal["dados"]["quantidade"]
    faces = bal["dados"]["faces"]
    gerador = _gerador(estado)

    tiradas = []
    for jogador in estado["jogadores"]:
        dados = gerador.dados(quantidade, faces)
        tiradas.append(
            {
                "jogador_id": jogador["jogador_id"],
                "nome": jogador["nome"],
                "dados": dados,
                "soma": sum(dados),
                "desempates": [],
            }
        )
        _log(estado, "sorteio", f"{jogador['nome']} tirou {' + '.join(map(str, dados))} = {sum(dados)}.",
             jogador["jogador_id"])

    por_soma: dict[int, list[dict]] = {}
    for tirada in tiradas:
        por_soma.setdefault(tirada["soma"], []).append(tirada)

    ordenadas: list[dict] = []
    for soma in sorted(por_soma, reverse=True):
        grupo = por_soma[soma]
        if len(grupo) > 1:
            nomes = ", ".join(t["nome"] for t in grupo)
            _log(estado, "sorteio", f"Empate em {soma} entre {nomes}. Dado extra para desempatar.")
            grupo = _desempatar(grupo, gerador, faces)
            for tirada in grupo:
                _log(estado, "sorteio",
                     f"{tirada['nome']} desempatou com {tirada['desempates'][-1]}.",
                     tirada["jogador_id"])
        ordenadas.extend(grupo)

    # A lista de jogadores passa a estar NA ORDEM DE JOGADA. Assim `vez` é
    # só um índice que anda, e nada mais precisa saber da ordem.
    por_id = {j["jogador_id"]: j for j in estado["jogadores"]}
    estado["jogadores"] = [por_id[t["jogador_id"]] for t in ordenadas]
    estado["sorteio"] = ordenadas
    estado["vez"] = 0
    estado["fase"] = FASE_ROLAR
    _guardar_gerador(estado, gerador)
    agora = time.time()
    _definir_prazo(estado, agora)
    duracao_partida = int(estado.get("minutos_de_partida", 0)) * 60
    estado["prazo_partida"] = agora + duracao_partida if duracao_partida > 0 else None

    ordem = " → ".join(t["nome"] for t in ordenadas)
    _log(estado, "sorteio", f"Ordem de jogada: {ordem}.")
    _log(estado, "vez", f"É a vez de {estado['jogadores'][0]['nome']}.",
         estado["jogadores"][0]["jogador_id"])
    return estado


# --------------------------------------------------------------------------
# 2. rolar e andar
# --------------------------------------------------------------------------

def _percorrer(estado: dict, tabuleiro, de: int, passos: int, gerador: Gerador):
    """Anda casa por casa e devolve (destino, portal, deu_a_volta).

    A Casa Portal teleporta o peão para uma casa sorteada, de onde ele anda o
    que faltava. Um teleporte por jogada: é o limite que impede o laço de
    portal em portal (BACKLOG, item 10). Com `portal.dispara_ao_passar`
    desligado no balanceamento — o padrão, ver o `_por_que` de lá —, o portal
    só vale para quem PARA nele, e aí não sobra passo para andar.

    O teleporte também anda para a frente: se a casa sorteada fica depois do
    Início, no sentido do peão, ele passou pelo Início e recebe o salário,
    como quem fez a volta a pé.
    """
    ao_passar = bool(carregar_balanceamento(estado["perfil"]).get("portal", {}).get("dispara_ao_passar", False))
    for andados in range(1, passos + 1):
        casa = tabuleiro.casa(tabuleiro.avancar(de, andados))
        if casa.tipo != "portal" or (andados < passos and not ao_passar):
            continue
        destino = gerador.escolher([c.indice for c in tabuleiro.casas if c.tipo != "portal"])
        restante = passos - andados
        salto = (casa.indice - destino) % len(tabuleiro)
        pelo_portal = tabuleiro.passou_pelo_inicio(casa.indice, salto)
        volta = (
            tabuleiro.passou_pelo_inicio(de, andados)
            or pelo_portal
            or tabuleiro.passou_pelo_inicio(destino, restante)
        )
        portal = {"casa": casa.indice, "apos": andados, "destino": destino, "passou_pelo_inicio": pelo_portal}
        return tabuleiro.avancar(destino, restante), portal, volta
    return tabuleiro.avancar(de, passos), None, tabuleiro.passou_pelo_inicio(de, passos)


#: Até onde o modo dev deixa andar numa jogada: três voltas.
PASSOS_DEV_MAXIMOS = 120


def rolar(estado: dict, jogador_id: int, *, passos: int | None = None, destino: int | None = None) -> dict:
    """Rola os dados e anda; a casa onde o peão para se resolve.

    `passos` e `destino` são do modo dev (MODO_DEV em server/config.py): andar
    um número escolhido de casas, no lugar dos dados, ou ir direto a uma casa
    — que se resolve como se o peão tivesse parado nela, sem salário, porque
    ele não andou. A jogada fica marcada como dev no log e no movimento.
    """
    estado = atualizar_tempo(estado)
    if estado["fase"] != FASE_ROLAR:
        raise ErroDeRegra("Não dá para rolar os dados agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)

    bal = carregar_balanceamento(estado["perfil"])
    tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
    gerador = _gerador(estado)

    dev = passos is not None or destino is not None
    de = jogador["posicao"]
    if destino is not None:
        if isinstance(destino, bool) or not isinstance(destino, int) or not 0 <= destino < len(tabuleiro):
            raise ErroDeRegra("Escolha uma casa do tabuleiro.")
        dados, passos, para, deu_a_volta = [], 0, destino, False
        # Só para a tela: o feixe de luz do portal leva o peão até a casa.
        portal = {"casa": de, "apos": 0, "destino": destino, "passou_pelo_inicio": False}
    else:
        if passos is None:
            dados = gerador.dados(bal["dados"]["quantidade"], bal["dados"]["faces"])
            passos = sum(dados)
        elif isinstance(passos, bool) or not isinstance(passos, int) or not 1 <= passos <= PASSOS_DEV_MAXIMOS:
            raise ErroDeRegra(f"Escolha de 1 a {PASSOS_DEV_MAXIMOS} casas.")
        else:
            dados = []
        para, portal, deu_a_volta = _percorrer(estado, tabuleiro, de, passos, gerador)
    casa = tabuleiro.casa(para)
    casas = bal.get("casas", {})
    caiu_no_easter_egg = bool(casa.easter_egg) and gerador.sorte() < float(casas.get("chance_easter_egg", 0))
    _guardar_gerador(estado, gerador)

    jogador["posicao"] = para

    # Numerar o lance é o que permite a tela de quem está ASSISTINDO saber
    # que chegou uma jogada nova e encená-la — sem isso o espectador só via
    # o peão aparecer no destino, como se teletransportasse.
    estado["lances"] = estado.get("lances", 0) + 1

    estado["ultimo_movimento"] = {
        "lance": estado["lances"],
        "jogador_id": jogador_id,
        "dados": dados,
        "passos": passos,
        "de": de,
        "para": para,
        "deu_a_volta": deu_a_volta,
        "portal": portal,
        "dev": dev,
    }

    if deu_a_volta:
        salario = int(bal.get("dinheiro", {}).get("salario_ao_passar_inicio", 0))
        if salario > 0:
            _creditar(jogador, salario)
            _log(
                estado,
                "salario_inicio",
                f"{jogador['nome']} passou pelo Início e recebeu {_reais(salario)}.",
                jogador_id,
            )
    trajeto = f", entrou na Casa Portal e parou em {casa.nome}" if portal else f" e parou em {casa.nome}"
    if destino is not None:
        lance = f"[dev] {jogador['nome']} foi direto para {casa.nome}."
    elif dev:
        lance = f"[dev] {jogador['nome']} andou {passos} {'casa' if passos == 1 else 'casas'}{trajeto}."
    else:
        lance = f"{jogador['nome']} tirou {' + '.join(map(str, dados))} = {passos}{trajeto}."
    _log(estado, "dado", lance, jogador_id)
    if portal and destino is None:
        destino = tabuleiro.casa(portal["destino"]).nome
        salario = int(bal.get("dinheiro", {}).get("salario_ao_passar_inicio", 0))
        depois_do_inicio = (
            f", depois do Início: {_reais(salario)} de salário" if portal["passou_pelo_inicio"] and salario > 0 else ""
        )
        _log(estado, "portal", f"O Portal teleportou {jogador['nome']} para {destino}{depois_do_inicio}.", jogador_id)

    if caiu_no_easter_egg:
        perdeu = _debitar_ate_o_caixa(jogador, int(casas.get("easter_egg", 0)))
        _log(estado, "easter_egg", f"{casa.nome}: {casa.easter_egg} {jogador['nome']} perdeu {_reais(perdeu)}.", jogador_id)

    propriedade = estado["propriedades"].get(str(para))
    if casa.tipo == "propriedade" and propriedade is None:
        if jogador["caixa"] >= casa.preco:
            estado["fase"] = FASE_COMPRA
            _definir_prazo(estado)
            estado["compra_pendente"] = {
                "casa": para,
                "preco": casa.preco,
                "jogador_id": jogador_id,
            }
            _log(estado, "compra", f"{jogador['nome']} pode comprar {casa.nome} por {_reais(casa.preco)}.", jogador_id)
            return estado
        _log(estado, "compra", f"{jogador['nome']} não tem dinheiro para comprar {casa.nome}.", jogador_id)
    elif casa.tipo == "propriedade" and propriedade["dono"] != jogador_id:
        vendedor = _jogador_por_id(estado, propriedade["dono"])
        preco = _valor_investido(estado, casa, propriedade)
        if not vendedor["falido"] and jogador["caixa"] >= preco:
            estado["fase"] = FASE_COMPRA_JOGADOR
            _definir_prazo(estado)
            estado["compra_pendente"] = {
                "tipo": "jogador",
                "casa": para,
                "preco": preco,
                "aluguel": _valor_aluguel(estado, casa, propriedade),
                "jogador_id": jogador_id,
                "vendedor_id": vendedor["jogador_id"],
            }
            _log(
                estado,
                "compra_jogador",
                f"{jogador['nome']} parou em {casa.nome}, de {vendedor['nome']}, e pode comprar por {_reais(preco)}.",
                jogador_id,
            )
            return estado
        if not vendedor["falido"]:
            if jogador["caixa"] < preco:
                _log(estado, "compra_jogador", f"{jogador['nome']} não tem dinheiro para comprar {casa.nome} de {vendedor['nome']}.", jogador_id)
            estado = _resolver_aluguel(estado, jogador, vendedor, casa, propriedade)
    elif casa.tipo == "propriedade" and _oferecer_melhoria(estado, jogador, casa, propriedade, "visita"):
        return estado
    elif casa.tipo != "propriedade" and _resolver_casa_de_evento(estado, jogador, casa):
        return estado

    # Aluguel de propriedade alheia é resolvido antes de passar a vez.
    if estado["fase"] == FASE_LIQUIDACAO_ALUGUEL or jogador["falido"]:
        return estado
    return _concluir_jogada(estado, jogador)


def decidir_compra(estado: dict, jogador_id: int, comprar: bool) -> dict:
    """Compra ou recusa o terreno oferecido e encerra o turno atual."""
    estado = atualizar_tempo(estado)
    if estado["fase"] != FASE_COMPRA or not estado.get("compra_pendente"):
        raise ErroDeRegra("Não há uma compra para decidir agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)
    pendente = estado["compra_pendente"]
    if pendente["jogador_id"] != jogador_id:
        raise ErroDeRegra("Essa compra pertence a outro jogador.", http=403)

    if comprar:
        preco = pendente["preco"]
        if jogador["caixa"] < preco:
            raise ErroDeRegra("Você não tem dinheiro suficiente para comprar este terreno.", http=409)
        indice = str(pendente["casa"])
        if indice in estado["propriedades"]:
            raise ErroDeRegra("Este terreno já foi comprado.", http=409)
        jogador["caixa"] -= preco
        estado["propriedades"][indice] = {"dono": jogador_id, "nivel": 0}
        _placar(jogador)["compras"] += 1
        tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
        casa = tabuleiro.casa(pendente["casa"])
        _log(estado, "compra", f"{jogador['nome']} comprou {casa.nome} por {_reais(preco)}.", jogador_id)
        _avisar_morro(estado, jogador, casa)
        estado["compra_pendente"] = None
        if _oferecer_melhoria(estado, jogador, casa, estado["propriedades"][indice], "compra"):
            return estado
    else:
        _log(estado, "compra", f"{jogador['nome']} recusou a compra.", jogador_id)

    estado["compra_pendente"] = None
    return _concluir_jogada(estado, jogador)


def decidir_compra_jogador(estado: dict, jogador_id: int, comprar: bool) -> dict:
    """Aceita ou recusa a oferta recebida ao cair numa propriedade alheia."""
    estado = atualizar_tempo(estado)
    pendente = estado.get("compra_pendente")
    if estado["fase"] != FASE_COMPRA_JOGADOR or not pendente or pendente.get("tipo") != "jogador":
        raise ErroDeRegra("Não há uma oferta de compra de outro jogador para decidir.", http=409)

    estado = copy.deepcopy(estado)
    comprador = _exigir_vez(estado, jogador_id)
    pendente = estado["compra_pendente"]
    if pendente["jogador_id"] != jogador_id:
        raise ErroDeRegra("Essa compra pertence a outro jogador.", http=403)

    indice = str(pendente["casa"])
    propriedade = estado["propriedades"].get(indice)
    vendedor = _jogador_por_id(estado, pendente["vendedor_id"])
    if vendedor["falido"] or propriedade is None or propriedade["dono"] != vendedor["jogador_id"]:
        # Quem vendia saiu da mesa (e a casa voltou ao banco) enquanto o
        # comprador pensava: não há mais negócio nem aluguel a pagar.
        estado["compra_pendente"] = None
        _log(estado, "compra_jogador", f"A compra foi cancelada porque {vendedor['nome']} saiu da partida.", jogador_id)
        return _concluir_jogada(estado, comprador)

    if comprar:
        preco = pendente["preco"]
        if comprador["caixa"] < preco:
            raise ErroDeRegra("Você não tem dinheiro suficiente para comprar essa propriedade.", http=409)
        comprador["caixa"] -= preco
        _creditar(vendedor, preco)
        propriedade["dono"] = jogador_id
        _placar(comprador)["compras"] += 1
        casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
        _log(
            estado,
            "compra_jogador",
            f"{comprador['nome']} comprou {casa.nome} de {vendedor['nome']} por {_reais(preco)}.",
            jogador_id,
        )
        _avisar_morro(estado, comprador, casa)
        estado["compra_pendente"] = None
        if _oferecer_melhoria(estado, comprador, casa, propriedade, "compra"):
            return estado
    else:
        casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
        _log(estado, "compra_jogador", f"{comprador['nome']} recusou comprar {casa.nome} de {vendedor['nome']}.", jogador_id)
        estado["compra_pendente"] = None
        estado = _resolver_aluguel(estado, comprador, vendedor, casa, propriedade)
        if estado["fase"] == FASE_LIQUIDACAO_ALUGUEL or estado["fase"] == FASE_FIM or comprador["falido"]:
            return estado

    estado["compra_pendente"] = None
    return _concluir_jogada(estado, comprador)


# --------------------------------------------------------------------------
# 3. casas de evento
# --------------------------------------------------------------------------

def _resolver_casa_de_evento(estado: dict, jogador: dict, casa) -> bool:
    """Aplica a casa onde o peão parou, quando ela não é propriedade.

    Devolve True quando a casa abriu uma decisão (Coringa, Reconstrução ou
    Prejuízo com mais de uma escolha): aí a vez espera o jogador. Nas outras,
    o efeito já aconteceu e a jogada termina. A Portal age no caminho, em
    `_percorrer`; a neutra e os cantos não fazem nada.
    """
    bal = carregar_balanceamento(estado["perfil"])
    jid = jogador["jogador_id"]
    nome = jogador["nome"]

    if casa.tipo == "ganho":
        valor = int(bal["casas"]["ganho"])
        _creditar(jogador, valor)
        _log(estado, "ganho", f"{nome} roubou na {casa.nome} e ganhou {_reais(valor)} na hora.", jid)
    elif casa.tipo == "roubo":
        valor = _debitar_ate_o_caixa(jogador, int(bal["casas"]["roubo"]))
        if valor:
            _log(estado, "roubo", f"{nome} sofreu um roubo na {casa.nome} e perdeu {_reais(valor)}.", jid)
        else:
            _log(estado, "roubo", f"{nome} sofreu um roubo na {casa.nome}, mas não tinha nada em caixa.", jid)
    elif casa.tipo == "coletor":
        valor = int(estado.get("coletor", 0))
        if valor > 0:
            estado["coletor"] = 0
            _creditar(jogador, valor)
            _log(estado, "coletor", f"{nome} parou na {casa.nome} e levou os {_reais(valor)} do Coletor de Impostos.", jid)
        else:
            _log(estado, "coletor_vazio", f"{nome} parou na {casa.nome}, mas o Coletor de Impostos está vazio.", jid)
    elif casa.tipo == "prisao":
        _prender(estado, jogador, bal)
    elif casa.tipo == "coringa":
        return _oferecer_coringa(estado, jogador, casa, bal)
    elif casa.tipo == "reconstrucao":
        return _oferecer_reconstrucao(estado, jogador, casa, bal)
    elif casa.tipo == "prejuizo":
        return _resolver_prejuizo(estado, jogador, casa, bal)
    return False


def _prender(estado: dict, jogador: dict, bal: dict) -> None:
    """Preso perde as próximas vezes — uma por rodada. Quem já saiu da cadeia
    pelo evento de final de ano volta para uma pena maior."""
    prisao = bal.get("prisao", {})
    reincidente = bool(jogador.get("reincidente"))
    rodadas = int(prisao.get("rodadas_presas_reincidente" if reincidente else "rodadas_presas", 1))
    jogador["preso"] = rodadas
    pena = "a próxima vez" if rodadas == 1 else f"as próximas {rodadas} vezes"
    motivo = " Reincidência: a pena é maior." if reincidente else ""
    _log(estado, "prisao", f"{jogador['nome']} foi para a prisão e perde {pena}.{motivo}", jogador["jogador_id"])


# --- Casa Coringa ---------------------------------------------------------

def _chance_do_coringa(estado: dict, jogador: dict, cfg: dict) -> tuple[float, str]:
    """A chance de ganhar acompanha a posição na mesa: patrimônio do jogador
    dividido pela média dos que ainda jogam. Quem está atrás tem mais chance."""
    media = _media_patrimonio(estado)
    razao = _patrimonio(estado, jogador) / media if media > 0 else 1.0
    if razao < float(cfg["atras_abaixo_de"]):
        return float(cfg["chance_atras"]), "atras"
    if razao > float(cfg["frente_acima_de"]):
        return float(cfg["chance_frente"]), "frente"
    return float(cfg["chance_na_media"]), "na_media"


def _oferecer_coringa(estado: dict, jogador: dict, casa, bal: dict) -> bool:
    cfg = bal["coringa"]
    chance, faixa = _chance_do_coringa(estado, jogador, cfg)
    ganho = int(cfg["ganho"])
    # A perda para no caixa: o Coringa nunca deixa ninguém negativo.
    perda = min(int(cfg["perda"]), max(0, jogador["caixa"]))
    estado["fase"] = FASE_CORINGA
    _definir_prazo(estado)
    estado["coringa_pendente"] = {
        "casa": casa.indice,
        "jogador_id": jogador["jogador_id"],
        "chance": chance,
        "faixa": faixa,
        "ganho": ganho,
        "perda": perda,
        "caixa": jogador["caixa"],
    }
    _log(
        estado,
        "coringa_oferta",
        f"{jogador['nome']} parou na {casa.nome}: {_porcento(chance)} de chance de ganhar {_reais(ganho)} se arriscar.",
        jogador["jogador_id"],
    )
    return True


def decidir_coringa(estado: dict, jogador_id: int, arriscar: bool) -> dict:
    """Arrisca ou deixa quieto na Casa Coringa."""
    estado = atualizar_tempo(estado)
    if estado["fase"] != FASE_CORINGA or not estado.get("coringa_pendente"):
        raise ErroDeRegra("Não há uma aposta da Casa Coringa para decidir agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)
    pendente = estado["coringa_pendente"]
    if pendente["jogador_id"] != jogador_id:
        raise ErroDeRegra("Essa aposta pertence a outro jogador.", http=403)

    if not arriscar:
        _log(estado, "coringa", f"{jogador['nome']} preferiu não arriscar na Casa Coringa.", jogador_id)
        estado["ultimo_coringa"] = {"n": estado["log_n"], "jogador_id": jogador_id, "arriscou": False}
        return _concluir_jogada(estado, jogador)

    gerador = _gerador(estado)
    ganhou = gerador.sorte() < pendente["chance"]
    _guardar_gerador(estado, gerador)
    if ganhou:
        valor = pendente["ganho"]
        _creditar(jogador, valor)
        _log(estado, "coringa", f"{jogador['nome']} arriscou na Casa Coringa e ganhou {_reais(valor)}!", jogador_id)
    else:
        valor = _debitar_ate_o_caixa(jogador, pendente["perda"])
        _log(estado, "coringa", f"{jogador['nome']} arriscou na Casa Coringa e perdeu {_reais(valor)}.", jogador_id)
    estado["ultimo_coringa"] = {
        "n": estado["log_n"],
        "jogador_id": jogador_id,
        "arriscou": True,
        "ganhou": ganhou,
        "valor": valor,
        "chance": pendente["chance"],
    }
    return _concluir_jogada(estado, jogador)


# --- Casa da Reconstrução ---------------------------------------------------

def _opcoes_de_reconstrucao(estado: dict, jogador: dict, desconto: float) -> list[dict]:
    """Cada propriedade do jogador que ainda sobe de nível, com o custo já
    descontado e o aluguel de antes e depois — a tela só mostra."""
    tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
    maximo = _niveis_maximos(estado)
    opcoes = []
    for indice, propriedade in sorted(_propriedades_de(estado, jogador["jogador_id"])):
        casa = tabuleiro.casa(indice)
        nivel = int(propriedade.get("nivel", 0))
        cheio = _valor_upgrade(estado, casa)
        if nivel >= maximo or cheio <= 0:
            continue
        custo = int(round(cheio * (1 - desconto)))
        opcoes.append({
            "casa": indice,
            "nivel": nivel,
            "custo": custo,
            "custo_cheio": cheio,
            "aluguel_atual": _valor_aluguel(estado, casa, propriedade),
            "aluguel_novo": _valor_aluguel(estado, casa, {**propriedade, "nivel": nivel + 1}),
        })
    return opcoes


def _oferecer_reconstrucao(estado: dict, jogador: dict, casa, bal: dict) -> bool:
    desconto = float(bal.get("reconstrucao", {}).get("desconto", 0))
    opcoes = _opcoes_de_reconstrucao(estado, jogador, desconto)
    jid = jogador["jogador_id"]
    if not opcoes:
        motivo = "já está com tudo no nível máximo" if _propriedades_de(estado, jid) else "não tem propriedade para reformar"
        _log(estado, "reconstrucao", f"{jogador['nome']} parou na {casa.nome}, mas {motivo}.", jid)
        return False
    if not any(opcao["custo"] <= jogador["caixa"] for opcao in opcoes):
        _log(estado, "reconstrucao", f"{jogador['nome']} parou na {casa.nome}, mas não tem caixa para nenhuma reforma.", jid)
        return False

    estado["fase"] = FASE_RECONSTRUCAO
    _definir_prazo(estado)
    estado["reconstrucao_pendente"] = {"casa": casa.indice, "jogador_id": jid, "desconto": desconto, "opcoes": opcoes}
    _log(
        estado,
        "reconstrucao_oferta",
        f"{jogador['nome']} pode melhorar uma propriedade com {_porcento(desconto)} de desconto.",
        jid,
    )
    return True


def decidir_reconstrucao(estado: dict, jogador_id: int, casa_indice: int | None) -> dict:
    """Melhora a propriedade escolhida com desconto, ou recusa (`None`)."""
    estado = atualizar_tempo(estado)
    if estado["fase"] != FASE_RECONSTRUCAO or not estado.get("reconstrucao_pendente"):
        raise ErroDeRegra("Não há uma reforma para decidir agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)
    pendente = estado["reconstrucao_pendente"]
    if pendente["jogador_id"] != jogador_id:
        raise ErroDeRegra("Essa reforma pertence a outro jogador.", http=403)

    if casa_indice is None:
        _log(estado, "reconstrucao", f"{jogador['nome']} não quis reformar nada.", jogador_id)
        return _concluir_jogada(estado, jogador)

    opcao = next((o for o in pendente["opcoes"] if o["casa"] == casa_indice), None)
    if opcao is None:
        raise ErroDeRegra("Escolha uma das suas propriedades da lista.")
    propriedade = estado["propriedades"].get(str(casa_indice))
    if propriedade is None or propriedade["dono"] != jogador_id:
        raise ErroDeRegra("Essa propriedade não é mais sua.", http=409)
    if int(propriedade.get("nivel", 0)) != opcao["nivel"]:
        raise ErroDeRegra("Essa propriedade já mudou de nível.", http=409)
    if jogador["caixa"] < opcao["custo"]:
        raise ErroDeRegra(f"Você precisa de {_reais(opcao['custo'])} para essa reforma.", http=409)

    jogador["caixa"] -= opcao["custo"]
    propriedade["nivel"] = opcao["nivel"] + 1
    _placar(jogador)["melhorias"] += 1
    casa = carregar_tabuleiro(estado["tabuleiro"]).casa(casa_indice)
    _log(
        estado,
        "reconstrucao",
        f"{jogador['nome']} reformou {casa.nome} para o nível {propriedade['nivel']} por {_reais(opcao['custo'])}, com desconto.",
        jogador_id,
    )
    return _concluir_jogada(estado, jogador)


# --- Casa do Prejuízo --------------------------------------------------------

def _lider(estado: dict) -> dict | None:
    """Maior patrimônio entre quem joga. Empate: o primeiro na ordem de jogada."""
    vivos = _vivos(estado)
    return max(vivos, key=lambda j: _patrimonio(estado, j)) if vivos else None


def _opcoes_de_prejuizo(estado: dict, alvo: dict, cfg: dict) -> list[dict]:
    """Propriedades do líder que o golpe pode tirar, da mais valiosa à menos."""
    tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
    grupos = set(cfg.get("grupos_atingidos", ["media", "barata"]))
    opcoes = []
    for indice, propriedade in _propriedades_de(estado, alvo["jogador_id"]):
        casa = tabuleiro.casa(indice)
        if casa.grupo not in grupos:
            continue
        valor = _valor_investido(estado, casa, propriedade)
        opcoes.append({"casa": indice, "valor": valor, "ao_coletor": int(round(valor * float(cfg["ao_coletor"])))})
    return sorted(opcoes, key=lambda o: (-o["valor"], o["casa"]))


def _resolver_prejuizo(estado: dict, jogador: dict, casa, bal: dict) -> bool:
    """O líder da mesa toma o golpe — mesmo quando é ele quem pisa. Quem
    pisou escolhe qual propriedade média ou barata do líder volta ao banco."""
    cfg = bal["prejuizo"]
    lider = _lider(estado)
    jid = jogador["jogador_id"]
    if lider is None:
        return False
    opcoes = _opcoes_de_prejuizo(estado, lider, cfg)
    if not opcoes:
        perda = _debitar_ate_o_caixa(lider, int(round(lider["caixa"] * float(cfg["sem_propriedade_perde_do_caixa"]))))
        estado["coletor"] = estado.get("coletor", 0) + perda
        _log(
            estado,
            "prejuizo",
            f"Casa do Prejuízo: {lider['nome']}, que lidera a mesa, não tem propriedade média ou barata "
            f"e perdeu {_reais(perda)} do caixa para o Coletor de Impostos.",
            lider["jogador_id"],
        )
        return False
    if len(opcoes) == 1:
        # Uma só possibilidade: não há o que escolher.
        _aplicar_prejuizo(estado, lider, opcoes[0])
        return False

    estado["fase"] = FASE_PREJUIZO
    _definir_prazo(estado)
    estado["prejuizo_pendente"] = {"casa": casa.indice, "jogador_id": jid, "alvo_id": lider["jogador_id"], "opcoes": opcoes}
    if lider is jogador:
        texto = f"{jogador['nome']} lidera a mesa, parou na {casa.nome} e escolhe qual propriedade sua volta para o banco."
    else:
        texto = f"{jogador['nome']} parou na {casa.nome} e escolhe qual propriedade de {lider['nome']}, que lidera a mesa, volta para o banco."
    _log(estado, "prejuizo_oferta", texto, jid)
    return True


def _aplicar_prejuizo(estado: dict, alvo: dict, opcao: dict) -> None:
    casa = carregar_tabuleiro(estado["tabuleiro"]).casa(opcao["casa"])
    del estado["propriedades"][str(opcao["casa"])]
    estado["coletor"] = estado.get("coletor", 0) + opcao["ao_coletor"]
    _log(
        estado,
        "prejuizo",
        f"{alvo['nome']} perdeu {casa.nome}, que voltou para o banco. "
        f"{_reais(opcao['ao_coletor'])} foram para o Coletor de Impostos.",
        alvo["jogador_id"],
    )


def _prejuizo_ainda_valido(estado: dict, pendente: dict) -> list[dict]:
    """As opções cuja casa ainda é do alvo — ele pode ter saído da mesa."""
    return [
        opcao for opcao in pendente["opcoes"]
        if estado["propriedades"].get(str(opcao["casa"]), {}).get("dono") == pendente["alvo_id"]
    ]


def escolher_prejuizo(estado: dict, jogador_id: int, casa_indice: int) -> dict:
    """Quem pisou na Casa do Prejuízo escolhe a propriedade que o líder perde."""
    estado = atualizar_tempo(estado)
    if estado["fase"] != FASE_PREJUIZO or not estado.get("prejuizo_pendente"):
        raise ErroDeRegra("Não há um prejuízo para escolher agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)
    pendente = estado["prejuizo_pendente"]
    if pendente["jogador_id"] != jogador_id:
        raise ErroDeRegra("Essa escolha pertence a outro jogador.", http=403)

    validas = _prejuizo_ainda_valido(estado, pendente)
    opcao = next((o for o in validas if o["casa"] == casa_indice), None)
    if opcao is None:
        if validas:
            raise ErroDeRegra("Escolha uma das propriedades da lista.")
        _log(estado, "prejuizo", "O líder já não tem a propriedade escolhida. O Prejuízo não tirou nada.", jogador_id)
        return _concluir_jogada(estado, jogador)
    _aplicar_prejuizo(estado, _jogador_por_id(estado, pendente["alvo_id"]), opcao)
    return _concluir_jogada(estado, jogador)


# --- Bônus do banco (evento temático) ------------------------------------------

def _bonus_disponivel(estado: dict, jogador: dict) -> bool:
    evento = _evento_ativo(estado)
    return bool(
        evento
        and evento["tipo"] == "bonus_do_banco"
        and not jogador["falido"]
        and jogador["posicao"] in evento.get("regiao", [])
        and jogador["jogador_id"] not in evento.get("usaram", [])
        and _propriedades_de(estado, jogador["jogador_id"])
    )


def _valor_no_bonus(estado: dict, casa, propriedade: dict) -> int:
    """Valor investido (tabela + melhorias) mais o bônus. Sem melhorias, é
    exatamente "35% acima do valor de tabela"."""
    acima = float(_config_evento(estado, "bonus_do_banco").get("acima_da_tabela", 0))
    return int(round(_valor_investido(estado, casa, propriedade) * (1 + acima)))


def vender_no_bonus(estado: dict, jogador_id: int, casa_indice: int | None) -> dict:
    """Bônus do banco: quem está na região sorteada vende uma propriedade ao
    banco acima da tabela, uma vez por evento.

    Vale de dois jeitos. Antes de rolar, para quem começou a vez dentro da
    região — aí a vez continua. E como decisão ao terminar o movimento na
    região (`FASE_BONUS_BANCO`) — aí `None` recusa e a vez passa.
    """
    estado = atualizar_tempo(estado)
    if estado["fase"] not in (FASE_ROLAR, FASE_BONUS_BANCO):
        raise ErroDeRegra("O bônus do banco não está disponível agora.", http=409)

    estado = copy.deepcopy(estado)
    jogador = _exigir_vez(estado, jogador_id)
    na_decisao = estado["fase"] == FASE_BONUS_BANCO
    if casa_indice is None:
        if not na_decisao:
            raise ErroDeRegra("Escolha uma propriedade para vender.")
        _log(estado, "bonus_banco", f"{jogador['nome']} preferiu não vender nada ao banco.", jogador_id)
        return passar_turno(estado)
    if not _bonus_disponivel(estado, jogador):
        raise ErroDeRegra("Você não está na região do Bônus do banco, ou já usou o bônus.", http=409)
    propriedade = estado["propriedades"].get(str(casa_indice))
    if propriedade is None or propriedade["dono"] != jogador_id:
        raise ErroDeRegra("Essa propriedade não é sua.", http=409)

    casa = carregar_tabuleiro(estado["tabuleiro"]).casa(casa_indice)
    valor = _valor_no_bonus(estado, casa, propriedade)
    _creditar(jogador, valor)
    del estado["propriedades"][str(casa_indice)]
    _evento_ativo(estado)["usaram"].append(jogador_id)
    _log(estado, "bonus_banco", f"{jogador['nome']} vendeu {casa.nome} ao banco por {_reais(valor)} no Bônus do banco.", jogador_id)
    return passar_turno(estado) if na_decisao else estado


# --------------------------------------------------------------------------
# 4. eventos temáticos
# --------------------------------------------------------------------------

def _evento_faz_sentido(estado: dict, tipo: str) -> bool:
    """Evento que não mudaria nada não é sorteado: o Presidente com o Coletor
    vazio, ou o Bônus do banco sem ninguém com propriedade."""
    if tipo == "presidente":
        return estado.get("coletor", 0) > 0
    if tipo == "bonus_do_banco":
        return bool(estado["propriedades"])
    return True


def _iniciar_rodada(estado: dict) -> None:
    """Começo de rodada: o evento da anterior acaba e outro pode ser sorteado."""
    estado["evento"] = None
    cfg = carregar_balanceamento(estado["perfil"]).get("eventos", {})
    if estado["rodada"] < int(cfg.get("a_partir_da_rodada", 2)):
        return
    gerador = _gerador(estado)
    sorteado = gerador.sorte() < float(cfg.get("chance_por_rodada", 0))
    candidatos = [
        (tipo, float(cfg.get(tipo, {}).get("peso", 0)))
        for tipo in EVENTOS_TEMATICOS
        if float(cfg.get(tipo, {}).get("peso", 0)) > 0 and _evento_faz_sentido(estado, tipo)
    ]
    if sorteado and candidatos:
        alvo = gerador.sorte() * sum(peso for _, peso in candidatos)
        escolhido = candidatos[-1][0]
        for tipo, peso in candidatos:
            if alvo < peso:
                escolhido = tipo
                break
            alvo -= peso
        _aplicar_evento(estado, escolhido, gerador)
    _guardar_gerador(estado, gerador)


def _aplicar_evento(estado: dict, tipo: str, gerador: Gerador) -> None:
    cfg = _config_evento(estado, tipo)
    vivos = _vivos(estado)
    evento = {"tipo": tipo, "nome": EVENTOS_TEMATICOS[tipo], "rodada": estado["rodada"]}

    if tipo == "colheita_ruim":
        fracao = float(cfg.get("perde_do_caixa", 0))
        for jogador in vivos:
            _debitar_ate_o_caixa(jogador, int(round(jogador["caixa"] * fracao)))
        texto = f"Todos perderam {_porcento(fracao)} do caixa."
        resumo = texto[:-1]
    elif tipo == "baile_na_vila":
        ganho = int(cfg.get("ganho", 0))
        for jogador in vivos:
            _creditar(jogador, ganho)
        texto = f"Todos ganharam {_reais(ganho)}."
        resumo = texto[:-1]
    elif tipo == "final_de_ano":
        extra = float(cfg.get("aluguel_extra", 0))
        soltos = [j for j in vivos if j.get("preso", 0) > 0]
        for jogador in soltos:
            jogador["preso"] = 0
            jogador["reincidente"] = True
        texto = f"Nesta rodada, todos os aluguéis ficam {_porcento(extra)} mais caros."
        resumo = f"Aluguéis {_porcento(extra)} mais caros nesta rodada"
        if soltos:
            pena = carregar_balanceamento(estado["perfil"]).get("prisao", {}).get("rodadas_presas_reincidente", 3)
            nomes = ", ".join(j["nome"] for j in soltos)
            texto += f" Saíram da prisão: {nomes}. Quem voltar para lá perde {pena} rodadas."
    elif tipo == "presidente":
        valor = int(estado.get("coletor", 0))
        estado["coletor"] = 0
        texto = f"O Presidente Cor de Mel confiscou os {_reais(valor)} do Coletor de Impostos."
        resumo = f"Coletor confiscado ({_reais(valor)})"
    else:  # bonus_do_banco
        tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
        tamanho = max(1, min(len(tabuleiro), int(cfg.get("casas_na_regiao", 4))))
        inicio = gerador.inteiro(0, len(tabuleiro) - 1)
        # Casas seguidas, na ordem em que o peão anda.
        evento["regiao"] = [tabuleiro.avancar(inicio, k) for k in range(tamanho)]
        evento["usaram"] = []
        primeira = tabuleiro.casa(evento["regiao"][0]).nome
        ultima = tabuleiro.casa(evento["regiao"][-1]).nome
        acima = float(cfg.get("acima_da_tabela", 0))
        texto = (
            f"Nesta rodada, quem estiver entre {primeira} e {ultima} pode vender uma propriedade "
            f"ao banco por {_porcento(acima)} acima do valor."
        )
        resumo = f"Venda ao banco +{_porcento(acima)} na região dourada"

    evento["texto"] = texto
    # Uma linha para o chip do alto da tela; o texto inteiro vai no anúncio.
    evento["resumo"] = resumo
    estado["evento"] = evento
    _log(estado, "evento_tematico", f"{evento['nome']}! {texto}")


# --------------------------------------------------------------------------
# 5. leilão
# --------------------------------------------------------------------------
#
# Quem tem a vez põe uma propriedade sua em leilão e os outros dão lances
# contra o relógio. Vale a qualquer momento da própria vez: antes de rolar ou
# no meio de uma decisão — levantar dinheiro para comprar, ou para pagar um
# aluguel por mais do que o banco paga. Durante o leilão, `prazo_vez` é o
# relógio dos lances; quando ele zera, `atualizar_tempo` fecha o leilão e a
# vez volta para a fase em que estava (`_retomar_depois_do_leilao`).

#: As fases da vez em que dá para abrir um leilão.
FASES_QUE_ACEITAM_LEILAO = (
    FASE_ROLAR,
    FASE_COMPRA,
    FASE_COMPRA_JOGADOR,
    FASE_LIQUIDACAO_ALUGUEL,
    FASE_MELHORIA,
    FASE_CORINGA,
    FASE_RECONSTRUCAO,
    FASE_PREJUIZO,
    FASE_BONUS_BANCO,
)


def _config_leilao(estado: dict) -> dict:
    return carregar_balanceamento(estado["perfil"]).get("leilao", {})


def _por_que_nao_leiloa(estado: dict, jogador: dict) -> str | None:
    """O motivo de o jogador não poder abrir um leilão agora, ou None.

    A tela mostra o motivo no painel da casa a qualquer hora; por isso o que
    é da pessoa (não ter casa, estar acima do limite, já ter leiloado) vem
    antes do que é do momento (não ser a vez dela). O limite de patrimônio
    só vale se o balanceamento tiver um; o padrão é qualquer um poder.
    """
    cfg = _config_leilao(estado)
    if jogador["falido"] or estado["fase"] == FASE_FIM:
        return "A partida acabou para você."
    if not _propriedades_de(estado, jogador["jogador_id"]):
        return "Você não tem propriedade para leiloar."
    limite = cfg.get("so_abaixo_de_percentual_da_media")
    if limite is not None:
        media = _media_patrimonio(estado)
        razao = _patrimonio(estado, jogador) / media if media > 0 else 1.0
        if razao >= float(limite):
            return (
                f"O leilão é só para quem está abaixo de {_porcento(float(limite))} da média da mesa "
                f"— você está em {_porcento(razao)}."
            )
    ultima = jogador.get("leiloou_na_rodada")
    proxima = None if ultima is None else ultima + max(1, int(cfg.get("rodadas_entre_leiloes", 1)))
    if proxima is not None and estado["rodada"] < proxima:
        if proxima == estado["rodada"] + 1:
            return "Você já leiloou nesta rodada."
        return f"Seu próximo leilão fica para a rodada {proxima}."
    if _jogador_da_vez(estado)["jogador_id"] != jogador["jogador_id"] or estado["fase"] not in FASES_QUE_ACEITAM_LEILAO:
        return "O leilão abre na sua vez."
    return None


def _passo_do_lance(casa, cfg: dict) -> int:
    """De quanto em quanto o lance sobe: uma fração da tabela, redonda."""
    redondo = max(1, int(cfg.get("arredondar_para", 10_000)))
    bruto = (casa.preco or 0) * float(cfg.get("passo_do_lance", 0.05))
    return max(redondo, int(round(bruto / redondo)) * redondo)


def _oferta_do_banco_no_leilao(estado: dict, casa, propriedade: dict) -> int:
    """O que o banco paga se ninguém der lance: a mesma fração do valor
    investido da venda para pagar dívida. Sem melhoria, é a fração da tabela
    que a regra cita."""
    fracao = float(_config_leilao(estado).get("compra_do_banco_sem_lance", 0))
    return int(round(_valor_investido(estado, casa, propriedade) * fracao))


def _lider_do_leilao(leilao: dict) -> dict | None:
    # Cada lance passa do anterior: o último é o maior.
    return leilao["lances"][-1] if leilao["lances"] else None


def _lance_minimo(leilao: dict) -> int:
    """O próximo lance aceito: um passo acima do maior. O primeiro precisa
    passar da oferta do banco — senão seria pior para quem vende do que
    ninguém dar lance — e começa no primeiro número redondo acima dela."""
    lider = _lider_do_leilao(leilao)
    if lider:
        return lider["valor"] + leilao["passo"]
    return (leilao["oferta_do_banco"] // leilao["passo"] + 1) * leilao["passo"]


def abrir_leilao(estado: dict, jogador_id: int, casa_indice: int, agora: float | None = None) -> dict:
    """Põe uma propriedade do jogador da vez em leilão — antes de rolar ou no
    meio de uma decisão, que espera o leilão acabar."""
    instante = time.time() if agora is None else agora
    estado = copy.deepcopy(atualizar_tempo(estado, instante))
    jogador = _exigir_vez(estado, jogador_id)
    motivo = _por_que_nao_leiloa(estado, jogador)
    if motivo:
        raise ErroDeRegra(motivo, http=409)
    if isinstance(casa_indice, bool) or not isinstance(casa_indice, int):
        raise ErroDeRegra("Escolha uma propriedade válida.")
    propriedade = estado["propriedades"].get(str(casa_indice))
    if propriedade is None or propriedade["dono"] != jogador_id:
        raise ErroDeRegra("Essa propriedade não é sua.", http=409)
    melhoria = estado.get("melhoria_pendente")
    if estado["fase"] == FASE_MELHORIA and melhoria and melhoria["casa"] == casa_indice:
        raise ErroDeRegra("Decida a melhoria desta casa antes de leiloá-la.", http=409)

    bal = carregar_balanceamento(estado["perfil"])
    cfg = bal.get("leilao", {})
    casa = carregar_tabuleiro(estado["tabuleiro"]).casa(casa_indice)
    duracao = int(bal["tempo"].get("segundos_de_leilao", 12))
    estado["leilao"] = {
        "casa": casa_indice,
        "vendedor_id": jogador_id,
        "nivel": int(propriedade.get("nivel", 0)),
        "valor_tabela": casa.preco,
        "valor_investido": _valor_investido(estado, casa, propriedade),
        "oferta_do_banco": _oferta_do_banco_no_leilao(estado, casa, propriedade),
        # A regra: 2% do valor de TABELA, não do lance — o imposto não muda
        # com a disputa, e quem arremata sabe desde o começo quanto paga.
        "imposto": int(round((casa.preco or 0) * float(cfg.get("imposto_sobre_tabela", 0)))),
        "passo": _passo_do_lance(casa, cfg),
        "duracao": duracao,
        "lances": [],
        # A decisão em que a vez estava: ela volta quando o leilão fechar.
        "fase_anterior": estado["fase"],
        "aberto_em": instante,
    }
    estado["fase"] = FASE_LEILAO
    estado["prazo_vez"] = instante + duracao
    jogador["leiloou_na_rodada"] = estado["rodada"]
    _log(
        estado,
        "leilao_aberto",
        f"{jogador['nome']} pôs {casa.nome} em leilão. Lance mínimo: {_reais(_lance_minimo(estado['leilao']))}.",
        jogador_id,
    )
    estado["leilao"]["n"] = estado["log_n"]
    return estado


def dar_lance(estado: dict, jogador_id: int, valor: int, agora: float | None = None) -> dict:
    """Um lance no leilão aberto: qualquer um da mesa, menos quem vende.

    O lance precisa caber no caixa junto com o imposto — o dinheiro só sai
    quando o leilão fecha, mas nada mais acontece na mesa enquanto ele
    corre, então quem dá o lance continua podendo pagá-lo. Lance nos últimos
    segundos estica o relógio: com a tela consultando o servidor de tempos em
    tempos, sem isso o último a clicar levava sem ninguém ter visto o lance.
    """
    instante = time.time() if agora is None else agora
    estado = atualizar_tempo(estado, instante)
    if estado["fase"] != FASE_LEILAO or not estado.get("leilao"):
        raise ErroDeRegra("Não há leilão aberto agora.", http=409)

    estado = copy.deepcopy(estado)
    leilao = estado["leilao"]
    jogador = _jogador_por_id(estado, jogador_id)
    if jogador["falido"]:
        raise ErroDeRegra("Você já saiu da partida.", http=403)
    if jogador_id == leilao["vendedor_id"]:
        raise ErroDeRegra("Você não pode dar lance no seu próprio leilão.", http=403)
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErroDeRegra("Informe o valor do lance.")
    lider = _lider_do_leilao(leilao)
    if lider and lider["jogador_id"] == jogador_id:
        raise ErroDeRegra("Seu lance já é o maior.", http=409)
    minimo = _lance_minimo(leilao)
    if valor < minimo:
        raise ErroDeRegra(f"O lance mínimo agora é {_reais(minimo)}.", http=409)
    if valor + leilao["imposto"] > jogador["caixa"]:
        raise ErroDeRegra(
            f"Seu caixa não cobre {_reais(valor)} mais {_reais(leilao['imposto'])} de imposto.", http=409
        )

    leilao["lances"].append({"jogador_id": jogador_id, "valor": valor})
    cfg = _config_leilao(estado)
    esticar = float(cfg.get("segundos_apos_lance", 0))
    if esticar > 0:
        prazo = max(estado["prazo_vez"] or instante, instante + esticar)
        # Guerra de lances não come o relógio da partida: há um teto.
        teto = cfg.get("segundos_no_maximo")
        if teto and leilao.get("aberto_em") is not None:
            prazo = min(prazo, leilao["aberto_em"] + float(teto))
        estado["prazo_vez"] = prazo
    return estado


def _vencedor_do_leilao(estado: dict, leilao: dict) -> dict | None:
    """O maior lance de quem ainda está na mesa e ainda pode pagar."""
    for lance in reversed(leilao["lances"]):
        jogador = next((j for j in estado["jogadores"] if j["jogador_id"] == lance["jogador_id"]), None)
        if jogador and not jogador["falido"] and jogador["caixa"] >= lance["valor"] + leilao["imposto"]:
            return lance
    return None


def _fechar_leilao(estado: dict, instante: float) -> dict:
    """O relógio dos lances zerou: o maior lance leva a propriedade, com as
    melhorias; sem lance, o banco compra. A vez volta para quem vendeu, na
    fase em que estava, com o prazo recomeçado."""
    leilao = estado["leilao"]
    estado["leilao"] = None
    estado["fase"] = leilao.get("fase_anterior", FASE_ROLAR)
    _definir_prazo(estado, instante)
    casa = carregar_tabuleiro(estado["tabuleiro"]).casa(leilao["casa"])
    vendedor = _jogador_por_id(estado, leilao["vendedor_id"])
    propriedade = estado["propriedades"].get(str(leilao["casa"]))
    if propriedade is None or propriedade["dono"] != vendedor["jogador_id"]:
        # Nada na mesa tira a casa de quem vende durante o leilão; se um dia
        # tirar, o leilão acaba sem negócio em vez de travar a partida.
        _log(estado, "leilao_cancelado", f"O leilão de {casa.nome} foi cancelado.", vendedor["jogador_id"])
        return _retomar_depois_do_leilao(estado, vendedor)
    resultado = {
        "casa": leilao["casa"],
        "vendedor_id": vendedor["jogador_id"],
        "nivel": leilao["nivel"],
        "valor_tabela": leilao["valor_tabela"],
        "valor_investido": leilao["valor_investido"],
        "lances": len(leilao["lances"]),
        "comprador_id": None,
        "lance": None,
        "imposto": 0,
        "banco": None,
    }

    vencedor = _vencedor_do_leilao(estado, leilao)
    if vencedor:
        comprador = _jogador_por_id(estado, vencedor["jogador_id"])
        lance = vencedor["valor"]
        comprador["caixa"] -= lance + leilao["imposto"]
        _creditar(vendedor, lance)
        estado["coletor"] = estado.get("coletor", 0) + leilao["imposto"]
        propriedade["dono"] = comprador["jogador_id"]
        _placar(comprador)["compras"] += 1
        _log(
            estado,
            "leilao",
            f"{comprador['nome']} arrematou {casa.nome} de {vendedor['nome']} por {_reais(lance)}. "
            f"{_reais(leilao['imposto'])} de imposto foram para o Coletor.",
            comprador["jogador_id"],
        )
        _avisar_morro(estado, comprador, casa)
        resultado.update(comprador_id=comprador["jogador_id"], lance=lance, imposto=leilao["imposto"])
    else:
        valor = leilao["oferta_do_banco"]
        _creditar(vendedor, valor)
        del estado["propriedades"][str(leilao["casa"])]
        _log(
            estado,
            "leilao",
            f"Ninguém deu lance em {casa.nome}: o banco comprou de {vendedor['nome']} por {_reais(valor)}.",
            vendedor["jogador_id"],
        )
        resultado["banco"] = valor

    resultado["coletor"] = estado.get("coletor", 0)
    resultado["n"] = estado["log_n"]
    estado["ultimo_leilao"] = resultado
    return _retomar_depois_do_leilao(estado, vendedor)


def _retomar_depois_do_leilao(estado: dict, jogador: dict) -> dict:
    """A decisão que esperava o leilão volta com o que ele mudou: o caixa
    novo e as casas que já não são do jogador.

    Liquidando um aluguel, o dinheiro do leilão pode já quitar a dívida. Na
    Coringa, a perda (que para no caixa) é recalculada com o caixa de agora.
    Na Reconstrução e no Prejuízo, a casa vendida sai da lista; se não sobrar
    nenhuma, não há o que escolher e a jogada termina.
    """
    jid = jogador["jogador_id"]
    fase = estado["fase"]
    if fase == FASE_LIQUIDACAO_ALUGUEL and estado.get("aluguel_pendente"):
        return _encerrar_liquidacao(estado)
    if fase == FASE_CORINGA and estado.get("coringa_pendente"):
        pendente = estado["coringa_pendente"]
        perda_cheia = int(carregar_balanceamento(estado["perfil"])["coringa"]["perda"])
        pendente["perda"] = min(perda_cheia, max(0, jogador["caixa"]))
        pendente["caixa"] = jogador["caixa"]
    elif fase == FASE_RECONSTRUCAO and estado.get("reconstrucao_pendente"):
        pendente = estado["reconstrucao_pendente"]
        pendente["opcoes"] = [
            opcao for opcao in pendente["opcoes"]
            if estado["propriedades"].get(str(opcao["casa"]), {}).get("dono") == jid
        ]
        if not pendente["opcoes"]:
            _log(estado, "reconstrucao", f"{jogador['nome']} leiloou a última casa que dava para reformar.", jid)
            return _concluir_jogada(estado, jogador)
    elif fase == FASE_PREJUIZO and estado.get("prejuizo_pendente"):
        pendente = estado["prejuizo_pendente"]
        pendente["opcoes"] = _prejuizo_ainda_valido(estado, pendente)
        if not pendente["opcoes"]:
            _log(estado, "prejuizo", "O líder já não tem nenhuma das casas da lista. O Prejuízo não tirou nada.", jid)
            return _concluir_jogada(estado, jogador)
    return estado


def _cancelar_leilao_de_quem_saiu(estado: dict, jogador: dict) -> None:
    """Saiu da mesa no meio do leilão: se era quem vendia, o leilão acaba
    (a casa volta ao banco com as outras); se dava lance, os lances dele
    saem e o maior dos que sobraram volta a liderar."""
    leilao = estado.get("leilao")
    if not leilao:
        return
    if leilao["vendedor_id"] != jogador["jogador_id"]:
        leilao["lances"] = [lance for lance in leilao["lances"] if lance["jogador_id"] != jogador["jogador_id"]]
        return
    casa = carregar_tabuleiro(estado["tabuleiro"]).casa(leilao["casa"])
    estado["leilao"] = None
    _log(
        estado,
        "leilao_cancelado",
        f"O leilão de {casa.nome} foi cancelado: {jogador['nome']} saiu da partida.",
        jogador["jogador_id"],
    )


# --------------------------------------------------------------------------
# 6. modo dev (trapaças de teste)
# --------------------------------------------------------------------------
#
# Só o servidor decide se valem (MODO_DEV em server/config.py). Andar um
# número escolhido de casas e ir direto a uma casa são `rolar(passos=...)` e
# `rolar(destino=...)`; aqui fica o caixa. Toda trapaça vai para o log como
# [dev]: a mesa vê.

#: O caixa mais alto que o modo dev aceita.
CAIXA_DEV_MAXIMO = 1_000_000_000


def definir_caixa(estado: dict, jogador_id: int, valor: int) -> dict:
    """Modo dev: o caixa do jogador passa a ser `valor`, a qualquer momento.

    Não conta no placar do fim (não é arrecadação). Se ele estava liquidando
    um aluguel e o caixa novo cobre a dívida, a dívida se paga na hora."""
    estado = atualizar_tempo(estado)
    if estado["fase"] in (FASE_SORTEIO, FASE_FIM):
        raise ErroDeRegra("A partida não está em andamento.", http=409)
    if isinstance(valor, bool) or not isinstance(valor, int) or not 0 <= valor <= CAIXA_DEV_MAXIMO:
        raise ErroDeRegra(f"Informe um valor de R$ 0 a {_reais(CAIXA_DEV_MAXIMO)}.")

    estado = copy.deepcopy(estado)
    jogador = _jogador_por_id(estado, jogador_id)
    if jogador["falido"]:
        raise ErroDeRegra("Você já saiu da partida.", http=403)
    antes = jogador["caixa"]
    jogador["caixa"] = valor
    _log(
        estado,
        "dev",
        f"[dev] {jogador['nome']} mudou o próprio caixa de {_reais(antes)} para {_reais(valor)}.",
        jogador_id,
    )
    pendente = estado.get("aluguel_pendente")
    if estado["fase"] == FASE_LIQUIDACAO_ALUGUEL and pendente and pendente["jogador_id"] == jogador_id:
        return _encerrar_liquidacao(estado)
    return estado


# --------------------------------------------------------------------------
# passagem de turno
# --------------------------------------------------------------------------

def abandonar(estado: dict, jogador_id: int) -> dict:
    """Jogador saiu no meio da partida.

    Ele é marcado como fora e sai da roda, e os terrenos dele voltam para o
    banco, como na falência — senão ficavam mortos no tabuleiro, sem aluguel
    nem venda. Sem isto o turno dele travava a mesa, porque a vez ficava
    esperando alguém que não está mais ali.
    """
    estado = copy.deepcopy(_atualizar(estado))
    jogador = _jogador_por_id(estado, jogador_id)

    if jogador["falido"] or estado["fase"] == FASE_FIM:
        return estado

    _cancelar_leilao_de_quem_saiu(estado, jogador)
    devolvidas = _devolver_ao_banco(estado, jogador_id)
    _tirar_da_mesa(estado, jogador)
    jogador["abandonou"] = True
    terrenos = f" {devolvidas} propriedade(s) voltou(aram) ao banco." if devolvidas else ""
    _log(estado, "saida", f"{jogador['nome']} abandonou a partida.{terrenos}", jogador_id)

    if _jogador_da_vez(estado)["jogador_id"] == jogador_id:
        return passar_turno(estado)
    if len(_vivos(estado)) <= 1:
        return _encerrar_partida(estado, "ultimo_sobrevivente")
    return estado


def _concluir_jogada(estado: dict, jogador: dict) -> dict:
    """Fim da jogada de quem está na vez. Antes de passar, o Bônus do banco:
    quem terminou o movimento dentro da região sorteada pode vender."""
    if _bonus_disponivel(estado, jogador):
        for chave in PENDENCIAS:
            estado[chave] = None
        estado["fase"] = FASE_BONUS_BANCO
        _definir_prazo(estado)
        _log(
            estado,
            "bonus_banco_oferta",
            f"{jogador['nome']} está na região do Bônus do banco e pode vender uma propriedade acima do valor.",
            jogador["jogador_id"],
        )
        return estado
    return passar_turno(estado)


def passar_turno(estado: dict, agora: float | None = None) -> dict:
    instante = time.time() if agora is None else agora
    _observar_prazo_partida(estado, instante)
    for chave in PENDENCIAS:
        estado[chave] = None
    vivos = [i for i, j in enumerate(estado["jogadores"]) if not j["falido"]]
    if len(vivos) <= 1:
        return _encerrar_partida(estado, "ultimo_sobrevivente")

    total = len(estado["jogadores"])
    atual = estado["vez"]
    while True:
        proximo = (atual + 1) % total
        while estado["jogadores"][proximo]["falido"]:
            proximo = (proximo + 1) % total

        # Voltar para alguém antes de quem acabou de jogar significa rodada nova.
        if proximo <= atual:
            if estado.get("encerrar_apos_rodada") is not None and estado["rodada"] >= estado["encerrar_apos_rodada"]:
                estado["vez"] = proximo
                return _encerrar_partida(estado, "tempo")
            estado["rodada"] += 1
            _log(estado, "rodada", f"Rodada {estado['rodada']}.")
            _iniciar_rodada(estado)

        # Preso perde a vez e a pena anda. Cada volta desconta uma vez de
        # alguém, então o laço termina mesmo com a mesa inteira presa.
        candidato = estado["jogadores"][proximo]
        if candidato.get("preso", 0) > 0:
            candidato["preso"] -= 1
            resto = candidato["preso"]
            depois = f" Ainda faltam {resto} rodada(s)." if resto else " Na próxima rodada, volta a jogar."
            _log(estado, "prisao", f"{candidato['nome']} está na prisão e perde a vez.{depois}", candidato["jogador_id"])
            atual = proximo
            continue
        break

    estado["vez"] = proximo
    estado["fase"] = FASE_ROLAR
    _definir_prazo(estado, agora)
    _log(estado, "vez", f"É a vez de {estado['jogadores'][proximo]['nome']}.",
         estado["jogadores"][proximo]["jogador_id"])
    return estado


def atualizar_tempo(estado: dict, agora: float | None = None) -> dict:
    """Aplica a ação padrão quando o prazo do turno termina."""
    estado = _atualizar(estado)
    instante = time.time() if agora is None else agora
    prazo_partida = estado.get("prazo_partida")
    if (
        prazo_partida is not None
        and instante >= prazo_partida
        and estado.get("encerrar_apos_rodada") is None
        and estado["fase"] not in (FASE_SORTEIO, FASE_FIM)
    ):
        estado = copy.deepcopy(estado)
        _observar_prazo_partida(estado, instante)

    prazo = estado.get("prazo_vez")
    if prazo is None or estado["fase"] in (FASE_SORTEIO, FASE_FIM):
        return estado

    if instante < prazo:
        return estado

    estado = copy.deepcopy(estado)
    if estado["fase"] == FASE_LEILAO and estado.get("leilao"):
        # O fim do leilão não passa a vez: quem vendeu ainda rola.
        return _fechar_leilao(estado, instante)
    jogador = _jogador_da_vez(estado)
    if estado["fase"] == FASE_COMPRA and estado.get("compra_pendente"):
        _log(estado, "tempo", f"Tempo esgotado: {jogador['nome']} não comprou o terreno.", jogador["jogador_id"])
    elif estado["fase"] == FASE_COMPRA_JOGADOR and estado.get("compra_pendente"):
        pendente = estado["compra_pendente"]
        propriedade = estado["propriedades"].get(str(pendente["casa"]))
        vendedor = next((j for j in estado["jogadores"] if j["jogador_id"] == pendente["vendedor_id"]), None)
        casa = carregar_tabuleiro(estado["tabuleiro"]).casa(pendente["casa"])
        _log(estado, "tempo", f"Tempo esgotado: {jogador['nome']} não comprou a propriedade.", jogador["jogador_id"])
        if propriedade and vendedor and propriedade["dono"] == vendedor["jogador_id"] and not vendedor["falido"]:
            estado["compra_pendente"] = None
            estado = _resolver_aluguel(estado, jogador, vendedor, casa, propriedade)
            if estado["fase"] in (FASE_LIQUIDACAO_ALUGUEL, FASE_FIM) or jogador["falido"]:
                return estado
    elif estado["fase"] == FASE_MELHORIA and estado.get("melhoria_pendente"):
        _log(estado, "tempo", f"Tempo esgotado: {jogador['nome']} não melhorou a propriedade.", jogador["jogador_id"])
    elif estado["fase"] == FASE_LIQUIDACAO_ALUGUEL and estado.get("aluguel_pendente"):
        pendente = estado["aluguel_pendente"]
        dono = _jogador_por_id(estado, pendente["dono_id"])
        if dono["falido"]:
            # O credor saiu da mesa: `_encerrar_liquidacao` perdoa a dívida.
            return _encerrar_liquidacao(estado)
        estado = _falir(estado, jogador, dono, pendente["divida"])
        return estado
    elif estado["fase"] == FASE_CORINGA and estado.get("coringa_pendente"):
        _log(estado, "tempo", f"Tempo esgotado: {jogador['nome']} não arriscou na Casa Coringa.", jogador["jogador_id"])
        estado["ultimo_coringa"] = {"n": estado["log_n"], "jogador_id": jogador["jogador_id"], "arriscou": False}
    elif estado["fase"] == FASE_RECONSTRUCAO and estado.get("reconstrucao_pendente"):
        _log(estado, "tempo", f"Tempo esgotado: {jogador['nome']} não reformou nada.", jogador["jogador_id"])
    elif estado["fase"] == FASE_PREJUIZO and estado.get("prejuizo_pendente"):
        # A ação padrão é a mais dura: a propriedade mais valiosa da lista.
        pendente = estado["prejuizo_pendente"]
        _log(estado, "tempo", "Tempo esgotado: o Prejuízo tirou a propriedade mais valiosa da lista.", jogador["jogador_id"])
        validas = _prejuizo_ainda_valido(estado, pendente)
        if validas:
            _aplicar_prejuizo(estado, _jogador_por_id(estado, pendente["alvo_id"]), validas[0])
    elif estado["fase"] == FASE_BONUS_BANCO:
        _log(estado, "tempo", f"Tempo esgotado: {jogador['nome']} não vendeu nada ao banco.", jogador["jogador_id"])
    else:
        _log(estado, "tempo", f"Tempo esgotado: a vez de {jogador['nome']} passou.", jogador["jogador_id"])

    estado["prazo_vez"] = None
    return passar_turno(estado, agora=instante)


# --------------------------------------------------------------------------
# o que a tela recebe
# --------------------------------------------------------------------------

def _propriedades_publicas(estado: dict) -> dict:
    """Posse de cada casa, com os valores já calculados.

    A tela mostra aluguel, custo de melhoria e quanto o banco paga; se ela
    refizesse essas contas, qualquer ajuste no balanceamento deixaria a tela
    mostrando um número e o motor cobrando outro.
    """
    tabuleiro = carregar_tabuleiro(estado["tabuleiro"])
    maximo = _niveis_maximos(estado)
    evento = _evento_ativo(estado)
    bonus = bool(evento and evento["tipo"] == "bonus_do_banco")
    publicas = {}
    for indice, propriedade in estado.get("propriedades", {}).items():
        casa = tabuleiro.casa(int(indice))
        nivel = int(propriedade.get("nivel", 0))
        multiplicador, no_morro = _bonus_do_morro(estado, casa, propriedade["dono"])
        publicas[indice] = {
            **propriedade,
            "nivel_maximo": maximo,
            "aluguel": _valor_aluguel(estado, casa, propriedade),
            "aluguel_proximo_nivel": (
                _valor_aluguel(estado, casa, {**propriedade, "nivel": nivel + 1}) if nivel < maximo else None
            ),
            "custo_melhoria": _valor_upgrade(estado, casa) if nivel < maximo else None,
            "preco_compra": _valor_investido(estado, casa, propriedade),
            "valor_banco": _valor_venda_banco(estado, casa, propriedade),
            "valor_bonus": _valor_no_bonus(estado, casa, propriedade) if bonus else None,
            "valor_leilao_banco": _oferta_do_banco_no_leilao(estado, casa, propriedade),
            # Casas do Morro do mesmo dono e o multiplicador que elas dão.
            "morro": {"casas": no_morro, "multiplicador": multiplicador} if no_morro else None,
        }
    return publicas


def _leilao_publico(estado: dict) -> dict | None:
    """O leilão aberto, com o que a tela precisa já calculado: quem lidera,
    o próximo lance aceito e quanto falta, em milissegundos — a barra do
    relógio anda mais lisa que os segundos inteiros da vez."""
    leilao = estado.get("leilao")
    if not leilao:
        return None
    lider = _lider_do_leilao(leilao)
    prazo = estado.get("prazo_vez")
    return {
        **leilao,
        "lance_atual": lider["valor"] if lider else None,
        "lider_id": lider["jogador_id"] if lider else None,
        "minimo": _lance_minimo(leilao),
        "ms_restantes": None if prazo is None else max(0, int((prazo - time.time()) * 1000)),
    }


def estado_publico(estado: dict, jogador_id: int | None = None) -> dict:
    """Nada aqui é secreto — todo mundo vê o mesmo tabuleiro. A função existe
    para marcar quem é 'você' e para não vazar a semente, que permitiria
    prever os dados."""
    estado = _atualizar(estado)
    da_vez = _jogador_da_vez(estado)
    prazo = estado.get("prazo_vez")
    restante = None if prazo is None else max(0, int(prazo - time.time() + 0.999))
    prazo_partida = estado.get("prazo_partida")
    restante_partida = None if prazo_partida is None else max(0, int(prazo_partida - time.time() + 0.999))
    eu = next((j for j in estado["jogadores"] if j["jogador_id"] == jogador_id), None)
    # Se EU posso leiloar agora e, se não, por quê: a tela mostra o motivo.
    leilao_disponivel = None
    if eu is not None and not eu["falido"] and estado["fase"] not in (FASE_SORTEIO, FASE_FIM):
        motivo = _por_que_nao_leiloa(estado, eu)
        leilao_disponivel = {"pode": motivo is None, "motivo": motivo}
    return {
        "fase": estado["fase"],
        "prazo_vez": estado.get("prazo_vez"),
        "segundos_restantes": restante,
        "prazo_partida": prazo_partida,
        "segundos_partida_restantes": restante_partida,
        "minutos_de_partida": estado.get("minutos_de_partida"),
        "encerrar_apos_rodada": estado.get("encerrar_apos_rodada"),
        "motivo_fim": estado.get("motivo_fim"),
        "vencedores": estado.get("vencedores", []),
        "patrimonios_finais": estado.get("patrimonios_finais", {}),
        "classificacao": estado.get("classificacao", []),
        "rodada": estado["rodada"],
        "vez": {
            "jogador_id": da_vez["jogador_id"],
            "nome": da_vez["nome"],
            "sou_eu": da_vez["jogador_id"] == jogador_id,
        },
        "jogadores": [
            {
                "jogador_id": j["jogador_id"],
                "nome": j["nome"],
                "personagem": j["personagem"],
                "visual": j.get("visual"),
                "caixa": j["caixa"],
                "patrimonio": 0 if j["falido"] else _patrimonio(estado, j),
                "posicao": j["posicao"],
                "falido": j["falido"],
                "abandonou": j.get("abandonou", False),
                "preso": j.get("preso", 0),
                "placar": j.get("placar", PLACAR_VAZIO),
                "sou_eu": j["jogador_id"] == jogador_id,
            }
            for j in estado["jogadores"]
        ],
        "sorteio": estado["sorteio"],
        "propriedades": _propriedades_publicas(estado),
        "coletor": estado.get("coletor", 0),
        "evento": _evento_ativo(estado),
        "pode_vender_no_bonus": bool(
            eu
            and da_vez is eu
            and estado["fase"] in (FASE_ROLAR, FASE_BONUS_BANCO)
            and _bonus_disponivel(estado, eu)
        ),
        "compra_pendente": estado.get("compra_pendente"),
        "aluguel_pendente": estado.get("aluguel_pendente"),
        "melhoria_pendente": estado.get("melhoria_pendente"),
        "coringa_pendente": estado.get("coringa_pendente"),
        "reconstrucao_pendente": estado.get("reconstrucao_pendente"),
        "prejuizo_pendente": estado.get("prejuizo_pendente"),
        "leilao": _leilao_publico(estado),
        "ultimo_leilao": estado.get("ultimo_leilao"),
        "leilao_disponivel": leilao_disponivel,
        "ultimo_coringa": estado.get("ultimo_coringa"),
        "ultimo_movimento": estado["ultimo_movimento"],
        "log": estado["log"][-25:],
    }

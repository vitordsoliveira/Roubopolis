
from __future__ import annotations

import colorsys

import numpy as np
from PIL import Image, ImageDraw

#: Lado do quadradinho copiado é 2*RAIO+1. Maior acompanha melhor as
#: linhas longas; menor erra menos em detalhe miúdo.
RAIO = 4

#: Retângulos (x0, y0, x1, y1) de onde NADA pode ser copiado: motos,
#: pedestres, postes. Sem isto, um pedaço de moto vira remendo no asfalto.
NAO_COPIAR = [
    (78, 578, 140, 628),     # motos paradas no começo da rua da esquerda
    (455, 716, 520, 774),    # moto parada junto do ponto de ônibus
    (1268, 608, 1332, 672),  # moto parada perto do muro
    (240, 580, 262, 610),    # pedestre em frente ao VILA VIVE
    (1025, 745, 1055, 805),  # pedestres da barraca
    (940, 780, 965, 825),
    (515, 395, 560, 475),    # menino de fora do alambrado
    (92, 486, 195, 582),     # van parada no começo da rua da esquerda
    (380, 655, 402, 704),    # lixeira verde da calçada
    (1338, 562, 1356, 652),  # poste perto do quiosque
    (1408, 556, 1436, 612),  # homem do quiosque
]

#: O que some da pintura. nome -> (polígono que cobre a figura e a sombra
#: dela, janela onde procurar o que copiar).
APAGAR = {
    "menino do alambrado": ([(570, 372), (598, 372), (599, 422), (570, 422)], (520, 330, 720, 500)),
    "menino do gol": ([(636, 387), (664, 387), (665, 437), (636, 437)], (560, 330, 730, 500)),
    "menino de vermelho": ([(552, 422), (584, 422), (585, 475), (552, 475)], (500, 360, 700, 510)),
    "menino de branco": ([(597, 417), (636, 417), (637, 469), (597, 469)], (520, 360, 720, 510)),
    "rapaz do muro": ([(1222, 643), (1251, 643), (1252, 694), (1222, 694)], (1120, 600, 1330, 740)),
}

#: Direção de cada rua na pintura: quanto ela desce por pixel andado para a
#: direita. Medida pelos tracinhos amarelos do meio (só os pequenos, e só
#: dentro do asfalto — o táxi e a coroa pichada no muro também são amarelos
#: e já estragaram essa medida uma vez). A arte não é um isométrico perfeito:
#: as duas ruas não têm a mesma inclinação.
RUA_DA_ESQUERDA = 0.5467
RUA_DA_DIREITA = -0.6071

#: Carros que viram trânsito. `ancora` é o ponto do chão entre as duas rodas
#: visíveis — o ponto que a tela faz correr pela faixa (cidade_viva.js
#: guarda a direção das ruas; a posição sai daqui).
VEICULOS = {
    "carro-vermelho": {
        "poligono": [(221, 646), (258, 623), (304, 623), (349, 648), (351, 717), (292, 722), (221, 692)],
        "lataria": (0.95, 0.05),  # faixa de tom (0-1) da tinta; vermelho dá a volta no zero
        "janela": (0, 540, 700, 800),
        "rua": RUA_DA_ESQUERDA,
        "ancora": (267.5, 695.0),
        "direcao": "desce-direita",
    },
    "taxi": {
        "poligono": [(1086, 741), (1118, 704), (1166, 698), (1205, 718), (1207, 760), (1152, 792), (1098, 792), (1086, 772)],
        "lataria": (0.09, 0.17),
        "janela": (840, 560, 1420, 900),
        "rua": RUA_DA_DIREITA,
        "ancora": (1162.0, 764.0),
        "direcao": "desce-esquerda",
    },
}

#: Contorno do carro: a lataria, alargada até pegar para-choque, pneu e
#: farol, mais a sombra no chão logo abaixo.
MARGEM_DO_CARRO = 3
SOMBRA_DO_CARRO = 9

#: Até onde, ao longo da rua, se procura o trecho para copiar. Longe demais,
#: qualquer erro na inclinação vira alguns pixels de desvio e a busca sai
#: da faixa certa.
ALCANCE_NA_RUA = 170
#: Quanto cada pixel de distância pesa contra a fonte: prefere o trecho de
#: rua mais perto, que é o mais parecido com o que o carro cobria.
PESO_DA_DISTANCIA = 1.5

#: Outras cores do carro vermelho: tom (0-360) que a lataria passa a ter.
CORES_DO_CARRO = {"carro-azul": 212, "carro-verde": 128, "carro-roxo": 280}

#: Postes da calçada da frente: retângulos apertados em volta de cada um.
#: Dentro deles, o que é escuro é poste.
POSTES = [
    (363, 624, 381, 753),
    (467, 715, 491, 823),
    (643, 814, 663, 917),
    (959, 817, 975, 875),
    (1061, 735, 1079, 821),
    (1251, 647, 1267, 704),
]
ESCURO_DE_POSTE = 70  # luminância abaixo disto é poste

#: Quanto a cor precisa mudar entre a pintura e o fundo refeito para o
#: pixel contar como carro, e não como asfalto, no recorte.
LIMIAR_DO_RECORTE = 30.0


# --------------------------------------------------------------------------
# máscaras
# --------------------------------------------------------------------------

def _poligono(forma: tuple[int, int], pontos) -> np.ndarray:
    mascara = Image.new("L", (forma[1], forma[0]), 0)
    ImageDraw.Draw(mascara).polygon(pontos, fill=255)
    return np.array(mascara) > 0


def _retangulos(forma, caixas) -> np.ndarray:
    m = np.zeros(forma, dtype=bool)
    for x0, y0, x1, y1 in caixas:
        m[y0:y1, x0:x1] = True
    return m


def _crescer(mascara: np.ndarray, vezes: int = 1) -> np.ndarray:
    """Dilatação pela vizinhança de 8, sem depender de scipy."""
    m = mascara.copy()
    for _ in range(vezes):
        n = m.copy()
        n[1:, :] |= m[:-1, :]
        n[:-1, :] |= m[1:, :]
        n[:, 1:] |= m[:, :-1]
        n[:, :-1] |= m[:, 1:]
        n[1:, 1:] |= m[:-1, :-1]
        n[:-1, :-1] |= m[1:, 1:]
        n[1:, :-1] |= m[:-1, 1:]
        n[:-1, 1:] |= m[1:, :-1]
        m = n
    return m


def _encolher(mascara: np.ndarray, vezes: int = 1) -> np.ndarray:
    return ~_crescer(~mascara, vezes)


def _casca_convexa(pontos: np.ndarray) -> list[tuple[int, int]]:
    """Menor polígono convexo que contém os pontos (cadeia monótona)."""
    pts = sorted(set(map(tuple, pontos.tolist())))
    if len(pts) < 3:
        return pts

    def giro(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    baixo, cima = [], []
    for p in pts:
        while len(baixo) >= 2 and giro(baixo[-2], baixo[-1], p) <= 0:
            baixo.pop()
        baixo.append(p)
    for p in reversed(pts):
        while len(cima) >= 2 and giro(cima[-2], cima[-1], p) <= 0:
            cima.pop()
        cima.append(p)
    return baixo[:-1] + cima[:-1]


def _contorno_do_carro(original: np.ndarray, poligono, lataria) -> np.ndarray:
    """Onde o carro está, justo: a casca da lataria, com margem e sombra.

    Um carro visto de cima é quase convexo, então a casca da tinta já cobre
    vidros e teto; a margem pega o que sai da tinta (pneu, farol,
    para-choque) e a faixa de baixo pega a sombra no chão. Apagar só isto, e
    não o polígono folgado, é o que deixa o muro e o arbusto de trás intactos.
    """
    area = _poligono(original.shape[:2], poligono)
    rgb = original[..., :3].astype(np.float32) / 255
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    tom = np.zeros_like(mx)
    d = np.maximum(mx - mn, 1e-6)
    tom = np.where(mx == r, ((g - b) / d) % 6, tom)
    tom = np.where(mx == g, (b - r) / d + 2, tom)
    tom = np.where(mx == b, (r - g) / d + 4, tom)
    tom = tom / 6
    t0, t1 = lataria
    no_tom = (tom >= t0) | (tom <= t1) if t0 > t1 else (tom >= t0) & (tom <= t1)
    tinta = _maior_pedaco(area & no_tom & (sat > 0.45) & (mx > 0.35))
    ys, xs = np.nonzero(tinta)
    casca = _casca_convexa(np.stack([xs, ys], axis=1))
    carro = _crescer(_poligono(original.shape[:2], casca), MARGEM_DO_CARRO)
    sombra = np.zeros_like(carro)
    sombra[SOMBRA_DO_CARRO:] = carro[:-SOMBRA_DO_CARRO]
    return (carro | sombra) & area


def _integral(a: np.ndarray) -> np.ndarray:
    s = np.zeros((a.shape[0] + 1, a.shape[1] + 1), dtype=np.float64)
    s[1:, 1:] = a.cumsum(0).cumsum(1)
    return s


def _soma_em_volta(a: np.ndarray, raio: int) -> np.ndarray:
    """Soma de `a` no quadrado de lado 2*raio+1 em volta de cada pixel."""
    s = _integral(a)
    h, w = a.shape
    ys, xs = np.arange(h), np.arange(w)
    y0, y1 = np.clip(ys - raio, 0, h), np.clip(ys + raio + 1, 0, h)
    x0, x1 = np.clip(xs - raio, 0, w), np.clip(xs + raio + 1, 0, w)
    return s[y1][:, x1] - s[y0][:, x1] - s[y1][:, x0] + s[y0][:, x0]


# --------------------------------------------------------------------------
# preenchimento por exemplos
# --------------------------------------------------------------------------

def _procurar_na_rua(cor, fonte, alvo, sabido, py, px, inclinacao):
    """Melhor quadradinho-fonte andando ao longo da rua a partir do alvo.

    Numa rua, o que está 150 px para o lado na mesma altura da faixa é o
    mesmo asfalto, o mesmo meio-fio, a mesma calçada. Procurar só nessa
    linha (com folga de 2 px para os lados) é o que impede de trazer
    calçada para o meio do asfalto — foi o que a busca livre fez nos carros.
    Devolve o canto do quadradinho escolhido, ou None se não houver nenhum.
    """
    r = RAIO
    h, w = cor.shape[:2]
    passos = np.arange(-ALCANCE_NA_RUA, ALCANCE_NA_RUA + 1)
    passos = passos[np.abs(passos) > r]
    tt, ee = np.meshgrid(passos, np.arange(-2, 3))
    cy = (py + np.rint(tt * inclinacao + ee)).astype(int).ravel()
    cx = (px + tt).astype(int).ravel()
    dentro = (cy >= r) & (cy < h - r) & (cx >= r) & (cx < w - r)
    cy, cx = cy[dentro], cx[dentro]
    livre = fonte[cy - r, cx - r]
    cy, cx = cy[livre], cx[livre]
    if not len(cy):
        return None
    ky, kx = np.nonzero(sabido)
    amostras = cor[cy[:, None] + ky[None, :] - r, cx[:, None] + kx[None, :] - r]
    dist = ((amostras - alvo[ky, kx][None]) ** 2).sum(axis=(1, 2))
    dist += PESO_DA_DISTANCIA * np.hypot(cy - py, cx - px)
    j = int(np.argmin(dist))
    return cy[j] - r, cx[j] - r


def _preencher(img: np.ndarray, falta: np.ndarray, proibido: np.ndarray, janela, rua=None) -> None:
    """Fecha o buraco `falta` copiando da vizinhança. Altera `img` no lugar.

    Com `rua` (a inclinação dela), copia só ao longo da rua; sem, procura na
    janela inteira."""
    x0, y0, x1, y1 = janela
    r = RAIO
    k = 2 * r + 1
    cor = img[y0:y1, x0:x1, :3].astype(np.float32)
    alfa = img[y0:y1, x0:x1, 3]
    buraco = falta[y0:y1, x0:x1].copy()
    h, w = buraco.shape
    if buraco[:r].any() or buraco[-r:].any() or buraco[:, :r].any() or buraco[:, -r:].any():
        raise ValueError(f"a janela {janela} precisa sobrar pelo menos {r} px em volta do buraco")

    # De onde se pode copiar: quadradinhos inteiros de pintura boa — nada do
    # buraco, nada proibido, nada fora da cidade (fundo transparente).
    ruim = buraco | proibido[y0:y1, x0:x1] | (alfa < 250)
    fonte = _soma_em_volta(ruim.astype(np.float32), r) == 0
    fonte[:r] = fonte[-r:] = False
    fonte[:, :r] = fonte[:, -r:] = False
    fonte = fonte[r:h - r, r:w - r]
    if not fonte.any():
        raise ValueError(f"nada para copiar na janela {janela}")

    confianca = (~buraco).astype(np.float32)

    while buraco.any():
        conhecido = ~buraco
        vizinho = np.zeros_like(buraco)
        vizinho[1:, :] |= conhecido[:-1, :]
        vizinho[:-1, :] |= conhecido[1:, :]
        vizinho[:, 1:] |= conhecido[:, :-1]
        vizinho[:, :-1] |= conhecido[:, 1:]
        ys, xs = np.nonzero(buraco & vizinho)

        # Confiança: quanto do quadradinho em volta já é pintura confiável.
        c = _soma_em_volta(confianca, r)[ys, xs] / (k * k)

        # Termo de estrutura: linha forte chegando de frente na borda do
        # buraco ganha prioridade, para atravessar o buraco reta.
        cinza = cor.mean(axis=2)
        gy, gx = np.gradient(cinza)
        confiavel = _encolher(conhecido, 1)
        gx[~confiavel] = 0
        gy[~confiavel] = 0
        ny, nx = np.gradient(buraco.astype(np.float32))
        dados = np.empty(len(ys), dtype=np.float32)
        for i, (py, px) in enumerate(zip(ys, xs)):
            a0, a1 = max(py - r, 0), min(py + r + 1, h)
            b0, b1 = max(px - r, 0), min(px + r + 1, w)
            mag = gx[a0:a1, b0:b1] ** 2 + gy[a0:a1, b0:b1] ** 2
            j = np.unravel_index(np.argmax(mag), mag.shape)
            iso_x, iso_y = -gy[a0 + j[0], b0 + j[1]], gx[a0 + j[0], b0 + j[1]]
            n = np.hypot(nx[py, px], ny[py, px]) or 1.0
            dados[i] = abs(iso_x * nx[py, px] / n + iso_y * ny[py, px] / n) / 127.0

        i = int(np.argmax(c * (0.15 + dados)))
        py = int(np.clip(ys[i], r, h - r - 1))
        px = int(np.clip(xs[i], r, w - r - 1))

        alvo = cor[py - r:py + r + 1, px - r:px + r + 1]
        sabido = conhecido[py - r:py + r + 1, px - r:px + r + 1]

        achado = _procurar_na_rua(cor, fonte, alvo, sabido, py, px, rua) if rua is not None else None
        if achado is not None:
            qy, qx = achado
        else:
            # Distância de cada quadradinho-fonte ao alvo, só nos pixels que
            # o alvo já tem. Um laço pelos 81 deslocamentos, sem montar o
            # bloco gigante de todos os quadradinhos de uma vez.
            dist = np.zeros((h - 2 * r, w - 2 * r), dtype=np.float32)
            for dy in range(k):
                for dx in range(k):
                    if sabido[dy, dx]:
                        d = cor[dy:dy + h - 2 * r, dx:dx + w - 2 * r] - alvo[dy, dx]
                        dist += (d * d).sum(axis=2)
            dist[~fonte] = np.inf
            # Empate fica com o mais perto: o vizinho costuma ser o mais parecido.
            yy, xx = np.mgrid[0:h - 2 * r, 0:w - 2 * r]
            dist += 0.02 * ((yy + r - py) ** 2 + (xx + r - px) ** 2) ** 0.5
            qy, qx = np.unravel_index(np.argmin(dist), dist.shape)

        falta_aqui = buraco[py - r:py + r + 1, px - r:px + r + 1]
        origem = cor[qy:qy + k, qx:qx + k]
        alvo[falta_aqui] = origem[falta_aqui]
        confianca[py - r:py + r + 1, px - r:px + r + 1][falta_aqui] = c[i]
        buraco[py - r:py + r + 1, px - r:px + r + 1][falta_aqui] = False

    img[y0:y1, x0:x1, :3] = np.clip(np.rint(cor), 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------
# recortes
# --------------------------------------------------------------------------

def _maior_pedaco(mascara: np.ndarray) -> np.ndarray:
    """Fica só com o maior pedaço conectado (o carro), sem os respingos."""
    rotulo = np.zeros(mascara.shape, dtype=np.int32)
    tamanhos = [0]
    atual = 0
    for y, x in zip(*np.nonzero(mascara)):
        if rotulo[y, x]:
            continue
        atual += 1
        pilha = [(y, x)]
        rotulo[y, x] = atual
        n = 0
        while pilha:
            cy, cx = pilha.pop()
            n += 1
            for vy, vx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= vy < mascara.shape[0] and 0 <= vx < mascara.shape[1] and mascara[vy, vx] and not rotulo[vy, vx]:
                    rotulo[vy, vx] = atual
                    pilha.append((vy, vx))
        tamanhos.append(n)
    if atual == 0:
        return mascara
    return rotulo == int(np.argmax(tamanhos))


def _sem_buracos(mascara: np.ndarray) -> np.ndarray:
    """O que não se alcança pela borda sem cruzar a máscara é dela: vidro
    escuro, sombra entre as rodas."""
    fora = np.zeros_like(mascara)
    h, w = mascara.shape
    pilha = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    while pilha:
        y, x = pilha.pop()
        if fora[y, x] or mascara[y, x]:
            continue
        fora[y, x] = True
        for vy, vx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= vy < h and 0 <= vx < w and not fora[vy, vx]:
                pilha.append((vy, vx))
    return ~fora


def _recortar(original: np.ndarray, limpa: np.ndarray, contorno: np.ndarray) -> tuple[Image.Image, tuple[int, int]]:
    """O carro é o que a pintura tem e o fundo refeito não tem.

    O contorno já é justo; a diferença para o fundo refeito só tira dele o
    asfalto que sobrou nos cantos, para o carro não andar com um pedaço de
    rua grudado."""
    ys, xs = np.nonzero(contorno)
    bx0, by0, bx1, by1 = xs.min() - 1, ys.min() - 1, xs.max() + 2, ys.max() + 2
    area = contorno[by0:by1, bx0:bx1]
    o = original[by0:by1, bx0:bx1, :3].astype(float)
    l_ = limpa[by0:by1, bx0:bx1, :3].astype(float)
    diferenca = np.sqrt(((o - l_) ** 2).sum(axis=2))
    aqui = area & (diferenca > LIMIAR_DO_RECORTE)
    aqui = _encolher(_crescer(aqui, 2), 2) & area  # fecha as frestas
    carro = np.zeros(contorno.shape, dtype=bool)
    carro[by0:by1, bx0:bx1] = _sem_buracos(_maior_pedaco(aqui))
    ys, xs = np.nonzero(carro)
    x0, y0, x1, y1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
    sprite = np.zeros((y1 - y0, x1 - x0, 4), dtype=np.uint8)
    sprite[carro[y0:y1, x0:x1]] = original[y0:y1, x0:x1][carro[y0:y1, x0:x1]]
    return Image.fromarray(sprite), (int(x0), int(y0))


def recolorir(sprite: Image.Image, tom: float) -> Image.Image:
    """Troca a cor da lataria (os pixels vermelhos e saturados) e deixa
    vidro, pneu e farol como estão."""
    a = np.array(sprite.convert("RGBA")).astype(np.float32) / 255
    saida = a.copy()
    for y, x in zip(*np.nonzero(a[..., 3] > 0)):
        h, s, v = colorsys.rgb_to_hsv(*a[y, x, :3])
        vermelho = (h < 0.06 or h > 0.93) and s > 0.35
        if vermelho:
            saida[y, x, :3] = colorsys.hsv_to_rgb(tom / 360, s, v)
    return Image.fromarray(np.clip(np.rint(saida * 255), 0, 255).astype(np.uint8))


def _camada_da_frente(original: np.ndarray) -> Image.Image:
    """Só os postes, no mesmo lugar da pintura: por cima da cidade eles não
    mudam nada, e por cima de um carro que passa atrás, aparecem.

    O poste é uma coluna estreita; só a luminária, em cima, e a base, embaixo,
    são mais largas. Pegar o retângulo inteiro trazia junto a moto parada
    colada num deles — e ela passaria na frente dos carros."""
    lum = original[..., :3].astype(float) @ np.array([0.299, 0.587, 0.114])
    frente = np.zeros_like(original)
    for x0, y0, x1, y1 in POSTES:
        escuro = lum[y0:y1, x0:x1] < ESCURO_DE_POSTE
        eixo = int(np.argmax(escuro.sum(axis=0)))
        altura = y1 - y0
        largura = np.full(altura, 3)
        largura[:16] = 9   # luminária
        largura[-12:] = 6  # base de concreto
        xs = np.arange(x1 - x0)[None, :]
        coluna = np.abs(xs - eixo) <= largura[:, None]
        poste = _crescer(escuro & coluna, 1) & coluna & (lum[y0:y1, x0:x1] < ESCURO_DE_POSTE + 45)
        frente[y0:y1, x0:x1][poste] = original[y0:y1, x0:x1][poste]
    return Image.fromarray(frente)


# --------------------------------------------------------------------------

def processar(cidade: Image.Image) -> dict:
    """Devolve a cidade limpa, os carros recortados e a camada da frente."""
    original = np.array(cidade.convert("RGBA"))
    forma = original.shape[:2]
    limpa = original.copy()

    buracos = {nome: _poligono(forma, pontos) for nome, (pontos, _) in APAGAR.items()}
    buracos.update({nome: _contorno_do_carro(original, v["poligono"], v["lataria"]) for nome, v in VEICULOS.items()})
    # Nada se copia de dentro de outra figura, nem do polígono folgado dos
    # carros: o que sobra nele fora do contorno ainda pode ter sombra.
    proibido = _retangulos(forma, NAO_COPIAR) | _retangulos(forma, POSTES)
    for m in buracos.values():
        proibido |= m
    for v in VEICULOS.values():
        proibido |= _poligono(forma, v["poligono"])

    for nome, (_, janela) in APAGAR.items():
        _preencher(limpa, buracos[nome], proibido, janela)
    for nome, v in VEICULOS.items():
        _preencher(limpa, buracos[nome], proibido, v["janela"], rua=v["rua"])

    carros = {}
    for nome, v in VEICULOS.items():
        sprite, (bx, by) = _recortar(original, limpa, buracos[nome])
        ax, ay = v["ancora"]
        carros[nome] = {
            "imagem": sprite,
            "ancora": (ax - bx, ay - by),
            "pintado_em": (ax, ay),
            "direcao": v["direcao"],
            "rua": v["rua"],
        }
    base = carros["carro-vermelho"]
    for nome, tom in CORES_DO_CARRO.items():
        carros[nome] = {**base, "imagem": recolorir(base["imagem"], tom), "pintado_em": None}

    return {
        "cidade": Image.fromarray(limpa),
        "carros": carros,
        "frente": _camada_da_frente(original),
    }

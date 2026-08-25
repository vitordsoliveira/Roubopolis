"""Transforma img/objetos/ (arte crua do designer) em client/assets/ (arte web).

Rode de novo sempre que a arte mudar:

    python ferramentas/preparar_assets.py

O que ele faz:
  - recorta cada PNG na área que realmente tem pixel (os botões vieram
    exportados na prancheta inteira, com a arte num canto);
  - recolore CIDADE VETOR nas duas versões das referências, extraindo a
    paleta das próprias imagens de referência;
  - reduz o que é grande demais para web e mantém o resto no tamanho
    original, porque sprite pequeno já está ótimo.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
ORIGEM = RAIZ / "img" / "objetos"
ORIGEM_FONTES = RAIZ / "fontes"
DESTINO = RAIZ / "client" / "assets"

#: arquivo de origem -> caminho de saída (sem recolorir, só recortar)
COPIAS = {
    "ROUBOPOLIS 2.png": "logo/roubodopolis.png",
    "JOGAR 1.png": "menu/jogar.png",
    "AMIGOS 1.png": "menu/amigos.png",
    "LOJA 1.png": "menu/loja.png",
    "CONFIGURAÇÃO 1.png": "menu/configuracao.png",
    "SAIR 1.png": "menu/sair.png",
    "VOLTAR 1.png": "menu/voltar.png",
    "BULLET 1.png": "ui/placa.png",
    "BULLET 2.png": "ui/placa-alta.png",
    "Group.png": "ui/baloes.png",
    "Group (1).png": "ui/faixa.png",
    "PERSONAGEM 1.png": "personagens/loh.png",
    "PERSONAGEM 2.png": "personagens/vitinhoxd.png",
    "PERSONAGEM 3.png": "personagens/festa.png",
    "PERSONAGEM 4.png": "personagens/andinho.png",
    "POLICIAL.png": "objetos/policial.png",
    "Group 5.png": "objetos/detetive.png",
    "Group 4 (1).png": "objetos/mulher.png",
    "Group 4.png": "objetos/mulher-loira.png",
    "COLAR.png": "objetos/colar.png",
    "DINHEIRO.png": "objetos/dinheiro.png",
    "OCULOS.png": "objetos/oculos.png",
    "NUVENS.png": "cenario/nuvens.png",
}

#: altura máxima por pasta. None = mantém o tamanho original.
LIMITE_ALTURA = {
    "logo": 400,
    "cenario": 900,
    "ui": 500,
    "personagens": None,
    "objetos": None,
}

#: Itens de menu recebem tratamento próprio: cada arquivo veio com uma
#: quantidade diferente de brilho em volta da palavra, então recortar pela
#: área com pixel deixaria JOGAR e CONFIGURAÇÃO com letras de tamanhos
#: diferentes. Normalizamos pela altura da LETRA e depois padronizamos a
#: altura da tela, para uma única regra de CSS servir para todos.
ALTURA_LETRA = 120
ALTURA_TELA_MENU = 178  # letra + o mínimo de folga para o brilho não cortar
ALFA_LETRA = 190  # acima disso é letra; abaixo é o brilho ao redor

#: Cores medidas a olho nu nas telas de referência, do mais escuro ao mais
#: claro: prédio da frente, prédio do meio, prédio do fundo, céu, topo do céu.
#: São elas que definem o clima de cada tela.
PALETAS = {
    "cenario/cidade-verde.png": ["#00b402", "#00d002", "#00fc01", "#c1ffb1", "#d2fde4"],
    "cenario/cidade-laranja.png": ["#8f1600", "#a31c00", "#f03e01", "#ff7611", "#ffa60b"],
}

#: Em que percentil de luz da arte base cada cor acima entra. Distribuir por
#: percentil (e não por valor fixo) faz o resultado respeitar a quantidade de
#: céu e de prédio que a imagem realmente tem.
PERCENTIS = [2, 18, 45, 78, 97]


def recortar(im: Image.Image) -> Image.Image:
    """Joga fora a prancheta vazia em volta da arte."""
    if im.mode in ("RGBA", "LA"):
        caixa = im.getchannel("A").getbbox()
        if caixa:
            return im.crop(caixa)
    return im


def redimensionar(im: Image.Image, altura_max: int | None) -> Image.Image:
    if not altura_max or im.height <= altura_max:
        return im
    largura = max(1, round(im.width * altura_max / im.height))
    # BOX faz média de área: em pixel art escalada, some sem borrar as bordas.
    return im.resize((largura, altura_max), Image.BOX)


# --------------------------------------------------------------------------
# recolorir a cidade
# --------------------------------------------------------------------------

def para_rgb(codigo: str) -> tuple[int, int, int]:
    codigo = codigo.lstrip("#")
    return tuple(int(codigo[i : i + 2], 16) for i in (0, 2, 4))


def recolorir(base: Image.Image, cores_hex: list[str]) -> Image.Image:
    """Repinta a cidade mantendo a estrutura de luz da arte original.

    Cada cor da paleta é ancorada num percentil de luminância da imagem base,
    e o que está entre duas âncoras é interpolado. O resultado é uma tabela de
    256 entradas por canal, que o Pillow aplica de uma vez com `point()` — sem
    laço em Python sobre milhões de pixels.
    """
    cores = [para_rgb(c) for c in cores_hex]
    cinza = base.convert("L")

    # onde cada percentil cai na escala de luz desta imagem
    histograma = cinza.histogram()
    total = sum(histograma)
    acumulado, soma = [], 0
    for valor in range(256):
        soma += histograma[valor]
        acumulado.append(soma / total)

    paradas = [
        next((i for i, a in enumerate(acumulado) if a >= p / 100), 255) for p in PERCENTIS
    ]

    tabelas: list[list[int]] = [[], [], []]
    for valor in range(256):
        if valor <= paradas[0]:
            cor = cores[0]
        elif valor >= paradas[-1]:
            cor = cores[-1]
        else:
            i = min(max(j for j, p in enumerate(paradas) if p <= valor), len(paradas) - 2)
            t = (valor - paradas[i]) / max(1, paradas[i + 1] - paradas[i])
            cor = tuple(round(cores[i][c] + (cores[i + 1][c] - cores[i][c]) * t) for c in range(3))
        for canal in range(3):
            tabelas[canal].append(cor[canal])

    return Image.merge("RGB", [cinza.point(t) for t in tabelas])


def gerar_cidades() -> None:
    base = redimensionar(Image.open(ORIGEM / "CIDADE VETOR.png").convert("RGB"), 900)

    for saida, paleta in PALETAS.items():
        destino = DESTINO / saida
        destino.parent.mkdir(parents=True, exist_ok=True)
        # 256 cores: a arte é chapada, não perde nada e o arquivo despenca.
        recolorir(base, paleta).quantize(colors=256).save(destino, optimize=True)
        print(f"  {saida:<32} {destino.stat().st_size // 1024} KB")


# --------------------------------------------------------------------------

def normalizar_item_de_menu(im: Image.Image) -> Image.Image:
    """Deixa a palavra do mesmo tamanho em todos os itens, brilho preservado."""
    solido = im.getchannel("A").point(lambda a: 255 if a >= ALFA_LETRA else 0)
    letra = solido.getbbox()
    if not letra:
        return im

    escala = ALTURA_LETRA / (letra[3] - letra[1])
    im = im.resize((max(1, round(im.width * escala)), max(1, round(im.height * escala))), Image.BOX)

    # centraliza pela letra, não pela imagem: o brilho é assimétrico
    meio_letra = (letra[1] + letra[3]) / 2 * escala
    tela = Image.new("RGBA", (im.width, ALTURA_TELA_MENU), (0, 0, 0, 0))
    tela.alpha_composite(im, (0, round(ALTURA_TELA_MENU / 2 - meio_letra)))
    return tela


def gerar_copias() -> None:
    for arquivo, saida in COPIAS.items():
        origem = ORIGEM / arquivo
        if not origem.exists():
            print(f"  AVISO: {arquivo} não encontrado")
            continue

        im = recortar(Image.open(origem).convert("RGBA"))
        pasta = saida.split("/")[0]
        antes = im.size

        if pasta == "menu":
            im = normalizar_item_de_menu(im)
        else:
            im = redimensionar(im, LIMITE_ALTURA.get(pasta))

        destino = DESTINO / saida
        destino.parent.mkdir(parents=True, exist_ok=True)
        im.save(destino, optimize=True)

        # O brilho neon dos títulos gera degradê, que infla o PNG. Reduzir a
        # 256 cores derruba o peso sem estragar arte chapada. FASTOCTREE é o
        # único método do Pillow que preserva a transparência.
        if destino.stat().st_size > 80 * 1024:
            im.quantize(colors=256, method=Image.FASTOCTREE).save(destino, optimize=True)

        mudou = "" if antes == im.size else f"  (era {antes[0]}x{antes[1]})"
        print(f"  {saida:<32} {im.width}x{im.height}  {destino.stat().st_size // 1024} KB{mudou}")


def copiar_fontes() -> None:
    """As fontes vão junto porque este script apaga client/assets/ inteiro."""
    if not ORIGEM_FONTES.exists():
        print(f"  AVISO: {ORIGEM_FONTES} não existe, nenhuma fonte copiada")
        return

    destino = DESTINO / "fontes"
    destino.mkdir(parents=True, exist_ok=True)
    for fonte in sorted(ORIGEM_FONTES.glob("*.[to]tf")):
        shutil.copy2(fonte, destino / fonte.name)
        print(f"  fontes/{fonte.name:<26} {fonte.stat().st_size // 1024} KB")


def main() -> int:
    if not ORIGEM.exists():
        print(f"Pasta de arte não encontrada: {ORIGEM}")
        return 1

    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    DESTINO.mkdir(parents=True)

    print("Cenário recolorido a partir das referências:")
    gerar_cidades()
    print("\nFontes:")
    copiar_fontes()
    print("\nArte recortada:")
    gerar_copias()

    total = sum(f.stat().st_size for f in DESTINO.rglob("*.png"))
    print(f"\nTotal em client/assets/: {total // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

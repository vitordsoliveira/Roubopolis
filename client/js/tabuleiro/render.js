/* O tabuleiro da partida, em isométrico, desenhado em SVG.

   O tabuleiro de verdade é uma grade plana (u, v); a tela mostra a projeção
   dela. Tudo que fica PARADO no tabuleiro — as casas, os prédios, a cidade
   do miolo — é desenhado aqui, num SVG só. O que se mexe (peão, dado) mora
   em HTML por cima, e se posiciona com `ponto()`.

   Por que SVG e não CSS 3D, como era antes: a cidade do miolo
   (img/tabuleiro/CIDADE.png) já vem PINTADA em isométrico. Para ela encaixar
   no anel de casas, as casas precisam da mesma projeção da pintura — e isso
   só dá para garantir fazendo a conta aqui. Com rotateX/rotateZ do CSS a
   cidade seria projetada duas vezes.

   A ordem de desenho é a de um diorama: primeiro a base, depois as casas do
   fundo, a cidade, e só então as casas da frente. Assim o prédio alto que
   está na beira de trás da cidade cobre a casa que fica atrás dele, como
   cobriria de verdade. Os nomes das casas vêm por último, por cima de
   tudo, para nunca sumirem atrás de uma árvore. */

import { animarCidade } from "./cidade_viva.js";
import { grupoPixel, medidas } from "./pixel.js";

const SVG = "http://www.w3.org/2000/svg";

// --- medidas, em unidades do tabuleiro (1 = largura de uma casa da borda) --

/** Profundidade da casa, que é também o lado dos cantos: canto maior que as
    casas da borda, como no desenho. */
const FUNDO_CASA = 1.35;
const ALTURA_CASA = 0.24;
const ESPESSURA_BASE = 0.55;
const FRESTA = 0.05;
/** Folga entre o anel de casas e o meio-fio da cidade. */
const RECUO_CIDADE = 0.12;

// --- projeção ------------------------------------------------------------

/* A proporção vem da CIDADE.png: o chão dela, em losango, tem a altura
   igual a 64% da largura. Com qualquer outro achatamento a cidade não
   encaixa no anel. */
const A = 50; // px por unidade, na horizontal
const B = A * 0.64; // px por unidade, na vertical
const C = A * 1.08; // px por unidade de altura

/** O chão da CIDADE.png, medido na própria imagem (em pixels dela). Se a
    arte for trocada, é aqui que se remede. */
const CIDADE = {
  arquivo: "/assets/tabuleiro/cidade.webp",
  largura: 1536,
  altura: 1024,
  centroX: 767,
  centroY: 501.5,
  meiaLargura: 752,
  meioFio: 25,
};

/** De coordenada do tabuleiro (u, v, altura) para coordenada da tela. */
const tela = (u, v, z = 0) => [(u - v) * A, (u + v) * B - z * C];

// --- cores -----------------------------------------------------------------

/** As duas cores da legenda que não são grupo de propriedade — medidas na
    legenda da arte, como as dos grupos (que vêm do tabuleiro). */
const COR_EVENTO = "#0fb91f";
const COR_NEUTRA = "#fdfdfd";

const COR_BASE = "#23224e";
const COR_ASFALTO = "#2c2838";
const CHAO_DO_CENARIO = {
  praca: "#d7d3e0",
  represa: "#efe9da",
  prisao: "#c9dbea",
  mansao: "#4c1c58",
};

function rgb(cor) {
  const n = parseInt(cor.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function misturar(cor, alvo, t) {
  const a = rgb(cor);
  const b = rgb(alvo);
  return "#" + a.map((c, i) => Math.round(c + (b[i] - c) * t).toString(16).padStart(2, "0")).join("");
}

const escurecer = (cor, t) => misturar(cor, "#000000", t);
const clarear = (cor, t) => misturar(cor, "#ffffff", t);

/** Clara o bastante para pedir letra escura (branco e amarelo). */
function eClara(cor) {
  const [r, g, b] = rgb(cor);
  return 0.299 * r + 0.587 * g + 0.114 * b > 165;
}

function corDaCasa(casa, grupos) {
  if (casa.cenario) return CHAO_DO_CENARIO[casa.cenario] || COR_NEUTRA;
  if (casa.tipo === "propriedade") return grupos[casa.grupo]?.cor || "#999999";
  if (casa.tipo === "neutra" || casa.tipo === "inicial") return COR_NEUTRA;
  return COR_EVENTO;
}

/** A legenda na ordem da arte: os grupos do tabuleiro, do mais caro ao mais
    barato, depois evento e neutra. */
export function itensDaLegenda(dados) {
  return [
    ...dados.ordem_dos_grupos.map((chave) => ({ rotulo: dados.grupos[chave].rotulo, cor: dados.grupos[chave].cor })),
    { rotulo: "Casa evento", cor: COR_EVENTO },
    { rotulo: "Casa neutra", cor: COR_NEUTRA },
  ];
}

// --- SVG ---------------------------------------------------------------------

function no(tag, atributos, pai) {
  const el = document.createElementNS(SVG, tag);
  for (const [nome, valor] of Object.entries(atributos)) el.setAttribute(nome, String(valor));
  if (pai) pai.appendChild(el);
  return el;
}

function pontos(lista) {
  return lista.map(([u, v, z]) => tela(u, v, z).map((n) => n.toFixed(1)).join(",")).join(" ");
}

function face(pai, lista, cor, extra = {}) {
  return no("polygon", { points: pontos(lista), fill: cor, ...extra }, pai);
}

/** Caixa de (u0, v0, z0) a (u1, v1, z1). Só as três faces que a câmera vê:
    a da frente-esquerda (+v) pega luz, a da frente-direita (+u) fica na
    sombra. É a mesma luz da CIDADE.png. */
function caixa(pai, u0, v0, u1, v1, z0, z1, cor, tampo = cor) {
  face(pai, [[u0, v1, z1], [u1, v1, z1], [u1, v1, z0], [u0, v1, z0]], escurecer(cor, 0.2));
  face(pai, [[u1, v0, z1], [u1, v1, z1], [u1, v1, z0], [u1, v0, z0]], escurecer(cor, 0.4));
  return face(pai, [[u0, v0, z1], [u1, v0, z1], [u1, v1, z1], [u0, v1, z1]], tampo);
}

/** Telhado de quatro águas. As duas de trás primeiro: com o telhado baixo,
    a câmera enxerga as quatro. */
function telhado(pai, u0, v0, u1, v1, z, altura, cor) {
  const cume = [(u0 + u1) / 2, (v0 + v1) / 2, z + altura];
  face(pai, [[u0, v0, z], [u0, v1, z], cume], clarear(cor, 0.14));
  face(pai, [[u0, v0, z], [u1, v0, z], cume], cor);
  face(pai, [[u0, v1, z], [u1, v1, z], cume], escurecer(cor, 0.18));
  face(pai, [[u1, v0, z], [u1, v1, z], cume], escurecer(cor, 0.36));
}

/** Janelas nas duas paredes que aparecem, em `andares` fileiras. */
function janelas(pai, u0, v0, u1, v1, z0, z1, colunas, andares, cor) {
  const alturaAndar = (z1 - z0) / andares;
  for (let andar = 0; andar < andares; andar += 1) {
    const baixo = z0 + alturaAndar * (andar + 0.3);
    const cima = baixo + alturaAndar * 0.42;
    for (let k = 0; k < colunas; k += 1) {
      // Parede da frente-esquerda: corre em u, no plano v = v1.
      const passoU = (u1 - u0) / (colunas * 2 + 1);
      const ua = u0 + passoU * (k * 2 + 1);
      face(pai, [[ua, v1, cima], [ua + passoU, v1, cima], [ua + passoU, v1, baixo], [ua, v1, baixo]], cor);
      // Parede da frente-direita: corre em v, no plano u = u1.
      const passoV = (v1 - v0) / (colunas * 2 + 1);
      const va = v0 + passoV * (k * 2 + 1);
      face(pai, [[u1, va, cima], [u1, va + passoV, cima], [u1, va + passoV, baixo], [u1, va, baixo]],
        escurecer(cor, 0.25));
    }
  }
}

/** Ícone de pixel art em pé sobre o chão, com a sombrinha embaixo. */
function iconeEmPe(pai, nome, u, v, z, altura) {
  const { largura, altura: alturaMapa } = medidas(nome);
  const escala = altura / alturaMapa;
  const [x, y] = tela(u, v, z);
  no("ellipse", {
    cx: x.toFixed(1),
    cy: y.toFixed(1),
    rx: (largura * escala * 0.42).toFixed(1),
    ry: (largura * escala * 0.15).toFixed(1),
    fill: "rgba(0, 0, 0, 0.28)",
  }, pai);
  const g = grupoPixel(nome);
  g.setAttribute(
    "transform",
    `translate(${(x - (largura * escala) / 2).toFixed(1)} ${(y - alturaMapa * escala).toFixed(1)}) ` +
      `scale(${escala.toFixed(3)})`,
  );
  pai.appendChild(g);
}

// --- geometria das casas -------------------------------------------------------

/** Onde começa e termina a célula `i` de um eixo com `n` células. As das
    pontas são os cantos, mais largos que as do meio. */
function faixa(i, n) {
  if (i === 0) return [0, FUNDO_CASA];
  if (i === n - 1) return [FUNDO_CASA + n - 2, 2 * FUNDO_CASA + n - 2];
  return [FUNDO_CASA + i - 1, FUNDO_CASA + i];
}

const ladoDoTabuleiro = (n) => 2 * FUNDO_CASA + n - 2;

function geometria(casa, largura, altura) {
  const [u0, u1] = faixa(casa.x, largura);
  const [v0, v1] = faixa(casa.y, altura);
  const naColuna = casa.x === 0 || casa.x === largura - 1;
  const naLinha = casa.y === 0 || casa.y === altura - 1;
  return {
    u0, u1, v0, v1,
    uc: (u0 + u1) / 2,
    vc: (v0 + v1) / 2,
    canto: naColuna && naLinha,
    // A profundidade da casa corre em u nas colunas e em v nas linhas. O
    // sentido positivo é sempre "para baixo na tela" (u + v crescendo).
    prof: naColuna ? [1, 0] : [0, 1],
    // Das casas do fundo (x = 0 ou y = 0) a cidade passa na frente.
    doFundo: casa.x === 0 || casa.y === 0,
  };
}

/* Enfeite em cima (para o fundo da tela) e nome embaixo, como na arte:
   nas casas da frente o prédio fica do lado da cidade, nas de trás fica do
   lado de fora — nos dois casos, "para cima" na tela. */
const RECUO_ENFEITE = 0.26;
const AVANCO_ROTULO = 0.2;

function pontoDoEnfeite(geo) {
  return [geo.uc - geo.prof[0] * RECUO_ENFEITE * FUNDO_CASA, geo.vc - geo.prof[1] * RECUO_ENFEITE * FUNDO_CASA];
}

function pontoDoRotulo(geo) {
  return [geo.uc + geo.prof[0] * AVANCO_ROTULO * FUNDO_CASA, geo.vc + geo.prof[1] * AVANCO_ROTULO * FUNDO_CASA];
}

// --- enfeites --------------------------------------------------------------------

/* O prédio diz a faixa de preço de longe: barraco com caixa d'água nas
   baratas, casinha de telhado nas médias, sobrado nas caras, prédio nas
   muito caras e torre nas extremamente caras. */
const PREDIOS = {
  barata: { larg: 0.46, prof: 0.4, alt: 0.34, paredes: ["#c0603a", "#d9893d", "#9c6a4f"], caixaDagua: true },
  media: { larg: 0.46, prof: 0.42, alt: 0.3, paredes: ["#f0e2c4", "#f3c6c6", "#cfe8b8"], telhado: "#c2452d" },
  cara: { larg: 0.5, prof: 0.46, alt: 0.46, paredes: ["#9fd3e6", "#b8c7f0", "#c5e8d4"], telhado: "#3c4668", janelas: [2, 1] },
  muito_cara: { larg: 0.46, prof: 0.46, alt: 0.78, paredes: ["#b9a4e0", "#d6c8f0", "#a8b8e8"], janelas: [2, 3] },
  extremamente_cara: { larg: 0.42, prof: 0.42, alt: 1.08, paredes: ["#7fb4ff", "#ff9be6", "#b5f0ff"], janelas: [2, 4], antena: true },
};

function predio(pai, casa, u, v, z) {
  const tipo = PREDIOS[casa.grupo] || PREDIOS.media;
  const parede = tipo.paredes[casa.i % tipo.paredes.length];
  const u0 = u - tipo.larg / 2;
  const u1 = u + tipo.larg / 2;
  const v0 = v - tipo.prof / 2;
  const v1 = v + tipo.prof / 2;
  const topo = z + tipo.alt;

  caixa(pai, u0, v0, u1, v1, z, topo, parede, tipo.telhado ? parede : clarear(parede, 0.25));

  if (tipo.janelas) {
    janelas(pai, u0, v0, u1, v1, z, topo, tipo.janelas[0], tipo.janelas[1], "#ffe79a");
  } else {
    // Casa pequena: uma porta na frente e uma janela do lado.
    const meio = (u0 + u1) / 2;
    face(pai, [[meio - 0.06, v1, z + 0.2], [meio + 0.06, v1, z + 0.2], [meio + 0.06, v1, z], [meio - 0.06, v1, z]],
      "#4a2a1a");
    const vm = (v0 + v1) / 2;
    face(pai, [[u1, vm - 0.07, z + 0.22], [u1, vm + 0.07, z + 0.22], [u1, vm + 0.07, z + 0.1], [u1, vm - 0.07, z + 0.1]],
      "#2f3f6a");
  }

  if (tipo.telhado) telhado(pai, u0 - 0.03, v0 - 0.03, u1 + 0.03, v1 + 0.03, topo, 0.2, tipo.telhado);

  if (tipo.caixaDagua) {
    const t = 0.07;
    caixa(pai, u - t, v - t, u + t, v + t, topo, topo + 0.13, "#2b56c9", "#4f7df0");
  }

  if (tipo.antena) {
    const [x, y] = tela(u, v, topo);
    no("line", { x1: x, y1: y, x2: x, y2: (y - 0.3 * C).toFixed(1), stroke: "#2a2440", "stroke-width": 1.6 }, pai);
    no("circle", { cx: x, cy: (y - 0.3 * C).toFixed(1), r: 1.8, fill: "#ff3b3b" }, pai);
  }

  // A bandeira do dono no canto de trás do telhado: longe da antena e da
  // caixa d'água, que ficam no meio, e é o ponto mais alto na tela.
  bandeira(pai, u0 + 0.05, v0 + 0.05, topo);

  // Uma arvorezinha do lado em metade das casas, como na arte.
  if (casa.i % 2 === 0) iconeEmPe(pai, "arvore", u + 0.3, v - 0.26, z, 0.42 * C);
}

/* --- de quem é o terreno ----------------------------------------------------

   Duas marcas na cor do peão do dono: um anel em volta do tampo, que se lê
   de longe mesmo com o prédio na frente, e uma bandeirinha no telhado. A
   cor não está no desenho: entra como --cor-dono no grupo da casa (ver
   `marcarDonos`), para a casa trocar de dono sem redesenhar o tabuleiro. */

function anelDoDono(pai, geo) {
  const m = 0.07;
  const z = ALTURA_CASA + 0.002;
  const lista = [[geo.u0 + m, geo.v0 + m, z], [geo.u1 - m, geo.v0 + m, z], [geo.u1 - m, geo.v1 - m, z], [geo.u0 + m, geo.v1 - m, z]];
  const g = no("g", { class: "casa__dono" }, pai);
  // Contorno escuro por baixo: o anel aparece até em casa da mesma cor.
  face(g, lista, "none", { class: "casa__dono-contorno" });
  face(g, lista, "none", { class: "casa__dono-anel" });
  return g;
}

/** Mastro em pé a partir de (u, v, z) e o pano virado para a direita. */
function bandeira(pai, u, v, z) {
  const [x, y] = tela(u, v, z);
  const topo = y - 0.52 * C;
  const g = no("g", { class: "casa__bandeira" }, pai);
  no("line", { x1: x.toFixed(1), y1: y.toFixed(1), x2: x.toFixed(1), y2: topo.toFixed(1), class: "casa__bandeira-mastro" }, g);
  no("polygon", {
    points: `${x.toFixed(1)},${topo.toFixed(1)} ${(x + 16).toFixed(1)},${(topo + 5.5).toFixed(1)} ${x.toFixed(1)},${(topo + 11).toFixed(1)}`,
    class: "casa__bandeira-pano",
  }, g);
}

/** Seta pintada no chão da INICIAL, apontando para a casa seguinte. */
function setaNoChao(pai, geo, direcao, z) {
  const [du, dv] = direcao;
  // Perpendicular à direção, no plano do tabuleiro.
  const [pu, pv] = [-dv, du];
  // No lugar do enfeite das outras casas, deixando o nome embaixo.
  const [uc, vc] = pontoDoEnfeite(geo);
  const em = (a, p) => [uc + du * a + pu * p, vc + dv * a + pv * p, z + 0.004];
  face(pai, [em(-0.32, -0.07), em(0.06, -0.07), em(0.06, -0.17), em(0.32, 0), em(0.06, 0.17), em(0.06, 0.07), em(-0.32, 0.07)],
    "#ec2733", { stroke: "#5e0d14", "stroke-width": 1.4, "stroke-linejoin": "round" });
}

function cenario(pai, casa, geo, z) {
  const { u0, v0, u1, v1, uc, vc } = geo;
  switch (casa.cenario) {
    case "praca": {
      // Quiosque no fundo. A Praça é o início, então os lados ficam livres
      // para a seta, o rótulo e os peões que começam aqui.
      const k = 0.17;
      const ku = u0 + 0.24;
      const kv = v0 + 0.24;
      caixa(pai, ku - k, kv - k, ku + k, kv + k, z, z + 0.28, "#f2c230");
      face(pai, [[ku - 0.07, kv + k, z + 0.18], [ku + 0.07, kv + k, z + 0.18], [ku + 0.07, kv + k, z], [ku - 0.07, kv + k, z]],
        "#2f6bd6");
      telhado(pai, ku - k - 0.05, kv - k - 0.05, ku + k + 0.05, kv + k + 0.05, z + 0.28, 0.22, "#d23a3a");
      break;
    }
    case "represa": {
      // Água no meio da casa, com margem de areia.
      const m = 0.2;
      face(pai, [[u0 + m, v0 + m, z + 0.004], [u1 - m, v0 + m, z + 0.004], [u1 - m, v1 - m, z + 0.004], [u0 + m, v1 - m, z + 0.004]],
        "#2e8bd6", { stroke: "#1b5d9a", "stroke-width": 1.2 });
      const n = 0.34;
      face(pai, [[u0 + n, v0 + n, z + 0.006], [u1 - n, v0 + n, z + 0.006], [u1 - n, v1 - n, z + 0.006], [u0 + n, v1 - n, z + 0.006]],
        "#56b3f0");
      for (const [a, b] of [[0.35, 0.62], [0.62, 0.42], [0.55, 0.86], [0.85, 0.66]]) {
        const [x1, y1] = tela(u0 + a, v0 + b, z);
        no("line", { x1: x1.toFixed(1), y1: y1.toFixed(1), x2: (x1 + 9).toFixed(1), y2: y1.toFixed(1),
          stroke: "#d6f3ff", "stroke-width": 1.4, "stroke-linecap": "round" }, pai);
      }
      iconeEmPe(pai, "arvore", u0 + 0.16, v0 + 0.2, z, 0.62 * C);
      iconeEmPe(pai, "pinheiro", u0 + 0.16, v1 - 0.18, z, 0.5 * C);
      break;
    }
    case "prisao": {
      const pu0 = uc - 0.4;
      const pu1 = uc + 0.3;
      const pv0 = vc - 0.36;
      const pv1 = vc + 0.3;
      caixa(pai, pu0, pv0, pu1, pv1, z, z + 0.5, "#a9a9b3", "#c4c4cc");
      // Janelas com grade.
      janelas(pai, pu0, pv0, pu1, pv1, z, z + 0.5, 2, 1, "#2a2a36");
      for (let k = 0; k < 5; k += 1) {
        const ua = pu0 + ((pu1 - pu0) / 5) * (k + 0.5);
        face(pai, [[ua, pv1, z + 0.32], [ua + 0.012, pv1, z + 0.32], [ua + 0.012, pv1, z + 0.14], [ua, pv1, z + 0.14]], "#d8d8e0");
      }
      face(pai, [[uc - 0.12, pv1, z + 0.26], [uc - 0.02, pv1, z + 0.26], [uc - 0.02, pv1, z], [uc - 0.12, pv1, z]], "#3b3b48");
      iconeEmPe(pai, "arvore", u1 - 0.22, v0 + 0.2, z, 0.56 * C);
      break;
    }
    case "mansao": {
      const mu0 = uc - 0.36;
      const mu1 = uc + 0.36;
      const mv0 = vc - 0.3;
      const mv1 = vc + 0.3;
      caixa(pai, mu0, mv0, mu1, mv1, z, z + 0.5, "#ff86d6");
      janelas(pai, mu0, mv0, mu1, mv1, z, z + 0.5, 2, 2, "#fff4c2");
      telhado(pai, mu0 - 0.05, mv0 - 0.05, mu1 + 0.05, mv1 + 0.05, z + 0.5, 0.3, "#b3127e");
      iconeEmPe(pai, "pinheiro", u0 + 0.2, v1 - 0.22, z, 0.62 * C);
      iconeEmPe(pai, "arvore", u1 - 0.2, v0 + 0.22, z, 0.66 * C);
      break;
    }
    default:
      iconeEmPe(pai, "arvore", uc, vc, z, 0.6 * C);
  }
}

const ICONE_DO_TIPO = {
  ganho: "saco",
  coletor: "documento",
  coringa: "interrogacao",
  portal: "portal",
  roubo: "ladrao",
  prejuizo: "prejuizo",
  reconstrucao: "capacete",
};

function enfeitar(pai, casa, geo, ctx) {
  const z = ALTURA_CASA;
  if (casa.cenario) {
    if (!casa.inicio) cenario(pai, casa, geo, z);
    if (casa.inicio) setaNoChao(pai, geo, ctx.direcaoDaSaida, z);
    return;
  }

  const [u, v] = pontoDoEnfeite(geo);
  if (casa.tipo === "propriedade") {
    // Nasce escondido: só aparece quando alguém compra (`marcarDonos`).
    const camada = no("g", { class: "casa__predio", display: "none" }, pai);
    return predio(camada, casa, u, v, z);
  }
  // Casa neutra não tem nome escrito: a árvore fica no meio dela.
  if (casa.tipo === "neutra") return iconeEmPe(pai, "arvore", geo.uc, geo.vc, z, 0.62 * C);
  if (casa.tipo === "inicial") return setaNoChao(pai, geo, ctx.direcaoDaSaida, z);

  const icone = ICONE_DO_TIPO[casa.tipo];
  if (icone) iconeEmPe(pai, icone, u, v, z, 0.66 * C);
}

// --- nomes -----------------------------------------------------------------------

/** Duas linhas quando o nome é comprido e tem mais de uma palavra, cortando
    onde as duas ficam mais parecidas: "Casa do / Imposto", não
    "Casa / do Imposto". */
function quebrarNome(nome) {
  const palavras = nome.split(" ");
  if (nome.length <= 9 || palavras.length < 2) return [nome];
  let melhor = null;
  for (let k = 1; k < palavras.length; k += 1) {
    const linhas = [palavras.slice(0, k).join(" "), palavras.slice(k).join(" ")];
    const maior = Math.max(...linhas.map((l) => l.length));
    if (!melhor || maior < melhor.maior) melhor = { maior, linhas };
  }
  return melhor.linhas;
}

function rotular(pai, casa, geo, cor) {
  if (casa.inicio || casa.tipo === "inicial") return;
  // Cantos com cenário e casas neutras não recebem rótulos comuns.
  if (casa.cenario || casa.tipo === "neutra") return;

  const linhas = quebrarNome(casa.nome);
  const [u, v] = pontoDoRotulo(geo);
  const [x, y] = tela(u, v, ALTURA_CASA);

  const classes = ["tabuleiro__nome"];
  if (eClara(cor)) classes.push("tabuleiro__nome--escuro");

  const texto = no("text", { x: x.toFixed(1), y: y.toFixed(1), class: classes.join(" "), "data-i": casa.i }, pai);
  // Centraliza o bloco na altura: sobe meia linha por linha extra.
  const primeira = -((linhas.length - 1) / 2) * 1.02 + 0.34;
  linhas.forEach((linha, k) => {
    const t = no("tspan", { x: x.toFixed(1), dy: `${(k === 0 ? primeira : 1.02).toFixed(2)}em` }, texto);
    t.textContent = linha;
  });
}

// --- montagem ------------------------------------------------------------------------

function desenharBase(pai, lu, lv) {
  caixa(pai, 0, 0, lu, lv, -ESPESSURA_BASE, 0, COR_BASE);
  // Filete claro na borda de cima da base, como o da arte.
  no("polyline", {
    points: pontos([[0, lv, 0], [lu, lv, 0], [lu, 0, 0]]),
    fill: "none",
    stroke: "#5b4fc4",
    "stroke-width": 2,
  }, pai);
  // Asfalto no miolo: aparece na folga entre as casas e a cidade.
  const f = FUNDO_CASA;
  face(pai, [[f, f, 0], [lu - f, f, 0], [lu - f, lv - f, 0], [f, lv - f, 0]], COR_ASFALTO);
}

/** Desenha a pintura da cidade e devolve um grupo por cima dela em que uma
    unidade é um pixel da pintura — é nele que a cidade ganha vida. */
function desenharCidade(pai, lu, lv) {
  const lado = Math.min(lu, lv) - 2 * FUNDO_CASA - 2 * RECUO_CIDADE;
  const escala = (lado * A) / CIDADE.meiaLargura;
  // O meio-fio da pintura assenta na base: o chão da cidade sobe a altura dele.
  const zChao = (CIDADE.meioFio * escala) / C;
  const [cx, cy] = tela(lu / 2, lv / 2, zChao);
  const x = cx - CIDADE.centroX * escala;
  const y = cy - CIDADE.centroY * escala;
  no("image", {
    href: CIDADE.arquivo,
    x: x.toFixed(1),
    y: y.toFixed(1),
    width: (CIDADE.largura * escala).toFixed(1),
    height: (CIDADE.altura * escala).toFixed(1),
    preserveAspectRatio: "none",
    class: "tabuleiro__cidade",
  }, pai);
  return no("g", { transform: `translate(${x.toFixed(2)} ${y.toFixed(2)}) scale(${escala.toFixed(5)})` }, pai);
}

function desenharCasa(pai, item, dados, ctx) {
  const { casa, geo } = item;
  const cor = corDaCasa(casa, dados.grupos);
  const terreno = casa.tipo === "propriedade" && !casa.cenario;
  const g = no("g", { class: terreno ? "casa casa--terreno" : "casa", "data-i": casa.i }, pai);

  const f = FRESTA / 2;
  const tampo = caixa(g, geo.u0 + f, geo.v0 + f, geo.u1 - f, geo.v1 - f, 0, ALTURA_CASA, cor);
  // Brilho de cima para baixo no tampo: é o que dá o ar "envernizado" da arte.
  no("polygon", { points: tampo.getAttribute("points"), fill: "url(#brilho-casa)" }, g);

  // O anel fica no tampo, por baixo do prédio. Nasce escondido, como ele.
  if (terreno) anelDoDono(g, geo).setAttribute("display", "none");

  enfeitar(g, casa, geo, ctx);
}

/**
 * Desenha o tabuleiro dentro do `svg` e devolve como conversar com ele.
 * `corDoDono(jogadorId)` diz a cor do peão de quem comprou cada terreno.
 * @returns {{proporcao: number, ponto: Function, destacar: Function, atualizarPropriedades: Function}}
 */
export function montarTabuleiro(svg, dados, propriedades = {}, { corDoDono = () => null } = {}) {
  const largura = dados.largura;
  const altura = dados.altura;
  const lu = ladoDoTabuleiro(largura);
  const lv = ladoDoTabuleiro(altura);
  const itens = dados.casas.map((casa) => ({ casa, geo: geometria(casa, largura, altura) }));
  const total = itens.length;

  // Enquadramento: da ponta esquerda à direita, do telhado da Mansão (o
  // ponto mais alto do canto de cima) até o pé da base.
  const margem = 14;
  const caixaVista = {
    x: -lv * A - margem,
    y: -(ALTURA_CASA + 0.75) * C,
    w: (lu + lv) * A + 2 * margem,
    h: 0,
  };
  caixaVista.h = (lu + lv) * B + ESPESSURA_BASE * C + margem - caixaVista.y;
  svg.setAttribute("viewBox", `${caixaVista.x} ${caixaVista.y} ${caixaVista.w} ${caixaVista.h}`);
  svg.replaceChildren();

  const defs = no("defs", {}, svg);
  const brilho = no("linearGradient", { id: "brilho-casa", x1: 0, y1: 0, x2: 0, y2: 1 }, defs);
  no("stop", { offset: "0", "stop-color": "#ffffff", "stop-opacity": 0.3 }, brilho);
  no("stop", { offset: "0.55", "stop-color": "#ffffff", "stop-opacity": 0 }, brilho);
  no("stop", { offset: "1", "stop-color": "#000000", "stop-opacity": 0.12 }, brilho);

  // A seta da casa inicial aponta para a casa anterior no índice, no sentido horário.
  const indiceInicial = dados.casas.findIndex((casa) => casa.inicio || casa.tipo === "inicial");
  const inicio = indiceInicial >= 0 ? indiceInicial : 0;
  const saida = itens[inicio].geo;
  const seguinte = itens[(inicio + total - 1) % total].geo;
  const du = seguinte.uc - saida.uc;
  const dv = seguinte.vc - saida.vc;
  const comprimento = Math.hypot(du, dv) || 1;
  const ctx = {
    direcaoDaSaida: [du / comprimento, dv / comprimento],
  };

  const porProfundidade = (a, b) => a.geo.uc + a.geo.vc - (b.geo.uc + b.geo.vc);

  desenharBase(no("g", { class: "tabuleiro__base" }, svg), lu, lv);
  const fundo = no("g", {}, svg);
  itens.filter((i) => i.geo.doFundo).sort(porProfundidade).forEach((i) => desenharCasa(fundo, i, dados, ctx));
  // A cidade e o que anda nela ficam entre as casas do fundo e as da frente:
  // um carro chegando na esquina passa atrás das casas da borda de baixo.
  animarCidade(desenharCidade(svg, lu, lv));
  const frente = no("g", {}, svg);
  itens.filter((i) => !i.geo.doFundo).sort(porProfundidade).forEach((i) => desenharCasa(frente, i, dados, ctx));
  const rotulos = no("g", { class: "tabuleiro__rotulos" }, svg);
  itens.forEach((i) => rotular(rotulos, i.casa, i.geo, corDaCasa(i.casa, dados.grupos)));

  /** Terreno com dono: prédio, anel e bandeira aparecem, na cor dele. */
  function marcarDonos(lista = {}) {
    for (const g of svg.querySelectorAll(".casa--terreno")) {
      const dono = lista[g.dataset.i]?.dono;
      for (const marca of g.querySelectorAll(".casa__predio, .casa__dono")) {
        if (dono == null) marca.setAttribute("display", "none");
        else marca.removeAttribute("display");
      }
      const cor = dono == null ? null : corDoDono(dono);
      if (cor) g.style.setProperty("--cor-dono", cor);
      else g.style.removeProperty("--cor-dono");
    }
  }
  marcarDonos(propriedades);

  const emPorcento = ([x, y]) => ({
    x: ((x - caixaVista.x) / caixaVista.w) * 100,
    y: ((y - caixaVista.y) / caixaVista.h) * 100,
  });

  /* Até quatro peões na mesma casa, cada um num lugar fixo. Nas casas da
     borda os lugares correm ao longo da borda e um pouco para a frente do
     prédio; nos cantos, que são maiores, espalham mais. */
  const LUGARES = [[-0.22, -0.02], [0.22, -0.02], [-0.22, 0.26], [0.22, 0.26]];
  const LUGARES_CANTO = [[-0.34, -0.34], [0.3, -0.36], [-0.36, 0.3], [0.06, 0.06]];

  return {
    proporcao: caixaVista.w / caixaVista.h,

    /** Só mostra os prédios dos terrenos comprados, com a cor do dono. */
    atualizarPropriedades: marcarDonos,

    /** Onde ficam os pés do peão, em % do quadro. */
    ponto(indice, assento = 0) {
      const { geo } = itens[((indice % total) + total) % total];
      let u;
      let v;
      if (geo.canto) {
        const [a, b] = LUGARES_CANTO[assento % 4];
        u = geo.uc + a;
        v = geo.vc + b;
      } else {
        const [ao, prof] = LUGARES[assento % 4];
        // Ao longo da borda é o eixo que não é o da profundidade.
        u = geo.uc + (geo.prof[0] ? 0 : ao) + geo.prof[0] * prof;
        v = geo.vc + (geo.prof[1] ? 0 : ao) + geo.prof[1] * prof;
      }
      return emPorcento(tela(u, v, ALTURA_CASA));
    },

    /** Posição do marcador dentro da casa inicial. */
    pontoInicio() {
      const geo = itens[inicio].geo;
      return emPorcento(tela(geo.uc + 0.43, geo.vc + 0.48, ALTURA_CASA + 0.35));
    },

    /** Faz a casa pular algumas vezes, para marcar onde o peão parou. */
    destacar(indice) {
      const alvos = svg.querySelectorAll(`[data-i="${((indice % total) + total) % total}"]`);
      for (const alvo of alvos) {
        alvo.classList.remove("casa--destacada");
        void alvo.getBoundingClientRect(); // reinicia a animação
        alvo.classList.add("casa--destacada");
        setTimeout(() => alvo.classList.remove("casa--destacada"), 1600);
      }
    },
  };
}

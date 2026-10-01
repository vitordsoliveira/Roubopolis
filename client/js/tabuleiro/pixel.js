/* Ícones em pixel art, desenhados a partir de mapas de caracteres.

   Cada ícone é uma lista de linhas; cada caractere é um pixel, e a PALETA
   diz a cor dele ("." é transparente). Assim um ícone novo é só um desenho
   em texto — sem arquivo de imagem, sem exportar nada — e fica nítido em
   qualquer tamanho, porque vira SVG.

   Os mesmos mapas servem ao tabuleiro (ícone em pé sobre a casa) e ao
   HUD (os botões de REGRAS, RANKING, CONFIG. e SAIR). */

const SVG = "http://www.w3.org/2000/svg";

const PALETA = {
  K: "#1a1020", // contorno
  W: "#ffffff",
  w: "#d9d4e4",
  a: "#8d8a99",
  Y: "#ffd23d",
  y: "#d99a14",
  O: "#ff8a1f",
  R: "#ec2733",
  r: "#9e1320",
  G: "#43c94a",
  g: "#22822c",
  L: "#a7f07a",
  U: "#2f7bff",
  u: "#1740b0",
  c: "#8fe3ff",
  b: "#c07a35",
  B: "#7d4a1c",
  N: "#5a3218",
  S: "#f4c7a1",
};

export const ICONES = {
  // Casa do Ganho
  saco: [
    ".....KKKK.....",
    "....KyYYyK....",
    ".....KbbK.....",
    "....KKKKKK....",
    "...KbbbbbbK...",
    "..KbbbbbbbbK..",
    ".KbbbbbYbbbbK.",
    ".KbbbbYYYYbbK.",
    "KbbbbYbYbbbbbK",
    "KbbbbbYYYbbbbK",
    "KbbbbbbYbYbbbK",
    "KbbbbYYYYbbbbK",
    "KbbbbbbYbbbbbK",
    ".KbbbbbbbbbbK.",
    "..KBBBBBBBBK..",
    "...KKKKKKKK...",
  ],
  // Casa do Imposto
  documento: [
    "KKKKKKKK...",
    "KWWWWWWKK..",
    "KWWWWWWKwK.",
    "KWWWWWWKKKK",
    "KWWWWRWWWWK",
    "KWWRRRRWWWK",
    "KWWRWRWWWWK",
    "KWWWRRRWWWK",
    "KWWWWRWRWWK",
    "KWWRRRRWWWK",
    "KWWWWRWWWWK",
    "KWaaaaaaaWK",
    "KWWWWWWWWWK",
    "KWaaaaaWWWK",
    "KKKKKKKKKKK",
  ],
  // Casa Coringa
  interrogacao: [
    "..KKKKKK..",
    ".KYYYYYYK.",
    "KYYKKKKYYK",
    "KYYK..KYYK",
    "KKKK..KYYK",
    ".....KYYK.",
    "....KYYK..",
    "...KYYK...",
    "...KYYK...",
    "...KKKK...",
    "..........",
    "...KKKK...",
    "...KYYK...",
    "...KKKK...",
  ],
  // Casa Portal
  portal: [
    "....KKKKKK....",
    "..KKuuuuuuKK..",
    ".KuuUUUUUUuuK.",
    ".KuUUccccUUuK.",
    "KuUUccUUccUUuK",
    "KuUcUUuuUUcUuK",
    "KuUcUuWWuUcUuK",
    "KuUcUuWWuUcUuK",
    "KuUcUUuuUUcUuK",
    "KuUUccUUccUUuK",
    ".KuUUccccUUuK.",
    ".KuuUUUUUUuuK.",
    "..KKuuuuuuKK..",
    "....KKKKKK....",
  ],
  // Casa do Roubo
  ladrao: [
    "..KKKKKKKK..",
    ".KNNNNNNNNK.",
    "KNNNNNNNNNNK",
    "KNSSSSSSSSNK",
    "KKKKKKKKKKKK",
    "KKWWKKKKWWKK",
    "KSKKKKKKKKSK",
    ".KSSSSSSSSK.",
    ".KSSKKKKSSK.",
    ".KSSSSSSSSK.",
    "..KSSSSSSK..",
    "...KKKKKK...",
  ],
  // Casa do Prejuízo
  prejuizo: [
    ".....KKKK.....",
    ".....KRRK.....",
    ".....KRRK.....",
    ".....KRRK.....",
    "..KKKKRRKKKK..",
    "..KRRRRRRRRK..",
    "...KRRRRRRK...",
    "....KRRRRK....",
    ".....KRRK.....",
    "......KK......",
    "KKKKKKKKKKKKKK",
    "KGGGGGGGGGGGGK",
    "KGgGGGLLGGGgGK",
    "KGGGGLGGLGGGGK",
    "KGgGGGLLGGGgGK",
    "KGGGGGGGGGGGGK",
    "KKKKKKKKKKKKKK",
  ],
  // Casa da Reconstrução
  capacete: [
    ".....KKKK.....",
    "...KKYYYYKK...",
    "..KYYYyyYYYK..",
    ".KYYYYyyYYYYK.",
    ".KYWYYyyYYYYK.",
    ".KYWYYyyYYYYK.",
    "KKKKKKKKKKKKKK",
    "KyyyyyyyyyyyyK",
    "KKKKKKKKKKKKKK",
  ],
  // INICIAL: aponta para onde o peão anda
  seta: [
    "......KK....",
    "......KRK...",
    "KKKKKKKRRK..",
    "KRRRRRRRRRK.",
    "KRRRRRRRRRRK",
    "KRRRRRRRRRK.",
    "KKKKKKKRRK..",
    "......KRK...",
    "......KK....",
  ],
  // Casa neutra e enfeite dos cantos
  arvore: [
    "...gggg...",
    ".ggGGGGgg.",
    ".gGGLLGGg.",
    "gGGLLGGGGg",
    "gGLLGGGGGg",
    "gGGGGGGGgg",
    "gGGGGGGgGg",
    ".gGGGGGGg.",
    ".ggGGGGgg.",
    "...gggg...",
    "....NN....",
    "....NN....",
    "...NNNN...",
  ],
  pinheiro: [
    "...gg...",
    "...GG...",
    "..gGGg..",
    "..GLGG..",
    ".gGGGGg.",
    ".GLGGGG.",
    "gGGGGGGg",
    "..gGGg..",
    ".gGGGGg.",
    "gGLGGGGg",
    "GGGGGGGG",
    "gggggggg",
    "...NN...",
    "...NN...",
  ],

  // --- HUD -----------------------------------------------------------
  regras: [
    "KKKKKKKK...",
    "KWWWWWWKK..",
    "KWWWWWWKwK.",
    "KWRRRRWKKKK",
    "KWWWWWWWWWK",
    "KWOOOOOOWWK",
    "KWWWWWWWWWK",
    "KWRRRRRRRWK",
    "KWWWWWWWWWK",
    "KWOOOOOWWWK",
    "KWWWWWWWWWK",
    "KWRRRRRRWWK",
    "KWWWWWWWWWK",
    "KKKKKKKKKKK",
  ],
  trofeu: [
    "..KKKKKKKKKK..",
    "KKKYYYYYYYYKKK",
    "KYKYYYYYYWYKYK",
    "KYKYYYYYYWYKYK",
    ".KKYYYYYYYYKK.",
    "..KyYYYYYYYK..",
    "...KyYYYYYK...",
    "....KKyyKK....",
    ".....KyyK.....",
    ".....KyyK.....",
    "...KKKKKKKK...",
    "...KYYYYYYK...",
    "...KKKKKKKK...",
  ],
  engrenagem: [
    ".....KKKK.....",
    ".....KYYK.....",
    "..KK.KYYK.KK..",
    "..KYKKYYKKYK..",
    "...KYYYYYYK...",
    "KKKKYYKKYYKKKK",
    "KYYYYK..KYYYYK",
    "KYYYYK..KYYYYK",
    "KKKKYYKKYYKKKK",
    "...KYYYYYYK...",
    "..KYKKYYKKYK..",
    "..KK.KYYK.KK..",
    ".....KYYK.....",
    ".....KKKK.....",
  ],
  sair: [
    "KKKKKK........",
    "KYYYYK........",
    "KYKKKK...KK...",
    "KYK......KYK..",
    "KYK.KKKKKKYYK.",
    "KYK.KYYYYYYYYK",
    "KYK.KYYYYYYYYK",
    "KYK.KKKKKKYYK.",
    "KYK......KYK..",
    "KYKKKK...KK...",
    "KYYYYK........",
    "KKKKKK........",
  ],
  balao: [
    "..KKKKKKKKK..",
    ".KYYYYYYYYYK.",
    "KYYYYYYYYYYYK",
    "KYYKYYKYYKYYK",
    "KYYYYYYYYYYYK",
    ".KYYYYYYYYYK.",
    "..KKKYKKKKK..",
    "....KYK......",
    "....KK.......",
  ],
  // As setas dos lados do JOGAR. A da esquerda é esta espelhada no CSS.
  chevron: [
    "KKK......",
    "KWWK.....",
    "KWWWK....",
    ".KWWWK...",
    "..KWWWK..",
    "...KWWWK.",
    "....KWWWK",
    "....KWWWK",
    "...KWWWK.",
    "..KWWWK..",
    ".KWWWK...",
    "KWWWK....",
    "KWWK.....",
    "KKK......",
  ],
  coroa: [
    "Y.....YY.....Y",
    "YY...Y..Y...YY",
    "Y.Y.Y....Y.Y.Y",
    "Y..Y......Y..Y",
    "Y............Y",
    "Y............Y",
    "YYYYYYYYYYYYYY",
  ],
};

/** Tamanho do desenho, em pixels do mapa. */
export function medidas(nome) {
  const linhas = ICONES[nome];
  return { largura: linhas[0].length, altura: linhas.length };
}

/* Um retângulo por trecho contínuo da mesma cor, e não um por pixel: o
   ícone maior tem ~200 pixels pintados, e juntar a linha reduz os
   elementos do SVG a menos de um terço. */
function pintar(pai, linhas, paleta) {
  linhas.forEach((linha, y) => {
    let x = 0;
    while (x < linha.length) {
      const cor = linha[x];
      let fim = x + 1;
      while (fim < linha.length && linha[fim] === cor) fim += 1;
      if (cor !== ".") {
        if (!paleta[cor]) throw new Error(`Cor "${cor}" sem valor na paleta do desenho.`);
        const r = document.createElementNS(SVG, "rect");
        r.setAttribute("x", String(x));
        r.setAttribute("y", String(y));
        r.setAttribute("width", String(fim - x));
        r.setAttribute("height", "1");
        r.setAttribute("fill", paleta[cor]);
        pai.appendChild(r);
      }
      x = fim;
    }
  });
}

/** Qualquer desenho em texto, com a paleta que quem chama quiser — é assim
    que o mesmo menino sai com camisa de time diferente. */
export function grupoDoMapa(linhas, paleta = PALETA) {
  const g = document.createElementNS(SVG, "g");
  g.setAttribute("shape-rendering", "crispEdges");
  pintar(g, linhas, paleta);
  return g;
}

/** Grupo SVG com o ícone, na escala de 1 unidade por pixel do mapa. Quem
    chama posiciona e escala com `transform`. */
export function grupoPixel(nome) {
  return grupoDoMapa(ICONES[nome]);
}

/** O ícone como um <svg> solto, para usar no meio do HTML. O tamanho vem
    do CSS; a proporção é a do desenho. */
export function iconePixel(nome, classe = "icone-pixel") {
  const { largura, altura } = medidas(nome);
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${largura} ${altura}`);
  svg.setAttribute("class", classe);
  svg.setAttribute("aria-hidden", "true");
  svg.appendChild(grupoPixel(nome));
  return svg;
}

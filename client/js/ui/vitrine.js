/* A amostra dos itens da loja: o dado e a casinha com as cores do item.

   A loja mostra antes de comprar, e a lista de amigos mostra o que cada um
   está usando — é o mesmo dado e o mesmo prédio que aparecem na partida
   (css/componentes/dados.css e js/tabuleiro/render.js). */

import { elemento } from "./comum.js";

const SVG = "http://www.w3.org/2000/svg";

/** Sem item equipado, a casa da vila: as cores das casas médias. */
const CASA_PADRAO = { paredes: ["#f0e2c4"], telhado: "#c2452d", janelas: "#ffe79a" };

function escurecer(cor, t) {
  const n = parseInt(cor.slice(1), 16);
  const canal = (deslocamento) => Math.round(((n >> deslocamento) & 255) * (1 - t));
  return `rgb(${canal(16)}, ${canal(8)}, ${canal(0)})`;
}

/** Uma face de cinco pontos, com as cores do dado. */
export function previaDoDado(visual) {
  const dado = elemento("div", "dado dado--vitrine");
  const face = elemento("div", "dado__face");
  face.dataset.valor = "5";
  for (let p = 0; p < 5; p += 1) face.appendChild(elemento("span", "dado__ponto"));
  dado.appendChild(face);
  if (visual) {
    dado.style.setProperty("--dado-face-a", visual.face?.[0]);
    dado.style.setProperty("--dado-face-b", visual.face?.[1]);
    dado.style.setProperty("--dado-borda", visual.borda);
    dado.style.setProperty("--dado-ponto", visual.ponto);
  }
  return dado;
}

function poligono(pai, pontos, cor) {
  const p = document.createElementNS(SVG, "polygon");
  p.setAttribute("points", pontos);
  p.setAttribute("fill", cor);
  pai.appendChild(p);
}

/** A casinha em isométrico, na mesma luz do tabuleiro. */
export function previaDaCasa(visual) {
  const cores = visual || CASA_PADRAO;
  const parede = cores.paredes?.[0] || CASA_PADRAO.paredes[0];
  const telhado = cores.telhado || CASA_PADRAO.telhado;
  const janela = cores.janelas || CASA_PADRAO.janelas;

  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 60 62");
  svg.setAttribute("class", "casa-vitrine");
  svg.setAttribute("aria-hidden", "true");
  poligono(svg, "6,28 30,42 30,60 6,46", escurecer(parede, 0.12));
  poligono(svg, "30,42 54,28 54,46 30,60", escurecer(parede, 0.32));
  poligono(svg, "11,37 18,41 18,48 11,44", janela);
  poligono(svg, "21,42.5 26,45.5 26,58 21,55", escurecer(telhado, 0.35));
  poligono(svg, "36,45 43,41 43,48 36,52", escurecer(janela, 0.25));
  poligono(svg, "45,39.8 50,37 50,44 45,46.8", escurecer(janela, 0.25));
  poligono(svg, "3,28 30,43.5 30,8", telhado);
  poligono(svg, "30,43.5 57,28 30,8", escurecer(telhado, 0.25));
  return svg;
}

export function previaDoItem(item) {
  const vitrine = elemento("div", `vitrine vitrine--${item.tipo}`);
  vitrine.appendChild(item.tipo === "dado" ? previaDoDado(item.visual) : previaDaCasa(item.visual));
  return vitrine;
}

/* Pequenas ferramentas que a partida e as janelas dela dividem. */

export function elemento(tag, classe, texto) {
  const el = document.createElement(tag);
  if (classe) el.className = classe;
  if (texto !== undefined) el.textContent = texto;
  return el;
}

export const reais = (v) => "R$ " + Number(v || 0).toLocaleString("pt-BR");

export const porcento = (fracao) => `${Math.round(Number(fracao || 0) * 100)}%`;

export const inicial = (n) => (n || "?").trim().charAt(0).toUpperCase();

export function formatarTempo(segundos) {
  const minutos = Math.floor(segundos / 60);
  const resto = segundos % 60;
  return `${String(minutos).padStart(2, "0")}:${String(resto).padStart(2, "0")}`;
}

/** O boneco do personagem, ou a ficha com a inicial quando não há sprite. */
export function retratoDe(jogador, classeImagem, classeFicha) {
  if (jogador?.personagem?.sprite) {
    const img = elemento("img", classeImagem);
    img.src = jogador.personagem.sprite;
    img.alt = jogador.nome || "";
    return img;
  }
  return elemento("span", classeFicha, inicial(jogador?.nome));
}

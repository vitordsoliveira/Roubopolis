/* A janela que conta o que acabou de acontecer: uma casa de evento ("Roubado!
   Fulano perdeu R$ 100.000") ou um evento temático ("O Presidente passou
   aqui"), com uma frase de sátira (data/eventos/) e o que mudou na mesa.

   Uma de cada vez, em fila: duas casas no mesmo lance (o portal e a casa
   onde o peão caiu) aparecem em sequência, sem uma cobrir a outra. Cada uma
   fecha sozinha quando a barra acaba, ou antes, no Continuar, no Esc ou
   quando quem tem a vez aperta JOGAR. A janela não trava a mesa: o relógio
   da vez continua correndo, e o clique fora dela passa para o jogo. Com as
   animações desligadas a janela aparece parada, mas aparece: é informação
   de jogo, não enfeite. */

import { guardado } from "../core/api.js";
import { iconePixel } from "../tabuleiro/pixel.js";

const cortina = document.querySelector("#modal-evento");
const janela = cortina.querySelector(".evento-janela");
const selo = document.querySelector("#evento-selo");
const chamada = document.querySelector("#evento-chamada");
const titulo = document.querySelector("#evento-titulo");
const frase = document.querySelector("#evento-frase");
const texto = document.querySelector("#evento-texto");
const nota = document.querySelector("#evento-nota");
const barra = document.querySelector("#evento-barra");
const botao = document.querySelector("#evento-continuar");

const fila = [];
let atual = null;

/**
 * @param {object} anuncio
 * @param {string} anuncio.titulo
 * @param {string} anuncio.texto  o que aconteceu, com os números
 * @param {string} [anuncio.chamada]  a linha pequena de cima ("Casa do Roubo")
 * @param {string} [anuncio.frase]  a sátira
 * @param {string} [anuncio.nota]  ex.: "Vale até o fim da rodada."
 * @param {string} [anuncio.icone]  nome de um desenho de tabuleiro/pixel.js
 * @param {"bom"|"ruim"|"neutro"|"evento"|"suspense"} [anuncio.tom]
 * @param {number} [anuncio.duracao]  ms na tela
 * @param {() => void} [anuncio.aoMostrar]  o som, na hora em que aparece
 * @returns {Promise<void>} resolve quando ESTA janela fecha
 */
export function anunciar(anuncio) {
  return new Promise((resolver) => {
    fila.push({ tom: "neutro", duracao: 4500, ...anuncio, resolver });
    if (!atual) proximo();
  });
}

export const anuncioAberto = () => atual !== null;

/** Fecha a janela da tela e esquece a fila: a partida acabou. */
export function limparAnuncios() {
  for (const item of fila.splice(0)) item.resolver();
  if (atual) fechar();
}

function proximo() {
  const item = fila.shift();
  if (!item) return;
  atual = item;

  // Fila longa (vários eventos de uma vez) anda mais rápido.
  const duracao = item.duracao * (fila.length > 1 ? 0.65 : 1);
  // O suspense da Coringa não se fecha na mão: é o tambor rufando.
  const fechavel = item.tom !== "suspense";

  janela.className = `compra moldura evento-janela evento-janela--${item.tom}`;
  selo.replaceChildren(...(item.icone ? [iconePixel(item.icone)] : []));
  chamada.textContent = item.chamada || "";
  chamada.hidden = !item.chamada;
  titulo.textContent = item.titulo;
  frase.textContent = item.frase ? `“${item.frase}”` : "";
  frase.hidden = !item.frase;
  // "R$" e o número na mesma linha.
  texto.textContent = item.texto.replace(/R\$ /g, "R$ ");
  nota.textContent = item.nota || "";
  nota.hidden = !item.nota;
  botao.hidden = !fechavel;
  cortina.hidden = false;

  // A barra esvazia no tempo que falta para a janela fechar sozinha. A
  // janela precisa já estar visível: transição que começa dentro de algo
  // escondido não anda, e a barra aparecia vazia.
  barra.style.transition = "none";
  barra.style.transform = "scaleX(1)";
  void barra.offsetWidth;
  if (guardado.animacoes()) {
    barra.style.transition = `transform ${duracao}ms linear`;
    barra.style.transform = "scaleX(0)";
  }

  item.aoMostrar?.();
  item.relogio = setTimeout(fechar, duracao);
}

function fechar() {
  if (!atual) return;
  const item = atual;
  clearTimeout(item.relogio);
  atual = null;
  cortina.hidden = true;
  item.resolver();
  proximo();
}

/** O Continuar, o Esc e o JOGAR: fecha a janela da tela agora. */
export function fecharAnuncio() {
  if (atual && atual.tom !== "suspense") fechar();
}

botao.addEventListener("click", fecharAnuncio);

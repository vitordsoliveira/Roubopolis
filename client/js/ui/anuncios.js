/* A janela que conta o que acabou de acontecer: uma casa de evento ("Roubado!
   Fulano perdeu R$ 100.000") ou um evento temático ("O Presidente passou
   aqui"), com uma frase de sátira (data/eventos/) e o que mudou na mesa.

   Fica 1 minuto, ou até a pessoa fechar: no ×, no Continuar, no Esc ou
   apertando JOGAR. A janela não trava a mesa: o relógio da vez continua
   correndo, e o clique fora dela passa para o jogo.

   Uma de cada vez, em fila: duas casas no mesmo lance (o portal e a casa
   onde o peão caiu) aparecem em sequência, sem uma cobrir a outra. Com
   outra esperando, a da tela cede depois de alguns segundos — senão a fila
   andava atrás da mesa, contando a jogada de duas vezes atrás. O suspense
   da Coringa passa na frente: a mesa está parada esperando o resultado.

   Com as animações desligadas a janela aparece parada, mas aparece: é
   informação de jogo, não enfeite. */

import { guardado } from "../core/api.js";
import { iconePixel } from "../tabuleiro/pixel.js";

/** Quanto a janela fica na tela se ninguém fechar: 1 minuto. */
const DURACAO_PADRAO = 60000;
/** Com outra janela esperando, a da tela cede depois deste tanto. */
const MINIMO_COM_FILA = 7000;

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
const botaoFechar = document.querySelector("#evento-fechar");

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
 * @param {number} [anuncio.duracao]  ms na tela; o padrão é 1 minuto
 * @param {() => void} [anuncio.aoMostrar]  o som, na hora em que aparece
 * @returns {Promise<void>} resolve quando ESTA janela fecha
 */
export function anunciar(anuncio) {
  return new Promise((resolver) => {
    const item = { tom: "neutro", duracao: DURACAO_PADRAO, ...anuncio, resolver };
    if (item.tom === "suspense") {
      // O tambor da Coringa não espera na fila: o resultado da jogada só
      // entra na mesa depois dele.
      fila.unshift(item);
      if (atual) fechar();
      else proximo();
      return;
    }
    fila.push(item);
    if (atual) apressar();
    else proximo();
  });
}

export const anuncioAberto = () => atual !== null;

/** Fecha a janela da tela e esquece a fila: a partida acabou. */
export function limparAnuncios() {
  for (const item of fila.splice(0)) item.resolver();
  if (atual) fechar();
}

/** A barra esvazia de `de` (1 = cheia) até zero em `ms`. A janela precisa
    já estar visível: transição que começa dentro de algo escondido não
    anda, e a barra aparecia vazia. */
function esvaziarBarra(de, ms) {
  barra.style.transition = "none";
  barra.style.transform = `scaleX(${de})`;
  void barra.offsetWidth;
  if (guardado.animacoes()) {
    barra.style.transition = `transform ${ms}ms linear`;
    barra.style.transform = "scaleX(0)";
  }
}

/** Agenda o fechamento da janela da tela para daqui a `ms`. */
function fecharEm(ms) {
  clearTimeout(atual.relogio);
  const agora = performance.now();
  atual.fim = agora + ms;
  atual.relogio = setTimeout(fechar, ms);
}

function proximo() {
  const item = fila.shift();
  if (!item) return;
  atual = item;
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
  botaoFechar.hidden = !fechavel;
  cortina.hidden = false;

  item.inicio = performance.now();
  // Já há outra esperando: esta fica o mínimo e cede a vez.
  const duracao = fila.length && fechavel ? Math.min(item.duracao, MINIMO_COM_FILA) : item.duracao;
  item.total = duracao;
  esvaziarBarra(1, duracao);
  fecharEm(duracao);
  item.aoMostrar?.();
}

/** Chegou outra janela: a da tela não fica mais o minuto inteiro — cede
    quando completar o mínimo, e a barra acompanha. */
function apressar() {
  if (!atual || atual.tom === "suspense") return;
  const agora = performance.now();
  const novoFim = atual.inicio + MINIMO_COM_FILA;
  if (novoFim >= atual.fim) return;
  const resta = Math.max(0, novoFim - agora);
  esvaziarBarra(Math.max(0, (atual.fim - agora) / atual.total), resta);
  fecharEm(resta);
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

/** O ×, o Continuar, o Esc e o JOGAR: fecha a janela da tela agora. */
export function fecharAnuncio() {
  if (atual && atual.tom !== "suspense") fechar();
}

botao.addEventListener("click", fecharAnuncio);
botaoFechar.addEventListener("click", fecharAnuncio);

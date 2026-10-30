/* A janela das decisões das casas de evento.

   Coringa, Reconstrução, Prejuízo e Bônus do banco são a mesma pergunta com
   conteúdos diferentes: um texto, às vezes uma lista para escolher, e os
   botões do pé. Cada casa monta a descrição no próprio arquivo (coringa.js,
   reconstrucao.js...) e esta janela só desenha e repassa o clique.

   Quem executa o clique é a tela da partida (`definirExecutor`): ela trava
   a mesa enquanto a ação vai ao servidor e aplica a resposta. */

import { elemento } from "../ui/comum.js";

const cortina = document.querySelector("#modal-decisao");
const chamada = document.querySelector("#decisao-chamada");
const titulo = document.querySelector("#decisao-titulo");
const corpo = document.querySelector("#decisao-corpo");
const opcoes = document.querySelector("#decisao-opcoes");
const tempo = document.querySelector("#decisao-tempo");
const acoes = document.querySelector("#decisao-acoes");

/** Identidade do que está na tela: a mesma decisão não é redesenhada a cada
    consulta — senão o botão sob o mouse piscava e o foco se perdia. */
let chaveAtual = null;
let executar = async (acao) => acao();

export function definirExecutor(funcao) {
  executar = funcao;
}

export const decisaoAberta = () => !cortina.hidden;

/**
 * @param {object} d
 * @param {string} d.chave
 * @param {string} d.chamada  a linha verde de cima
 * @param {string} d.titulo
 * @param {Node[]} [d.corpo]
 * @param {{rotulo: string, detalhe?: string, desabilitada?: boolean, acao: Function}[]} [d.opcoes]
 * @param {{rotulo: string, classe?: string, acao: Function}[]} [d.acoes]
 */
export function abrirDecisao(d) {
  if (d.chave === chaveAtual && !cortina.hidden) return;
  chaveAtual = d.chave;
  chamada.textContent = d.chamada;
  titulo.textContent = d.titulo;
  corpo.replaceChildren(...(d.corpo || []));

  const lista = d.opcoes || [];
  opcoes.hidden = lista.length === 0;
  opcoes.replaceChildren(...lista.map((opcao) => {
    const botao = elemento("button", "liquidacao__vender decisao__opcao");
    botao.type = "button";
    botao.append(elemento("strong", "", opcao.rotulo), elemento("span", "", opcao.detalhe || ""));
    botao.dataset.desabilitada = opcao.desabilitada ? "1" : "";
    botao.disabled = Boolean(opcao.desabilitada);
    botao.addEventListener("click", () => clicar(opcao.acao));
    const item = elemento("li", "liquidacao__item");
    item.appendChild(botao);
    return item;
  }));

  acoes.replaceChildren(...(d.acoes || []).map((acao) => {
    const botao = elemento("button", `jogar__botao jogar__botao--pequeno moldura ${acao.classe || ""}`, acao.rotulo);
    botao.type = "button";
    botao.addEventListener("click", () => clicar(acao.acao));
    return botao;
  }));

  cortina.hidden = false;
}

async function clicar(acao) {
  travarDecisao(true);
  try {
    await executar(acao);
  } finally {
    travarDecisao(false);
  }
}

export function travarDecisao(travada) {
  for (const botao of cortina.querySelectorAll("button")) {
    botao.disabled = travada || botao.dataset.desabilitada === "1";
  }
}

export function definirTempoDaDecisao(texto) {
  tempo.textContent = texto;
}

export function fecharDecisao() {
  cortina.hidden = true;
  chaveAtual = null;
}

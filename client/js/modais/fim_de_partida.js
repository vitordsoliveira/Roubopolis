/* Fim de partida: pódio, confete, fanfarra e o placar de cada um.

   A cena segue a abertura (o sorteio de quem começa): os degraus sobem do
   terceiro para o primeiro, e o vencedor aparece por último, com a coroa
   caindo na cabeça. Embaixo, o placar da partida inteira — patrimônio,
   tudo o que cada um arrecadou, quantas casas comprou e quanto ganhou de
   aluguel —, que é o que a mesa fica comentando depois. */

import { som } from "../core/som.js";
import { iconePixel } from "../tabuleiro/pixel.js";
import { elemento, reais, retratoDe } from "../ui/comum.js";

const cortina = document.querySelector("#modal-fim");
const confete = document.querySelector("#fim-confete");
const chamada = document.querySelector("#fim-chamada");
const titulo = document.querySelector("#fim-titulo");
const podio = document.querySelector("#fim-podio");
const placar = document.querySelector("#fim-placar");
const recompensa = document.querySelector("#fim-recompensa");

const CORES_CONFETE = ["#ffd93d", "#39ff14", "#ff4d84", "#a855f7", "#2f7bff", "#ff8a1f"];
/** Do terceiro para o primeiro: cada degrau sobe com este atraso (s). */
const ATRASO_DO_DEGRAU = { 3: 0.25, 2: 0.65, 1: 1.1 };

export const fimAberto = () => !cortina.hidden;

export function fecharFimDePartida() {
  cortina.hidden = true;
  confete.replaceChildren();
}

/** Classificação do motor; em estado antigo, sem ela, ordena pelo patrimônio. */
function classificacaoDe(estado) {
  if (estado.classificacao?.length) return estado.classificacao;
  return [...estado.jogadores]
    .sort((a, b) => Number(a.falido) - Number(b.falido) || b.patrimonio - a.patrimonio)
    .map((jogador, i) => ({ jogador_id: jogador.jogador_id, posicao: i + 1, patrimonio: jogador.patrimonio, fora: jogador.falido }));
}

function chuvaDeConfete() {
  const pecas = Array.from({ length: 70 }, (_, i) => {
    const peca = elemento("i", "confete");
    peca.style.setProperty("--x", `${Math.random() * 100}%`);
    peca.style.setProperty("--cor", CORES_CONFETE[i % CORES_CONFETE.length]);
    peca.style.setProperty("--duracao", `${2.6 + Math.random() * 2.4}s`);
    peca.style.setProperty("--atraso", `${Math.random() * 3}s`);
    peca.style.setProperty("--desvio", `${(Math.random() - 0.5) * 30}vw`);
    peca.style.setProperty("--giro", `${(Math.random() < 0.5 ? -1 : 1) * (360 + Math.random() * 720)}deg`);
    return peca;
  });
  confete.replaceChildren(...pecas);
}

function lugarNoPodio({ posicao, patrimonio }, jogador, cor) {
  const degrauVisual = Math.min(posicao, 3);
  const lugar = elemento("div", `podio__lugar podio__lugar--${degrauVisual}`);
  lugar.style.setProperty("--cor", cor);
  lugar.style.setProperty("--atraso", `${ATRASO_DO_DEGRAU[degrauVisual]}s`);

  const coroa = elemento("div", "podio__coroa");
  if (posicao === 1) coroa.appendChild(iconePixel("coroa_cheia"));

  const boneco = elemento("div", "podio__boneco");
  boneco.appendChild(retratoDe(jogador, "", "podio__ficha"));

  lugar.append(
    coroa,
    boneco,
    elemento("span", "podio__nome", jogador.nome + (jogador.sou_eu ? " (você)" : "")),
    elemento("span", "podio__patrimonio", reais(patrimonio)),
    elemento("div", "podio__degrau", `${posicao}º`),
  );
  return lugar;
}

function linhaDoPlacar({ posicao, patrimonio, fora }, jogador, cor) {
  const linha = elemento("tr", [jogador.sou_eu ? "fim__eu" : "", fora ? "fim__fora" : ""].join(" ").trim());
  const nome = elemento("td");
  const amostra = elemento("span", "fim__cor");
  amostra.style.setProperty("--cor", cor);
  nome.append(amostra, document.createTextNode(jogador.nome));
  const placarDoJogador = jogador.placar || {};
  const situacao = fora ? (jogador.abandonou ? "saiu" : "faliu") : reais(patrimonio);
  linha.append(
    elemento("td", "", `${posicao}º`),
    nome,
    elemento("td", "", situacao),
    elemento("td", "", reais(placarDoJogador.arrecadado)),
    elemento("td", "", String(placarDoJogador.compras || 0)),
    elemento("td", "", reais(placarDoJogador.aluguel_recebido)),
  );
  return linha;
}

/**
 * Monta e abre a comemoração.
 * @param {object} p
 * @param {object} p.estado  o estado público da partida, já encerrada
 * @param {number|null} p.recompensa  créditos que esta pessoa ganhou
 * @param {boolean} p.espectador
 * @param {(jogador: object, i: number) => string} p.corDe
 */
export function mostrarFimDePartida({ estado, recompensa: creditos, espectador, corDe }) {
  const porId = new Map(estado.jogadores.map((jogador, i) => [jogador.jogador_id, { jogador, cor: corDe(jogador, i) }]));
  const classificacao = classificacaoDe(estado).filter((c) => porId.has(c.jogador_id));
  const vencedores = classificacao.filter((c) => c.posicao === 1 && !c.fora).map((c) => porId.get(c.jogador_id).jogador);

  chamada.textContent = estado.motivo_fim === "tempo" ? "Acabou o tempo" : "Fim de partida — sobrou um de pé";
  if (vencedores.length > 1) {
    titulo.textContent = `Empate: ${vencedores.map((j) => j.nome).join(" e ")}!`;
  } else if (vencedores.length === 1) {
    titulo.textContent = vencedores[0].sou_eu ? "Você venceu!" : `${vencedores[0].nome} venceu!`;
  } else {
    titulo.textContent = "Fim de partida";
  }

  // No pódio, o primeiro fica no meio, o segundo à esquerda e o terceiro à direita.
  const tres = classificacao.filter((c) => !c.fora).slice(0, 3);
  const arrumados = [tres[1], tres[0], tres[2]].filter(Boolean);
  podio.replaceChildren(...arrumados.map((c) => {
    const { jogador, cor } = porId.get(c.jogador_id);
    return lugarNoPodio(c, jogador, cor);
  }));

  placar.replaceChildren(...classificacao.map((c) => {
    const { jogador, cor } = porId.get(c.jogador_id);
    return linhaDoPlacar(c, jogador, cor);
  }));

  recompensa.hidden = espectador || creditos == null;
  recompensa.textContent = creditos > 0
    ? `+${creditos} créditos para gastar na loja`
    : "Quem sai no meio da partida não leva créditos.";

  cortina.hidden = false;
  chuvaDeConfete();
  som.tocar("vitoria");
  document.querySelector("#fim-menu").focus({ preventScroll: true });
}

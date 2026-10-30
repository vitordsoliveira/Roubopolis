/* Leilão: quem está bem atrás na mesa põe uma propriedade sua à venda no
   começo da vez, e o resto da mesa dá lances contra o relógio.

   Três peças moram aqui:
   - a escolha da propriedade, na janela de decisão das casas de evento;
   - a janela do leilão em andamento, que abre para a mesa inteira — quem
     vende acompanha, quem assiste vê, os outros montam o lance com − e +;
   - a janela do resultado, "Leilão encerrado", para todo mundo.

   Os números (lance mínimo, oferta do banco, imposto) chegam prontos do
   servidor; aqui só se desenha. Quem manda o lance é a tela da partida
   (`definirLanceDoLeilao`): ela aplica a resposta como qualquer outra. */

import { api } from "../core/api.js";
import { som } from "../core/som.js";
import { elemento, formatarTempo, porcento, reais } from "../ui/comum.js";

const cortina = document.querySelector("#modal-leilao");
const elNome = document.querySelector("#leilao-nome");
const elVendedor = document.querySelector("#leilao-vendedor");
const elGrupo = document.querySelector("#leilao-grupo");
const elLance = document.querySelector("#leilao-lance");
const elLider = document.querySelector("#leilao-lider");
const elTempo = document.querySelector("#leilao-tempo");
const elBarra = document.querySelector("#leilao-barra");
const elControles = document.querySelector("#leilao-controles");
const botaoMenos = document.querySelector("#leilao-menos");
const botaoMais = document.querySelector("#leilao-mais");
const elValor = document.querySelector("#leilao-valor");
const botaoDar = document.querySelector("#leilao-dar");
const elSituacao = document.querySelector("#leilao-situacao");
const elHistorico = document.querySelector("#leilao-historico");
const elImposto = document.querySelector("#leilao-imposto");

const cortinaFim = document.querySelector("#modal-leilao-fim");

/** O leilão na tela e o que esta pessoa pode fazer nele. */
let atual = null;
/** O lance montado com − e +. */
let valor = 0;
/** O leilão (pelo `n`) que a pessoa escondeu no ×. */
let escondido = null;
/** Quando o relógio dos lances zera, no relógio desta tela. */
let prazoMs = null;
let relogio = null;
let ultimoSegundo = null;
let enviando = false;
let mandarLance = async () => {};

export function definirLanceDoLeilao(funcao) {
  mandarLance = funcao;
}

export const leilaoNaTela = () => !cortina.hidden;
export const leilaoEscondido = () => atual !== null && escondido === atual.leilao.n;
export const fimDoLeilaoAberto = () => !cortinaFim.hidden;

const nomeDe = (jogador) => (jogador?.sou_eu ? "Você" : jogador?.nome || "Alguém");

/** "Média", "Barata · Morro"... com a bolinha na cor do grupo. */
function pintarGrupo(alvo, tabuleiro, casa, regras, nivel) {
  const grupo = tabuleiro.grupos?.[casa?.grupo];
  const morro = casa?.grupo && casa.grupo === regras?.morro?.grupo ? " · Morro" : "";
  const andares = nivel > 0 ? ` · nível ${nivel}` : "";
  alvo.textContent = `${grupo?.rotulo || "Propriedade"}${morro}${andares}`;
  alvo.style.setProperty("--cor", grupo?.cor || "#9b3dff");
}

// --- escolher a propriedade -------------------------------------------------

/** A janela de decisão listando as propriedades de quem vai leiloar. */
export function escolhaDoLeilao({ estado, tabuleiro, eu, codigo, regras }) {
  const minhas = Object.entries(estado.propriedades || {})
    .filter(([, posse]) => posse.dono === eu?.jogador_id)
    .map(([indice, posse]) => ({ casa: tabuleiro.casas[Number(indice)], posse }))
    .sort((a, b) => b.posse.preco_compra - a.posse.preco_compra);
  const segundos = regras?.leilao?.segundos ?? 12;
  const intervalo = regras?.leilao?.rodadas_entre ?? 1;
  const proximo = intervalo > 1 ? `Depois deste, o próximo só daqui a ${intervalo} rodadas.` : "Um leilão por rodada.";

  return {
    chave: `leilao:${minhas.map(({ casa }) => casa.i).join(",")}`,
    chamada: "Leilão",
    titulo: "Escolha o que leiloar",
    corpo: [
      elemento(
        "p",
        "decisao__texto",
        `A mesa dá lances por ${segundos} segundos e o maior leva. Se ninguém der lance, o banco compra pelo valor ao lado. ${proximo}`,
      ),
    ],
    opcoes: minhas.map(({ casa, posse }) => ({
      rotulo: casa?.nome || "Propriedade",
      detalhe: `vale ${reais(posse.preco_compra)} · sem lance, o banco paga ${reais(posse.valor_leilao_banco)}`,
      acao: () => api.abrirLeilao(codigo, casa.i),
    })),
    acoes: [{ rotulo: "Voltar", classe: "compra__recusar", acao: async () => null }],
  };
}

// --- o leilão em andamento ----------------------------------------------------

/**
 * Abre, atualiza ou fecha a janela conforme o estado. Chamada a cada
 * consulta: só o que muda é redesenhado.
 */
export function pintarLeilao({ estado, tabuleiro, eu, espectador, regras }) {
  const leilao = estado?.fase === "leiloando" ? estado.leilao : null;
  if (!leilao) {
    fecharLeilao();
    return;
  }

  const novo = atual?.leilao.n !== leilao.n;
  const vendedor = estado.jogadores.find((j) => j.jogador_id === leilao.vendedor_id);
  const lider = estado.jogadores.find((j) => j.jogador_id === leilao.lider_id);
  const casa = tabuleiro.casas[leilao.casa];
  const souQuemVende = eu?.jogador_id === leilao.vendedor_id;
  const daLance = Boolean(eu && !eu.falido && !espectador && !souQuemVende);
  const maximo = daLance ? eu.caixa - leilao.imposto : 0;
  atual = { leilao, daLance, maximo, lidero: daLance && leilao.lider_id === eu.jogador_id };

  // O lance montado nunca fica abaixo do mínimo: quando alguém cobre, ele
  // sobe junto.
  if (novo || valor < leilao.minimo) valor = leilao.minimo;
  if (valor > maximo) valor = Math.max(leilao.minimo, maximo);

  elNome.textContent = casa?.nome || "Propriedade";
  elVendedor.textContent = souQuemVende ? "Leiloado por você" : `Leiloado por ${vendedor?.nome || "alguém"}`;
  pintarGrupo(elGrupo, tabuleiro, casa, regras, leilao.nivel);

  elLance.textContent = leilao.lance_atual == null ? "—" : reais(leilao.lance_atual);
  elLider.textContent = lider
    ? `${lider.sou_eu ? "Você está" : `${lider.nome} está`} na frente`
    : `Sem lance, o banco paga ${reais(leilao.oferta_do_banco)}`;
  elLider.classList.toggle("leilao__nota--eu", Boolean(lider?.sou_eu));

  pintarHistorico(estado, leilao);
  pintarControles(leilao, eu, souQuemVende);
  elImposto.textContent = `Quem arrematar paga mais ${reais(leilao.imposto)} de imposto — ${porcento(regras?.leilao?.imposto_sobre_tabela)} do valor de tabela — para o Coletor de Impostos.`;

  prazoMs = leilao.ms_restantes == null ? null : performance.now() + leilao.ms_restantes;
  if (novo) {
    escondido = null;
    ultimoSegundo = null;
  }
  if (escondido !== leilao.n) cortina.hidden = false;
  tique();
  if (!relogio) relogio = setInterval(tique, 100);
}

function pintarHistorico(estado, leilao) {
  if (!leilao.lances.length) {
    elHistorico.replaceChildren(elemento("li", "leilao__vazio", "Nenhum lance ainda."));
    return;
  }
  elHistorico.replaceChildren(
    ...[...leilao.lances].reverse().map((lance, i) => {
      const quem = estado.jogadores.find((j) => j.jogador_id === lance.jogador_id);
      const item = elemento("li", i === 0 ? "leilao__item leilao__item--lider" : "leilao__item");
      item.append(elemento("span", "", nomeDe(quem)), elemento("strong", "", reais(lance.valor)));
      return item;
    }),
  );
}

function pintarControles(leilao, eu, souQuemVende) {
  elControles.hidden = !atual.daLance;
  if (souQuemVende) {
    elSituacao.textContent = `Você está leiloando. Se ninguém der lance, o banco paga ${reais(leilao.oferta_do_banco)}.`;
  } else if (!atual.daLance) {
    elSituacao.textContent = "Assistindo ao leilão.";
  } else if (atual.lidero) {
    elSituacao.textContent = "Seu lance é o maior. Agora é torcer para o relógio.";
  } else if (atual.maximo < leilao.minimo) {
    elSituacao.textContent = `Seu caixa (${reais(eu.caixa)}) não cobre o lance mínimo mais o imposto.`;
  } else {
    elSituacao.textContent = `Seu caixa: ${reais(eu.caixa)} · lance máximo: ${reais(atual.maximo)}`;
  }
  pintarValor();
}

function pintarValor() {
  if (!atual) return;
  const { leilao, daLance, lidero, maximo } = atual;
  const pode = daLance && !lidero && maximo >= leilao.minimo && !enviando;
  elValor.textContent = reais(valor);
  botaoMenos.disabled = !pode || valor - leilao.passo < leilao.minimo;
  botaoMais.disabled = !pode || valor + leilao.passo > maximo;
  botaoDar.disabled = !pode || (prazoMs !== null && performance.now() >= prazoMs);
}

/** O relógio e a barra andam aqui, entre uma consulta e outra. Os três
    últimos segundos tiquetaqueiam para a mesa inteira. */
function tique() {
  if (!atual) return;
  const restante = prazoMs === null ? 0 : Math.max(0, prazoMs - performance.now());
  const segundos = Math.ceil(restante / 1000);
  elTempo.textContent = restante > 0 ? formatarTempo(segundos) : "Fechando...";
  const total = (atual.leilao.duracao || 12) * 1000;
  elBarra.style.setProperty("--resta", String(Math.min(1, restante / total)));
  elBarra.parentElement.classList.toggle("leilao__barra--fim", segundos <= 3);
  if (!cortina.hidden && restante > 0 && segundos <= 3 && segundos !== ultimoSegundo) som.tocar("tique");
  ultimoSegundo = segundos;
  if (restante <= 0) pintarValor();
}

export function fecharLeilao() {
  cortina.hidden = true;
  atual = null;
  prazoMs = null;
  if (relogio) clearInterval(relogio);
  relogio = null;
}

/** O × só esconde: o leilão continua, e o botão "Ver o leilão" traz de volta. */
export function esconderLeilao() {
  if (!atual) return;
  escondido = atual.leilao.n;
  cortina.hidden = true;
}

export function reabrirLeilao() {
  if (!atual) return;
  escondido = null;
  cortina.hidden = false;
}

function mudarValor(sentido) {
  if (!atual) return false;
  const { passo, minimo } = atual.leilao;
  const novo = valor + sentido * passo;
  if (novo < minimo || novo > atual.maximo) return false;
  valor = novo;
  pintarValor();
  return true;
}

/* − e +: um clique anda um passo; segurar o botão vai andando sozinho, para
   chegar longe sem clicar vinte vezes. Depois de segurar, o clique que o
   navegador dispara ao soltar não conta de novo. */
function passoQueRepete(botao, sentido) {
  let espera = null;
  let repetindo = null;
  let repetiu = false;
  const parar = () => {
    clearTimeout(espera);
    clearInterval(repetindo);
    espera = null;
    repetindo = null;
  };
  botao.addEventListener("pointerdown", () => {
    parar();
    repetiu = false;
    espera = setTimeout(() => {
      repetindo = setInterval(() => {
        repetiu = true;
        if (!mudarValor(sentido)) parar();
      }, 90);
    }, 380);
  });
  for (const fim of ["pointerup", "pointerleave", "pointercancel"]) botao.addEventListener(fim, parar);
  botao.addEventListener("click", () => {
    if (repetiu) {
      repetiu = false;
      return;
    }
    if (mudarValor(sentido)) som.tocar("clique");
  });
}

passoQueRepete(botaoMenos, -1);
passoQueRepete(botaoMais, 1);

botaoDar.addEventListener("click", async () => {
  if (!atual || enviando) return;
  enviando = true;
  pintarValor();
  try {
    await mandarLance(valor);
  } finally {
    enviando = false;
    pintarValor();
  }
});

// --- o resultado ----------------------------------------------------------------

const doFim = (id) => document.querySelector(`#leilao-fim-${id}`);

/** "Leilão encerrado": quem levou, por quanto, quanto foi de imposto e
    quanto o Coletor juntou. Cada um lê do próprio ponto de vista. */
export function mostrarFimDoLeilao({ resultado, estado, tabuleiro, eu, regras }) {
  const casa = tabuleiro.casas[resultado.casa];
  const vendedor = estado.jogadores.find((j) => j.jogador_id === resultado.vendedor_id);
  const comprador = estado.jogadores.find((j) => j.jogador_id === resultado.comprador_id);
  const souQuemVendeu = eu?.jogador_id === resultado.vendedor_id;
  const souQuemComprou = Boolean(comprador?.sou_eu);
  const comMelhoria = resultado.nivel > 0;
  const referencia = comMelhoria ? resultado.valor_investido : resultado.valor_tabela;

  doFim("quem").textContent = comprador
    ? souQuemComprou ? "Você arrematou o terreno!" : `${comprador.nome} arrematou o terreno`
    : "Ninguém deu lance: o banco comprou o terreno";
  doFim("nome").textContent = casa?.nome || "Propriedade";
  doFim("dono").textContent = `Antigo dono: ${souQuemVendeu ? "você" : vendedor?.nome || "alguém"}`;
  pintarGrupo(doFim("grupo"), tabuleiro, casa, regras, resultado.nivel);

  doFim("valor-rotulo").textContent = comMelhoria ? "Valor investido" : "Valor de tabela";
  doFim("valor").textContent = reais(referencia);
  doFim("lance-rotulo").textContent = comprador ? "Lance vencedor" : "O banco pagou";
  doFim("lance").textContent = reais(comprador ? resultado.lance : resultado.banco);

  // O saldo é do ponto de vista de quem olha: quem comprou economizou (ou
  // pagou acima), quem vendeu recebeu, o resto vê o desconto da mesa.
  const pago = comprador ? resultado.lance : resultado.banco;
  const diferenca = referencia - pago;
  let rotulo;
  let saldo;
  let bom = true;
  if (souQuemVendeu) {
    rotulo = "Você recebeu";
    saldo = pago;
  } else if (souQuemComprou) {
    rotulo = diferenca >= 0 ? "Você economizou" : "Você pagou acima do valor";
    saldo = Math.abs(diferenca);
    bom = diferenca >= 0;
  } else {
    rotulo = diferenca >= 0 ? "Abaixo do valor" : "Acima do valor";
    saldo = Math.abs(diferenca);
  }
  doFim("saldo-rotulo").textContent = rotulo;
  doFim("saldo").textContent = reais(saldo);
  doFim("saldo-placa").classList.toggle("leilao__placa--verde", bom);
  doFim("saldo-placa").classList.toggle("leilao__placa--vermelha", !bom);

  doFim("imposto-rotulo").textContent = comprador
    ? `Imposto do leilão (${porcento(regras?.leilao?.imposto_sobre_tabela)} da tabela)`
    : "Imposto do leilão (o banco não paga)";
  doFim("imposto").textContent = reais(resultado.imposto);
  doFim("cofre").textContent = `${reais(resultado.coletor)} acumulado`;

  cortinaFim.hidden = false;
  doFim("continuar").focus();
}

export function fecharFimDoLeilao() {
  cortinaFim.hidden = true;
}

doFim("continuar").addEventListener("click", () => {
  som.tocar("clique");
  fecharFimDoLeilao();
});

cortinaFim.addEventListener("click", (evento) => {
  if (evento.target === cortinaFim) fecharFimDoLeilao();
});

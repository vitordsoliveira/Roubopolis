/* Cartões do que chega de outra pessoa enquanto a tela está aberta: o
   convite de um amigo para a sala dele e o pedido de amizade. O menu e o
   lobby consultam o servidor de tempos em tempos, e cada novidade aparece
   no topo da tela, com a resposta ali mesmo.

   O × só tira o cartão da frente: o convite segue valendo até vencer, e o
   pedido continua no painel de AMIGOS. Fechado, não volta enquanto o jogo
   estiver aberto — nem ao trocar de tela. Convite que o dono renova tem
   chave nova, e aí volta. */

import { api } from "../core/api.js";
import { som } from "../core/som.js";
import { elemento, inicial } from "./comum.js";
import { toast } from "./toast.js";

const INTERVALO_MS = 4000;
const CHAVE_FECHADOS = "roubopolis.notificacoes-fechadas";
const MAXIMO_FECHADOS = 50;

let pilha = null;
let relogio = null;
let aoAtualizar = () => {};
/** chave → cartão na tela */
const cartoes = new Map();

function fechados() {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(CHAVE_FECHADOS) || "[]"));
  } catch {
    return new Set();
  }
}

function lembrarFechado(chave) {
  try {
    sessionStorage.setItem(CHAVE_FECHADOS, JSON.stringify([...fechados(), chave].slice(-MAXIMO_FECHADOS)));
  } catch {
    /* sem armazenamento: o cartão volta na próxima tela, nada pior que isso */
  }
}

/** Começa a consultar. `aoAtualizar(dados)` recebe cada resposta — o menu
    acende o selo do AMIGOS com os pedidos. Chamar de novo não duplica. */
export function acompanharNotificacoes(opcoes = {}) {
  if (opcoes.aoAtualizar) aoAtualizar = opcoes.aoAtualizar;
  if (relogio) return;
  if (!pilha) {
    pilha = elemento("div", "notificacoes");
    pilha.setAttribute("aria-live", "polite");
    document.body.appendChild(pilha);
  }
  relogio = setInterval(consultar, INTERVALO_MS);
  consultar();
}

export function pararNotificacoes() {
  if (relogio) clearInterval(relogio);
  relogio = null;
  for (const chave of [...cartoes.keys()]) tirar(chave);
}

async function consultar() {
  if (document.hidden) return;
  let dados;
  try {
    dados = await api.notificacoes();
  } catch (erro) {
    // Token que não vale mais: quem cuida é a tela (o menu volta ao login).
    if (erro.status === 401) pararNotificacoes();
    return;
  }
  if (!relogio) return; // parou enquanto a resposta vinha
  pintar(dados);
  aoAtualizar(dados);
}

function pintar({ convites, pedidos }) {
  const itens = [
    ...convites.map((convite) => [convite.chave, () => cartaoDeConvite(convite)]),
    ...pedidos.map((pedido) => [`pedido-${pedido.id}`, () => cartaoDePedido(pedido)]),
  ];

  // O que o servidor não manda mais (venceu, foi respondido em outro lugar) sai.
  const vivas = new Set(itens.map(([chave]) => chave));
  for (const chave of [...cartoes.keys()]) {
    if (!vivas.has(chave)) tirar(chave);
  }

  const jaFechados = fechados();
  let chegouNovo = false;
  for (const [chave, montar] of itens) {
    if (cartoes.has(chave) || jaFechados.has(chave)) continue;
    const cartao = montar();
    cartoes.set(chave, cartao);
    pilha.appendChild(cartao);
    chegouNovo = true;
  }
  if (chegouNovo) som.tocar("chamado");
}

function tirar(chave) {
  cartoes.get(chave)?.remove();
  cartoes.delete(chave);
}

/** Responde pelo cartão: trava os botões enquanto a resposta vai e tira o
    cartão quando ela volta — com erro também: o servidor já descartou o
    que não vale mais, e falha de rede faz o cartão voltar na próxima
    consulta. */
async function responder(chave, tarefa) {
  cartoes.get(chave)?.querySelectorAll("button").forEach((botao) => (botao.disabled = true));
  try {
    await tarefa();
  } catch (erro) {
    som.tocar("erro");
    toast(erro.message, "erro");
  }
  tirar(chave);
  consultar();
}

// --- cartões ---------------------------------------------------------------

function foto(pessoa) {
  const quadro = elemento("span", "notificacao__foto");
  if (pessoa.foto) {
    const img = elemento("img");
    img.src = pessoa.foto;
    img.alt = "";
    quadro.appendChild(img);
  } else {
    quadro.textContent = inicial(pessoa.nome);
  }
  return quadro;
}

function botao(rotulo, classe, aoClicar) {
  const el = elemento("button", `botao botao--pequeno ${classe}`, rotulo);
  el.type = "button";
  el.addEventListener("click", aoClicar);
  return el;
}

function cartao({ chave, pessoa, titulo, texto, acoes }) {
  const el = elemento("article", "notificacao");
  const corpo = elemento("div", "notificacao__corpo");
  const caixaAcoes = elemento("div", "notificacao__acoes");
  caixaAcoes.append(...acoes);
  corpo.append(elemento("p", "notificacao__titulo", titulo), texto, caixaAcoes);

  const fechar = elemento("button", "notificacao__fechar", "×");
  fechar.type = "button";
  fechar.title = "Fechar sem responder";
  fechar.setAttribute("aria-label", "Fechar sem responder");
  fechar.addEventListener("click", () => {
    som.tocar("clique");
    lembrarFechado(chave);
    tirar(chave);
  });

  el.append(foto(pessoa), corpo, fechar);
  return el;
}

function cartaoDeConvite(convite) {
  const texto = elemento("p", "notificacao__texto");
  texto.append(
    elemento("strong", "", convite.de.nome),
    ` te chamou para a sala ${convite.sala} (${convite.jogadores}/${convite.lugares} jogadores).`,
  );
  return cartao({
    chave: convite.chave,
    pessoa: convite.de,
    titulo: "Convite para jogar",
    texto,
    acoes: [
      botao("Entrar", "botao--verde", () => responder(convite.chave, async () => {
        const { codigo } = await api.aceitarConvite(convite.id);
        som.tocar("entrar");
        location.href = `/lobby?codigo=${codigo}`;
      })),
      botao("Recusar", "botao--perigo", () => responder(convite.chave, async () => {
        await api.recusarConvite(convite.id);
        som.tocar("voltar");
      })),
    ],
  });
}

function cartaoDePedido(pedido) {
  const chave = `pedido-${pedido.id}`;
  const texto = elemento("p", "notificacao__texto");
  texto.append(elemento("strong", "", pedido.nome), ` (@${pedido.login || "?"}) quer ser seu amigo.`);
  return cartao({
    chave,
    pessoa: pedido,
    titulo: "Pedido de amizade",
    texto,
    acoes: [
      botao("Aceitar", "botao--verde", () => responder(chave, async () => {
        await api.aceitarAmizade(pedido.id);
        som.tocar("sucesso");
        toast(`Agora você e ${pedido.nome} são amigos.`, "ok");
      })),
      botao("Recusar", "botao--perigo", () => responder(chave, async () => {
        await api.desfazerAmizade(pedido.id);
        som.tocar("voltar");
      })),
    ],
  });
}

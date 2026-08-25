/* Lobby: um lugar por jogador, com o boneco num carrossel logo abaixo.

   A atualização é por consulta a cada poucos segundos. Quando
   server/sockets/lobby.py existir, troque `iniciarConsulta` por um socket —
   o formato do estado é o mesmo. */

import { api, guardado } from "../core/api.js";
import { toast } from "../ui/toast.js";

const fila = document.querySelector("#slots");
const rotuloCodigo = document.querySelector("#codigo-sala");
const botaoPronto = document.querySelector("#pronto");
const botaoIniciar = document.querySelector("#iniciar");
const aviso = document.querySelector("#aviso");

const codigo = new URLSearchParams(location.search).get("codigo")?.toUpperCase() || "";
let estado = null;
let consulta = null;

if (!codigo || !guardado.token()) {
  toast("Volte ao menu e digite seu nome primeiro.", "erro");
  setTimeout(() => (location.href = "/"), 1400);
} else {
  rotuloCodigo.textContent = codigo;
  entrar();
}

/** Entrar é idempotente: quem já está na sala só recebe o estado de volta. */
async function entrar() {
  try {
    pintar(await api.entrarNaSala(codigo));
    iniciarConsulta();
  } catch (erro) {
    toast(erro.message, "erro");
    setTimeout(() => (location.href = "/"), 1800);
  }
}

// --- desenho --------------------------------------------------------

function elemento(tag, classe, texto) {
  const el = document.createElement(tag);
  if (classe) el.className = classe;
  if (texto !== undefined) el.textContent = texto;
  return el;
}

function montarPerfil(participante) {
  const perfil = elemento("div", "slot__perfil");
  perfil.appendChild(elemento("span", "slot__nome", participante.nome));

  const marcas = elemento("div", "slot__marcas");
  if (participante.dono) marcas.appendChild(elemento("span", "slot__marca slot__marca--dono", "DONO"));
  if (participante.pronto) marcas.appendChild(elemento("span", "slot__marca slot__marca--pronto", "PRONTO"));
  perfil.appendChild(marcas);

  return perfil;
}

function montarCarrossel(participante) {
  const carrossel = elemento("div", "carrossel");
  carrossel.appendChild(elemento("span", "carrossel__rotulo", "personagem"));

  function seta(passo, sinal, rotulo) {
    const botao = elemento("button", "carrossel__seta", sinal);
    botao.type = "button";
    botao.dataset.passo = String(passo);
    // Só o dono do lugar folheia o próprio boneco.
    botao.disabled = !participante.sou_eu;
    botao.setAttribute("aria-label", rotulo);
    return botao;
  }

  const palco = elemento("div", "carrossel__boneco");
  if (participante.personagem?.sprite) {
    const img = elemento("img");
    img.src = participante.personagem.sprite;
    img.alt = participante.personagem.nome;
    palco.appendChild(img);
  } else {
    palco.appendChild(elemento("span", "carrossel__vazio", "sem boneco livre"));
  }

  const linha = elemento("div", "carrossel__linha");
  linha.append(seta(-1, "<", "Personagem anterior"), palco, seta(1, ">", "Próximo personagem"));

  carrossel.appendChild(linha);
  return carrossel;
}

function montarSlots(dados) {
  const itens = [];
  for (let lugar = 0; lugar < dados.max_jogadores; lugar += 1) {
    const participante = dados.participantes[lugar];

    if (!participante) {
      const vazio = elemento("li", "slot slot--vazio");
      const perfil = elemento("div", "slot__perfil");
      perfil.appendChild(elemento("span", "slot__mais", "+"));
      vazio.append(perfil, elemento("span", "slot__espera", "lugar vago"));
      itens.push(vazio);
      continue;
    }

    const slot = elemento("li", "slot" + (participante.sou_eu ? " slot--eu" : ""));
    slot.append(montarPerfil(participante), montarCarrossel(participante));
    itens.push(slot);
  }
  fila.replaceChildren(...itens);
}

function pintar(dados) {
  estado = dados;
  montarSlots(dados);

  const eu = dados.participantes.find((p) => p.sou_eu);
  botaoPronto.disabled = !eu?.personagem;
  botaoPronto.textContent = eu?.pronto ? "NÃO ESTOU PRONTO" : "ESTOU PRONTO";
  botaoIniciar.hidden = !dados.sou_dono;
  aviso.textContent = mensagemDeEspera(dados);
}

function mensagemDeEspera(dados) {
  if (dados.participantes.length < 2) {
    return `Passe o código ${dados.codigo} para alguém entrar. Faltam jogadores.`;
  }
  if (!dados.pode_iniciar) return "Esperando todo mundo ficar pronto.";
  return "Todo mundo pronto. O tabuleiro entra na próxima fase do projeto.";
}

// --- trocar de boneco ------------------------------------------------

/** Só entram na roda os bonecos livres e o que já é meu. */
function vizinho(passo) {
  const opcoes = estado.personagens.filter((p) => p.disponivel || p.meu);
  if (!opcoes.length) return null;
  const atual = opcoes.findIndex((p) => p.meu);
  if (atual < 0) return opcoes[0].slug;
  return opcoes[(atual + passo + opcoes.length) % opcoes.length].slug;
}

fila.addEventListener("click", async (evento) => {
  const seta = evento.target.closest(".carrossel__seta");
  if (!seta || seta.disabled || !estado) return;

  const alvo = vizinho(Number(seta.dataset.passo));
  if (!alvo) return;

  try {
    pintar(await api.escolherPersonagem(codigo, alvo));
  } catch (erro) {
    toast(erro.message, "erro");
    atualizar(); // alguém pegou antes: reflete o estado real na hora
  }
});

// --- ações ------------------------------------------------------------

botaoPronto.addEventListener("click", async () => {
  const eu = estado?.participantes.find((p) => p.sou_eu);
  try {
    pintar(await api.marcarPronto(codigo, !eu?.pronto));
  } catch (erro) {
    toast(erro.message, "erro");
  }
});

document.querySelector("#copiar").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(codigo);
    toast(`Código ${codigo} copiado.`, "ok");
  } catch {
    // Sem permissão de área de transferência: mostrar já resolve.
    toast(`Anote o código: ${codigo}`);
  }
});

document.querySelector("#voltar").addEventListener("click", async () => {
  pararConsulta();
  try {
    await api.sairDaSala(codigo);
  } catch {
    /* sair é melhor esforço: se falhar, o menu ainda é o destino */
  }
  location.href = "/";
});

// --- consulta periódica -----------------------------------------------

async function atualizar() {
  if (document.hidden) return;
  try {
    pintar(await api.verSala(codigo));
  } catch (erro) {
    if (erro.status === 404) {
      pararConsulta();
      toast("A sala foi encerrada.", "erro");
      setTimeout(() => (location.href = "/"), 1600);
    }
  }
}

function iniciarConsulta() {
  pararConsulta();
  consulta = setInterval(atualizar, 2500);
}

function pararConsulta() {
  if (consulta) clearInterval(consulta);
  consulta = null;
}

// Voltar para a aba mostra o estado atual sem esperar o próximo ciclo.
document.addEventListener("visibilitychange", () => !document.hidden && atualizar());

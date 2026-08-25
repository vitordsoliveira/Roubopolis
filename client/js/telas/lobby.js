/* Lobby: mostra o código da sala, deixa escolher o boneco e acompanha
   quem já está na mesa.

   A atualização é por consulta a cada poucos segundos. Quando
   server/sockets/lobby.py existir, troque `iniciarConsulta` por um socket —
   o formato do estado é o mesmo. */

import { api, guardado } from "../core/api.js";
import { toast } from "../ui/toast.js";

const PECAS_DO_BONECO = `
  <i class="boneco__chapeu"></i><i class="boneco__aba"></i>
  <i class="boneco__cabelo"></i><i class="boneco__cabeca"></i>
  <i class="boneco__olho boneco__olho--e"></i><i class="boneco__olho boneco__olho--d"></i>
  <i class="boneco__boca"></i>
  <i class="boneco__corpo"></i><i class="boneco__detalhe"></i>
  <i class="boneco__braco boneco__braco--e"></i><i class="boneco__braco boneco__braco--d"></i>
  <i class="boneco__mao boneco__mao--e"></i><i class="boneco__mao boneco__mao--d"></i>
  <i class="boneco__calca"></i><i class="boneco__vinco"></i>
  <i class="boneco__sapato boneco__sapato--e"></i><i class="boneco__sapato boneco__sapato--d"></i>`;

const CORES_DA_PALETA = ["chapeu", "cabelo", "pele", "roupa", "detalhe", "calca", "sapato"];

const grade = document.querySelector("#personagens");
const listaMesa = document.querySelector("#mesa");
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

function montarBoneco(personagem, meu) {
  const boneco = document.createElement("div");
  boneco.className = "boneco";
  if (meu) boneco.classList.add("boneco--meu");
  else if (!personagem.disponivel) boneco.classList.add("boneco--tomado");

  const paleta = personagem.paleta || {};
  for (const chave of CORES_DA_PALETA) {
    if (paleta[chave]) boneco.style.setProperty(`--${chave}`, paleta[chave]);
  }
  boneco.innerHTML = PECAS_DO_BONECO;
  return boneco;
}

function montarCartao(personagem) {
  const cartao = document.createElement("button");
  cartao.type = "button";
  cartao.className = "personagem" + (personagem.meu ? " personagem--meu" : "");
  cartao.style.setProperty("--cor-do-personagem", personagem.cor);
  // Já é de outra pessoa: fica à vista, mas não dá para clicar.
  cartao.disabled = !personagem.disponivel && !personagem.meu;
  cartao.dataset.slug = personagem.slug;

  const faixa = document.createElement("span");
  faixa.className = "personagem__faixa";

  const nome = document.createElement("span");
  nome.className = "personagem__nome";
  nome.textContent = personagem.nome;

  const situacao = document.createElement("span");
  situacao.className = "personagem__estado";
  if (personagem.meu) situacao.textContent = "É O SEU";
  else if (personagem.tomado_por) situacao.textContent = `DE ${personagem.tomado_por.toUpperCase()}`;
  else situacao.textContent = personagem.descricao || "LIVRE";

  cartao.append(montarBoneco(personagem, personagem.meu), faixa, nome, situacao);
  return cartao;
}

function pintarMesa(dados) {
  listaMesa.replaceChildren();

  for (const participante of dados.participantes) {
    const linha = document.createElement("li");
    linha.className = "mesa__jogador" + (participante.sou_eu ? " mesa__jogador--eu" : "");
    if (participante.personagem) {
      linha.style.setProperty("--cor-do-personagem", participante.personagem.cor);
    }

    const nome = document.createElement("span");
    nome.className = "mesa__nome";
    nome.textContent = participante.personagem
      ? `${participante.nome} · ${participante.personagem.nome}`
      : `${participante.nome} · escolhendo...`;
    linha.appendChild(nome);

    if (participante.dono) linha.appendChild(marca("DONO", "dono"));
    if (participante.pronto) linha.appendChild(marca("PRONTO", "pronto"));
    listaMesa.appendChild(linha);
  }

  for (let i = 0; i < dados.vagas; i += 1) {
    const vaga = document.createElement("li");
    vaga.className = "mesa__vaga";
    vaga.textContent = "vaga aberta";
    listaMesa.appendChild(vaga);
  }
}

function marca(texto, tipo) {
  const span = document.createElement("span");
  span.className = `mesa__marca mesa__marca--${tipo}`;
  span.textContent = texto;
  return span;
}

function pintar(dados) {
  estado = dados;
  grade.replaceChildren(...dados.personagens.map(montarCartao));
  pintarMesa(dados);

  const eu = dados.participantes.find((p) => p.sou_eu);
  const escolhi = Boolean(eu?.personagem);

  botaoPronto.disabled = !escolhi;
  botaoPronto.textContent = eu?.pronto ? "NÃO ESTOU PRONTO" : "ESTOU PRONTO";
  botaoIniciar.hidden = !dados.sou_dono;

  aviso.textContent = mensagemDeEspera(dados, escolhi);
}

function mensagemDeEspera(dados, escolhi) {
  if (!escolhi) return `Escolha um dos ${dados.disponiveis} bonecos livres.`;
  if (dados.participantes.length < 2) {
    return `Passe o código ${dados.codigo} para alguém entrar. Faltam jogadores.`;
  }
  if (!dados.pode_iniciar) return "Esperando todo mundo escolher e ficar pronto.";
  return "Todo mundo pronto. O tabuleiro entra na próxima fase do projeto.";
}

// --- ações ----------------------------------------------------------

grade.addEventListener("click", async (evento) => {
  const cartao = evento.target.closest(".personagem");
  if (!cartao || cartao.disabled) return;
  try {
    pintar(await api.escolherPersonagem(codigo, cartao.dataset.slug));
  } catch (erro) {
    toast(erro.message, "erro");
    atualizar(); // alguém pegou antes: reflete o estado real na hora
  }
});

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

// --- consulta periódica ---------------------------------------------

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

/* Tela inicial: guarda o nome e cria (ou entra em) uma sala. */

import { api, guardado } from "../core/api.js";
import { toast } from "../ui/toast.js";

const campoNome = document.querySelector("#nome");
const dica = document.querySelector("#dica");
const opcoes = document.querySelector("#opcoes");
const painelCodigo = document.querySelector("#painel-codigo");
const campoCodigo = document.querySelector("#codigo");
const painelConfig = document.querySelector("#painel-config");
const botaoSom = document.querySelector("#som");

let ocupado = false;

// --- nome -----------------------------------------------------------

campoNome.value = guardado.nome();
campoNome.focus();
campoNome.select();

campoNome.addEventListener("input", () => {
  campoNome.classList.remove("campo--erro");
  dica.textContent = "";
  dica.classList.remove("menu__dica--erro");
});

function nomeValido() {
  const nome = campoNome.value.trim();
  if (nome.length < 3) {
    avisarNoCampo("Digite seu nome — 3 letras no mínimo.");
    return null;
  }
  return nome;
}

function avisarNoCampo(mensagem) {
  dica.textContent = mensagem;
  dica.classList.add("menu__dica--erro");
  campoNome.classList.remove("campo--erro");
  // Reinicia a animação de tremida mesmo em cliques seguidos.
  void campoNome.offsetWidth;
  campoNome.classList.add("campo--erro");
  campoNome.focus();
}

// --- ações ----------------------------------------------------------

async function comIndicador(tarefa) {
  if (ocupado) return;
  ocupado = true;
  opcoes.setAttribute("aria-busy", "true");
  try {
    await tarefa();
  } catch (erro) {
    toast(erro.message, "erro");
  } finally {
    ocupado = false;
    opcoes.removeAttribute("aria-busy");
  }
}

function jogar() {
  const nome = nomeValido();
  if (!nome) return;
  return comIndicador(async () => {
    await api.identificar(nome);
    const sala = await api.criarSala();
    window.location.href = `/lobby?codigo=${sala.codigo}`;
  });
}

function entrarComCodigo() {
  const nome = nomeValido();
  if (!nome) return;
  const codigo = campoCodigo.value.trim().toUpperCase();
  if (codigo.length < 4) {
    campoCodigo.classList.add("campo--erro");
    campoCodigo.focus();
    return;
  }
  return comIndicador(async () => {
    await api.identificar(nome);
    const sala = await api.entrarNaSala(codigo);
    window.location.href = `/lobby?codigo=${sala.codigo}`;
  });
}

// --- painéis --------------------------------------------------------

function abrir(painel) {
  painel.hidden = false;
  painel.querySelector("input, button")?.focus();
}

function fechar(painel) {
  painel.hidden = true;
  campoCodigo.classList.remove("campo--erro");
}

document.addEventListener("keydown", (evento) => {
  if (evento.key !== "Escape") return;
  [painelCodigo, painelConfig].forEach((p) => {
    if (!p.hidden) fechar(p);
  });
});

// Clicar no fundo escuro fecha o painel.
[painelCodigo, painelConfig].forEach((painel) => {
  painel.addEventListener("click", (evento) => {
    if (evento.target === painel) fechar(painel);
  });
});

// --- som (só a preferência; o áudio entra junto com os assets) ------

function pintarSom() {
  const ligado = guardado.som();
  botaoSom.setAttribute("aria-pressed", String(ligado));
  botaoSom.textContent = ligado ? "LIGADO" : "DESLIGADO";
}
pintarSom();

botaoSom.addEventListener("click", () => {
  guardado.salvarSom(!guardado.som());
  pintarSom();
});

document.querySelector("#esquecer").addEventListener("click", () => {
  guardado.esquecer();
  campoNome.value = "";
  fechar(painelConfig);
  toast("Seus dados neste navegador foram apagados.", "ok");
  campoNome.focus();
});

// --- roteamento dos cliques ----------------------------------------

const acoes = {
  jogar,
  "abrir-codigo": () => abrir(painelCodigo),
  "entrar-codigo": entrarComCodigo,
  config: () => abrir(painelConfig),
  fechar: (elemento) => fechar(elemento.closest(".painel")),
  amigos: () => toast("AMIGOS ainda não foi construído. Em breve.", ""),
  loja: () => toast("A LOJA ainda não abriu. Em breve.", ""),
  sair: () => {
    guardado.esquecer();
    campoNome.value = "";
    campoNome.focus();
    toast("Até a próxima. Seu nome foi esquecido neste navegador.", "ok");
  },
};

document.addEventListener("click", (evento) => {
  const alvo = evento.target.closest("[data-acao]");
  if (!alvo) return;
  acoes[alvo.dataset.acao]?.(alvo);
});

// Enter no nome já começa a partida; no código, entra na sala.
campoNome.addEventListener("keydown", (e) => e.key === "Enter" && jogar());
campoCodigo.addEventListener("keydown", (e) => e.key === "Enter" && entrarComCodigo());

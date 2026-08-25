/* Tela inicial: guarda o nome e cria (ou entra em) uma sala. */

import { api, guardado } from "../core/api.js";
import { toast } from "../ui/toast.js";

const campoLogin = document.querySelector("#login");
const campoSenha = document.querySelector("#senha");
const campoNome = document.querySelector("#nome");
const blocoNome = document.querySelector("#bloco-nome");
const botaoAcessar = document.querySelector("#acessar");
const abas = document.querySelectorAll("[data-modo]");
const dica = document.querySelector("#dica");
const opcoes = document.querySelector("#opcoes");
const painelCodigo = document.querySelector("#painel-codigo");
const campoCodigo = document.querySelector("#codigo");
const painelConfig = document.querySelector("#painel-config");
const botaoSom = document.querySelector("#som");

let ocupado = false;
let modo = "entrar";

// --- identidade só desta aba (para testar a sala sozinho) ------------

if (new URLSearchParams(location.search).has("novo")) {
  guardado.usarAbaPropria();
  history.replaceState(null, "", "/"); // tira o ?novo=1 da barra
}

if (guardado.abaPropria()) {
  document.querySelector(".menu__rodape").textContent =
    "v0.1 - esta aba tem um jogador próprio";
}

// --- nome -----------------------------------------------------------

campoNome.value = guardado.nome();
campoLogin.focus();

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

function mostrarJogo(jogador) {
  campoNome.value = jogador.nome;
  document.querySelector(".menu__login").hidden = true;
  opcoes.hidden = false;
  document.querySelector(".menu__rodape").textContent = `Olá, ${jogador.nome}!`;
  opcoes.querySelector("button")?.focus();
}

function voltarAoLogin() {
  guardado.esquecer();
  campoLogin.value = "";
  campoSenha.value = "";
  campoNome.value = "";
  document.querySelector(".menu__login").hidden = false;
  opcoes.hidden = true;
  document.querySelector(".menu__rodape").textContent = "v0.1 - entre para jogar";
  campoLogin.focus();
}

function validarAcesso() {
  if (campoLogin.value.trim().length < 3) {
    campoLogin.focus();
    dica.textContent = "Digite seu usuário.";
    return false;
  }
  if (campoSenha.value.length < 6) {
    campoSenha.focus();
    dica.textContent = "A senha precisa ter pelo menos 6 caracteres.";
    return false;
  }
  if (modo === "cadastrar" && !nomeValido()) return false;
  return true;
}

async function acessar() {
  if (!validarAcesso()) return;
  return comIndicador(async () => {
    const jogador = modo === "entrar"
      ? await api.entrar(campoLogin.value, campoSenha.value)
      : await api.cadastrar(campoLogin.value, campoSenha.value, campoNome.value.trim());
    mostrarJogo(jogador);
  });
}

abas.forEach((aba) => aba.addEventListener("click", () => {
  modo = aba.dataset.modo;
  abas.forEach((item) => {
    const ativo = item === aba;
    item.classList.toggle("login__aba--ativa", ativo);
    item.setAttribute("aria-selected", String(ativo));
  });
  blocoNome.hidden = modo !== "cadastrar";
  botaoAcessar.textContent = modo === "entrar" ? "Entrar" : "Criar conta";
  campoSenha.setAttribute("autocomplete", modo === "entrar" ? "current-password" : "new-password");
}));

botaoAcessar.addEventListener("click", acessar);
campoSenha.addEventListener("keydown", (evento) => evento.key === "Enter" && acessar());

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
    voltarAoLogin();
    toast("Você saiu da conta.", "ok");
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

if (guardado.token()) {
  api.quemSouEu?.().then(mostrarJogo).catch(() => guardado.esquecer());
}

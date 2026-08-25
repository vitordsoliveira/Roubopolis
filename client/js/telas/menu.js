/* Tela inicial: guarda o nome e cria (ou entra em) uma sala. */

import { api, guardado } from "../core/api.js";
import { som } from "../core/som.js";
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
const painelPerfil = document.querySelector("#painel-perfil");
const painelSaida = document.querySelector("#painel-saida");
const atalhoPerfil = document.querySelector("#atalho-perfil");
const atalhoFoto = document.querySelector("#atalho-foto");
const atalhoInicial = document.querySelector("#atalho-inicial");
const atalhoNome = document.querySelector("#atalho-nome");
const rodapeMensagem = document.querySelector("#rodape-mensagem");
const botaoSom = document.querySelector("#som");
const modoExibicao = document.querySelector("#modo-exibicao");
const botaoAplicarModoExibicao = document.querySelector("#aplicar-modo-exibicao");
const controleVolumeSom = document.querySelector("#volume-som");
const valorVolumeSom = document.querySelector("#valor-volume-som");
const perfilPartidas = document.querySelector("#perfil-partidas");
const perfilVitorias = document.querySelector("#perfil-vitorias");
const perfilTaxa = document.querySelector("#perfil-taxa");
const perfilAviso = document.querySelector("#perfil-aviso");
const perfilFoto = document.querySelector("#perfil-foto");
const perfilFotoVazia = document.querySelector("#perfil-foto-vazia");
const perfilArquivo = document.querySelector("#perfil-arquivo");
const perfilRemoverFoto = document.querySelector("#perfil-remover-foto");
const perfilNomeCampo = document.querySelector("#perfil-nome-campo");
const perfilSenhaAtual = document.querySelector("#perfil-senha-atual");
const perfilSenhaNova = document.querySelector("#perfil-senha-nova");
const perfilSalvar = document.querySelector("#perfil-salvar");

let ocupado = false;
let modo = "entrar";

/* Foto escolhida mas ainda não enviada. Três estados distintos:
   undefined = não mexeu | string = trocou | null = mandou remover. */
let fotoPendente;

// --- identidade só desta aba (para testar a sala sozinho) ------------

if (new URLSearchParams(location.search).has("novo")) {
  guardado.usarAbaPropria();
  history.replaceState(null, "", "/"); // tira o ?novo=1 da barra
}

if (guardado.abaPropria()) {
  rodapeMensagem.textContent =
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

/** Pinta o cartão do canto: quadrado com a foto (ou a inicial) e o nome. */
function pintarAtalho(jogador) {
  const temFoto = Boolean(jogador.foto);
  atalhoNome.textContent = jogador.nome;
  atalhoInicial.textContent = (jogador.nome || "?").trim().charAt(0);
  atalhoFoto.src = temFoto ? jogador.foto : "";
  atalhoFoto.hidden = !temFoto;
  atalhoInicial.hidden = temFoto;
  atalhoPerfil.hidden = false;
}

function mostrarJogo(jogador) {
  campoNome.value = jogador.nome;
  document.querySelector(".menu__login").hidden = true;
  opcoes.hidden = false;
  pintarAtalho(jogador);
  opcoes.querySelector("button")?.focus();
}

function voltarAoLogin() {
  guardado.esquecer();
  campoLogin.value = "";
  campoSenha.value = "";
  campoNome.value = "";
  document.querySelector(".menu__login").hidden = false;
  opcoes.hidden = true;
  rodapeMensagem.textContent = "v0.1 - entre para jogar";
  atalhoPerfil.hidden = true;
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
    som.tocar("sucesso");
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
    som.tocar("erro");
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
    await new Promise((resolver) => setTimeout(resolver, 140));
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
    som.tocar("entrar");
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

function abrirConfiguracao() {
  pintarTelaCheia();
  abrir(painelConfig);
}

function fechar(painel) {
  painel.hidden = true;
  campoCodigo.classList.remove("campo--erro");
}

// --- perfil ---------------------------------------------------------

//: Lado do avatar em pixels. Pequeno de propósito: a foto viaja como data
//: URL e é guardada no banco, então cada pixel a mais custa em toda resposta.
const LADO_FOTO = 192;

function avisarPerfil(mensagem, ok = false) {
  perfilAviso.textContent = mensagem;
  perfilAviso.hidden = !mensagem;
  perfilAviso.classList.toggle("perfil__aviso--ok", ok);
}

function mostrarFoto(foto) {
  const tem = Boolean(foto);
  perfilFoto.src = tem ? foto : "";
  perfilFoto.hidden = !tem;
  perfilFotoVazia.hidden = tem;
}

function preencherPerfil({ jogador, estatisticas }) {
  perfilNomeCampo.value = jogador.nome;
  perfilPartidas.textContent = estatisticas.partidas_jogadas;
  perfilVitorias.textContent = estatisticas.vitorias;
  perfilTaxa.textContent = `${estatisticas.taxa_vitorias}%`;
  mostrarFoto(jogador.foto);
  pintarAtalho(jogador);
}

async function abrirPerfil() {
  abrir(painelPerfil);
  avisarPerfil("");
  // Senha nunca volta preenchida, e a foto pendente de uma abertura
  // anterior não pode vazar para esta.
  perfilSenhaAtual.value = "";
  perfilSenhaNova.value = "";
  fotoPendente = undefined;
  try {
    preencherPerfil(await api.perfil());
  } catch (erro) {
    avisarPerfil(erro.message);
  }
}

/** Recorta no centro, reduz e devolve um data URL JPEG. */
async function prepararFoto(arquivo) {
  const bitmap = await createImageBitmap(arquivo);
  const lado = Math.min(bitmap.width, bitmap.height);
  const tela = document.createElement("canvas");
  tela.width = LADO_FOTO;
  tela.height = LADO_FOTO;
  tela.getContext("2d").drawImage(
    bitmap,
    (bitmap.width - lado) / 2,
    (bitmap.height - lado) / 2,
    lado,
    lado,
    0,
    0,
    LADO_FOTO,
    LADO_FOTO,
  );
  bitmap.close?.();
  return tela.toDataURL("image/jpeg", 0.82);
}

async function salvarPerfil() {
  // Só vai no corpo o que a pessoa realmente mexeu: campo ausente é
  // "não altera" para o servidor.
  const corpo = {};
  const nome = perfilNomeCampo.value.trim();
  if (nome) corpo.nome = nome;

  if (perfilSenhaNova.value) {
    corpo.senha_atual = perfilSenhaAtual.value;
    corpo.senha_nova = perfilSenhaNova.value;
  }

  if (fotoPendente === null) corpo.remover_foto = true;
  else if (typeof fotoPendente === "string") corpo.foto = fotoPendente;

  try {
    const dados = await api.salvarPerfil(corpo);
    guardado.salvarNome(dados.jogador.nome);
    preencherPerfil(dados);
    fotoPendente = undefined;
    perfilSenhaAtual.value = "";
    perfilSenhaNova.value = "";
    som.tocar("sucesso");
    avisarPerfil("Perfil salvo.", true);
  } catch (erro) {
    som.tocar("erro");
    avisarPerfil(erro.message);
  }
}

perfilArquivo.addEventListener("change", async () => {
  const arquivo = perfilArquivo.files?.[0];
  // Zera para que escolher o MESMO arquivo de novo dispare o evento.
  perfilArquivo.value = "";
  if (!arquivo) return;
  try {
    fotoPendente = await prepararFoto(arquivo);
    mostrarFoto(fotoPendente);
    avisarPerfil("Foto trocada. Clique em SALVAR para confirmar.", true);
  } catch {
    avisarPerfil("Não consegui ler essa imagem. Tente um PNG ou JPG.");
  }
});

perfilRemoverFoto.addEventListener("click", () => {
  fotoPendente = null;
  mostrarFoto(null);
  avisarPerfil("Foto removida. Clique em SALVAR para confirmar.", true);
});

perfilSalvar.addEventListener("click", salvarPerfil);

document.addEventListener("keydown", (evento) => {
  if (evento.key !== "Escape") return;
  [painelCodigo, painelConfig, painelPerfil, painelSaida].forEach((p) => {
    if (!p.hidden) fechar(p);
  });
});

// Clicar no fundo escuro fecha o painel.
[painelCodigo, painelConfig, painelPerfil, painelSaida].forEach((painel) => {
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

function pintarVolumeSom() {
  const volume = guardado.volumeSom();
  controleVolumeSom.value = String(volume);
  valorVolumeSom.textContent = `${volume}%`;
}
pintarVolumeSom();

botaoSom.addEventListener("click", () => {
  const ligado = !guardado.som();
  guardado.salvarSom(ligado);
  pintarSom();
  if (ligado) som.tocar("confirmar");
});

controleVolumeSom.addEventListener("input", () => {
  const volume = Number(controleVolumeSom.value);
  guardado.salvarVolumeSom(volume);
  valorVolumeSom.textContent = `${volume}%`;
});

controleVolumeSom.addEventListener("change", () => som.tocar("clique"));

function estaEmTelaCheia() {
  return window.roubodopolis?.desktop
    ? Boolean(window.roubodopolis.telaCheia?.())
    : Boolean(document.fullscreenElement);
}

function pintarTelaCheia() {
  modoExibicao.value = estaEmTelaCheia() ? "tela-cheia" : "janela";
}

async function aplicarModoExibicao() {
  const deveFicarEmTelaCheia = modoExibicao.value === "tela-cheia";
  try {
    if (window.roubodopolis?.desktop) {
      if (deveFicarEmTelaCheia !== estaEmTelaCheia()) {
        await window.roubodopolis.alternarTelaCheia();
      }
    } else if (deveFicarEmTelaCheia && !document.fullscreenElement) {
      await document.documentElement.requestFullscreen();
    } else if (!deveFicarEmTelaCheia && document.fullscreenElement) {
      await document.exitFullscreen();
    }
    pintarTelaCheia();
  } catch {
    pintarTelaCheia();
    toast("Não foi possível alterar o modo de exibição.", "erro");
  }
}

botaoAplicarModoExibicao.addEventListener("click", aplicarModoExibicao);
document.addEventListener("fullscreenchange", pintarTelaCheia);
window.roubodopolis?.aoMudarTelaCheia?.(pintarTelaCheia);
pintarTelaCheia();

// --- roteamento dos cliques ----------------------------------------

const acoes = {
  jogar,
  "abrir-codigo": () => abrir(painelCodigo),
  "entrar-codigo": entrarComCodigo,
  perfil: abrirPerfil,
  config: abrirConfiguracao,
  fechar: (elemento) => fechar(elemento.closest(".painel")),
  amigos: () => toast("AMIGOS ainda não foi construído. Em breve.", ""),
  loja: () => toast("A LOJA ainda não abriu. Em breve.", ""),
  sair: () => abrir(painelSaida),
  logout: () => {
    fechar(painelSaida);
    voltarAoLogin();
    toast("Você saiu da conta.", "ok");
  },
  "sair-jogo": () => {
    if (window.roubodopolis?.desktop) {
      window.roubodopolis.sairDoJogo();
      return;
    }
    window.close();
    toast("Feche esta aba para sair do jogo.", "");
  },
};

document.addEventListener("click", (evento) => {
  const alvo = evento.target.closest("[data-acao]");
  if (!alvo) return;
  const tipoSom = {
    "abrir-codigo": "confirmar",
    "entrar-codigo": "confirmar",
    perfil: "selecionar",
    config: "clique",
    fechar: "voltar",
    amigos: "clique",
    loja: "clique",
    sair: "voltar",
    logout: "voltar",
    "sair-jogo": "voltar",
  }[alvo.dataset.acao];
  if (tipoSom) som.tocar(tipoSom);
  acoes[alvo.dataset.acao]?.(alvo);
});

// Enter no nome já começa a partida; no código, entra na sala.
campoNome.addEventListener("keydown", (e) => e.key === "Enter" && jogar());
campoCodigo.addEventListener("keydown", (e) => e.key === "Enter" && entrarComCodigo());

if (guardado.token()) {
  api.quemSouEu?.().then(mostrarJogo).catch(() => guardado.esquecer());
}

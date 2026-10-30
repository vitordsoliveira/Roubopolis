/* Tela inicial: guarda o nome e cria (ou entra em) uma sala. */

import { api, guardado } from "../core/api.js";
import { musica } from "../core/musica.js";
import { som } from "../core/som.js";
import { elemento, inicial } from "../ui/comum.js";
import { acompanharNotificacoes, pararNotificacoes } from "../ui/notificacoes.js";
import { toast } from "../ui/toast.js";
import { previaDaCasa, previaDoDado, previaDoItem } from "../ui/vitrine.js";

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
const atalhoCoins = document.querySelector("#atalho-coins");
const rodapeMensagem = document.querySelector("#rodape-mensagem");
const botaoSom = document.querySelector("#som");
const botaoMusica = document.querySelector("#musica");
const botaoAnimacoes = document.querySelector("#animacoes");
const modoExibicao = document.querySelector("#modo-exibicao");
const controleVolumeSom = document.querySelector("#volume-som");
const valorVolumeSom = document.querySelector("#valor-volume-som");
const controleVolumeMusica = document.querySelector("#volume-musica");
const valorVolumeMusica = document.querySelector("#valor-volume-musica");
const perfilPartidas = document.querySelector("#perfil-partidas");
const perfilVitorias = document.querySelector("#perfil-vitorias");
const perfilTaxa = document.querySelector("#perfil-taxa");
const perfilAviso = document.querySelector("#perfil-aviso");
const perfilFoto = document.querySelector("#perfil-foto");
const perfilFotoVazia = document.querySelector("#perfil-foto-vazia");
const perfilArquivo = document.querySelector("#perfil-arquivo");
const perfilRemoverFoto = document.querySelector("#perfil-remover-foto");
const perfilNomeCampo = document.querySelector("#perfil-nome-campo");
const perfilLoginCampo = document.querySelector("#perfil-login-campo");
const perfilSenhaAtual = document.querySelector("#perfil-senha-atual");
const perfilSenhaNova = document.querySelector("#perfil-senha-nova");
const perfilSalvar = document.querySelector("#perfil-salvar");
const painelAmigos = document.querySelector("#painel-amigos");
const amigosMeuLogin = document.querySelector("#amigos-meu-login");
const amigosFormulario = document.querySelector("#amigos-formulario");
const amigosCampo = document.querySelector("#amigos-login");
const amigosAviso = document.querySelector("#amigos-aviso");
const amigosLista = document.querySelector("#amigos-lista");
const amigosRecebidos = document.querySelector("#amigos-recebidos");
const amigosEnviados = document.querySelector("#amigos-enviados");
const seloAmigos = document.querySelector("#selo-amigos");
const painelLoja = document.querySelector("#painel-loja");
const lojaCreditos = document.querySelector("#loja-creditos");
const lojaComo = document.querySelector("#loja-como");
const lojaAviso = document.querySelector("#loja-aviso");
const lojaItens = document.querySelector("#loja-itens");
const abasLoja = document.querySelectorAll("[data-loja-aba]");

const PAINEIS = () => [painelCodigo, painelConfig, painelPerfil, painelSaida, painelAmigos, painelLoja];

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
  if (jogador.coins !== undefined) atalhoCoins.textContent = `${Number(jogador.coins) || 0} CRÉDITOS`;
  atalhoInicial.textContent = (jogador.nome || "?").trim().charAt(0);
  atalhoFoto.src = temFoto ? jogador.foto : "";
  atalhoFoto.hidden = !temFoto;
  atalhoInicial.hidden = temFoto;
  atalhoPerfil.hidden = false;
}

function mostrarJogo(jogador) {
  document.querySelector(".menu__login").hidden = true;
  opcoes.hidden = false;
  pintarAtalho(jogador);
  // Convite de amigo e pedido de amizade aparecem em cartão no topo; cada
  // consulta também acerta o selo do AMIGOS.
  acompanharNotificacoes({ aoAtualizar: (dados) => pintarSelo(dados.pedidos.length) });
  // Foco no CONTÊINER, não no primeiro botão. Focar o botão acendia a
  // setinha do `:focus-visible` no JOGAR, que ficava parecendo uma seleção
  // travada e concorria com a setinha do mouse. Assim o leitor de tela
  // entra no menu e nada acende.
  opcoes.focus({ preventScroll: true });
}

function voltarAoLogin() {
  document.querySelectorAll(".painel:not([hidden])").forEach(fechar);
  pararNotificacoes();
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

async function comIndicador(tarefa, { logado = false } = {}) {
  if (ocupado) return;
  ocupado = true;
  opcoes.setAttribute("aria-busy", "true");
  try {
    await tarefa();
  } catch (erro) {
    som.tocar("erro");
    if (logado && erro.status === 401) {
      // O token guardado não vale mais (a conta entrou em outra máquina,
      // por exemplo): o caminho é entrar de novo. No login, 401 é só
      // senha errada — por isso o `logado`.
      voltarAoLogin();
      toast("Sua sessão expirou. Entre de novo.", "erro");
      return;
    }
    toast(erro.message, "erro");
  } finally {
    ocupado = false;
    opcoes.removeAttribute("aria-busy");
  }
}

/* JOGAR e o código usam a conta já logada (o token guardado) e não mandam
   nome nenhum. Antes os dois mandavam o nome do campo de cadastro, que só
   era preenchido ao abrir o menu: trocado o nome no perfil, o antigo
   voltava ao servidor na entrada da sala. */
function jogar() {
  return comIndicador(async () => {
    const sala = await api.criarSala();
    await new Promise((resolver) => setTimeout(resolver, 140));
    window.location.href = `/lobby?codigo=${sala.codigo}`;
  }, { logado: true });
}

function entrarComCodigo() {
  const codigo = campoCodigo.value.trim().toUpperCase();
  if (codigo.length < 4) {
    campoCodigo.classList.add("campo--erro");
    campoCodigo.focus();
    return;
  }
  return comIndicador(async () => {
    som.tocar("entrar");
    const sala = await api.entrarNaSala(codigo);
    window.location.href = `/lobby?codigo=${sala.codigo}`;
  }, { logado: true });
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
  if (painel === painelAmigos) pararAmigos();
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
  perfilLoginCampo.value = jogador.login || "";
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
  // Mandar o mesmo de agora não muda nada: o servidor só recusa o que já é
  // de outra pessoa.
  const login = perfilLoginCampo.value.trim();
  if (login) corpo.login = login;

  if (perfilSenhaNova.value) {
    corpo.senha_atual = perfilSenhaAtual.value;
    corpo.senha_nova = perfilSenhaNova.value;
  }

  if (fotoPendente === null) corpo.remover_foto = true;
  else if (typeof fotoPendente === "string") corpo.foto = fotoPendente;

  try {
    const dados = await api.salvarPerfil(corpo);
    // Atualiza o cache do navegador junto: é ele que desenha o menu na
    // próxima abertura, antes de qualquer consulta ao servidor.
    guardado.salvarSessao(dados.jogador);
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
  PAINEIS().forEach((p) => {
    if (!p.hidden) fechar(p);
  });
});

// Clicar no fundo escuro fecha o painel.
PAINEIS().forEach((painel) => {
  painel.addEventListener("click", (evento) => {
    if (evento.target === painel) fechar(painel);
  });
});

// --- amigos -------------------------------------------------------------

/* Amizade se pede pelo nome de usuário, que é único — o nome no jogo não
   serve, dois jogadores podem se chamar igual. A lista diz onde cada amigo
   está: numa partida (dá para assistir, sem jogar) ou num lobby (dá para
   entrar, se houver lugar). Enquanto o painel está aberto, ela se atualiza
   sozinha. */

const INTERVALO_AMIGOS_MS = 5000;
let consultaAmigos = null;

function avisarAmigos(mensagem, ok = false) {
  amigosAviso.textContent = mensagem;
  amigosAviso.hidden = !mensagem;
  amigosAviso.classList.toggle("perfil__aviso--ok", ok);
}

function pintarSelo(recebidos) {
  seloAmigos.hidden = recebidos === 0;
  seloAmigos.textContent = recebidos > 9 ? "9+" : String(recebidos);
}

function fotoDoAmigo(amigo) {
  const quadro = elemento("span", "amigo__foto");
  if (amigo.foto) {
    const img = elemento("img");
    img.src = amigo.foto;
    img.alt = "";
    quadro.appendChild(img);
  } else {
    quadro.textContent = inicial(amigo.nome);
  }
  return quadro;
}

function botaoPequeno(rotulo, classe, aoClicar) {
  const botao = elemento("button", `botao botao--pequeno ${classe}`, rotulo);
  botao.type = "button";
  botao.addEventListener("click", aoClicar);
  return botao;
}

function statusDoAmigo(amigo) {
  if (amigo.sala?.status === "em_partida") return ["Em partida", "amigo__status--partida"];
  if (amigo.sala?.status === "aguardando") return ["No lobby", "amigo__status--lobby"];
  return amigo.online ? ["Online", "amigo__status--online"] : ["Offline", ""];
}

function cartaoDeAmigo(amigo, { detalhe, acoes }) {
  const item = elemento("li", "amigo");
  const info = elemento("div", "amigo__info");
  info.append(elemento("span", "amigo__nome", amigo.nome), detalhe);
  const caixaAcoes = elemento("div", "amigo__acoes");
  caixaAcoes.append(...acoes);
  item.append(fotoDoAmigo(amigo), info, caixaAcoes);
  return item;
}

/** Amigo aceito: status, o dado e a casa que está usando, e o que dá para
    fazer agora. */
function itemDeAmigo(amigo) {
  const [rotulo, classe] = statusDoAmigo(amigo);
  const detalhe = elemento("span", "amigo__detalhe");
  const visual = elemento("span", "amigo__visual");
  visual.title = `Usando: dado ${amigo.visual?.dado?.nome || "Clássico"} e casa ${amigo.visual?.casa?.nome || "Da vila"}`;
  visual.append(previaDoDado(amigo.visual?.dado?.visual), previaDaCasa(amigo.visual?.casa?.visual));
  detalhe.append(elemento("span", `amigo__status ${classe}`, rotulo), elemento("span", "", `@${amigo.login || "?"}`), visual);

  const acoes = [];
  if (amigo.sala?.status === "em_partida") {
    acoes.push(botaoPequeno("Assistir", "botao--verde", () => {
      som.tocar("entrar");
      location.href = `/partida?codigo=${amigo.sala.codigo}`;
    }));
  } else if (amigo.sala?.status === "aguardando" && !amigo.sala.cheia) {
    acoes.push(botaoPequeno("Entrar na sala", "", () => entrarNaSalaDoAmigo(amigo.sala.codigo)));
  }
  acoes.push(botaoQueConfirma("Remover", () => desfazerAmizade(amigo)));
  return cartaoDeAmigo(amigo, { detalhe, acoes });
}

/** Desfazer amizade não tem volta: o primeiro clique só arma o botão
    ("Certeza?") e o segundo, em até 3 segundos, confirma. Sem caixa de
    diálogo do navegador — ela destoa do resto do jogo. */
let confirmando = false;

function botaoQueConfirma(rotulo, aoConfirmar) {
  let armado = null;
  const botao = botaoPequeno(rotulo, "botao--perigo", () => {
    if (armado) {
      clearTimeout(armado);
      confirmando = false;
      aoConfirmar();
      return;
    }
    som.tocar("aviso");
    botao.textContent = "Certeza?";
    confirmando = true;
    armado = setTimeout(() => {
      armado = null;
      confirmando = false;
      botao.textContent = rotulo;
    }, 3000);
  });
  return botao;
}

function pintarAmigos(painel) {
  amigosMeuLogin.textContent = painel.eu.login ? `@${painel.eu.login}` : "sem usuário";
  pintarSelo(painel.recebidos.length);

  amigosLista.replaceChildren(
    ...(painel.amigos.length
      ? painel.amigos.map(itemDeAmigo)
      : [elemento("li", "amigos__vazio", "Nenhum amigo ainda. Peça o usuário de alguém e adicione aqui.")]),
  );

  document.querySelector("#amigos-recebidos-secao").hidden = !painel.recebidos.length;
  amigosRecebidos.replaceChildren(...painel.recebidos.map((outro) => cartaoDeAmigo(outro, {
    detalhe: elemento("span", "amigo__detalhe", `@${outro.login || "?"} quer ser seu amigo`),
    acoes: [
      botaoPequeno("Aceitar", "botao--verde", () => aceitarAmizade(outro)),
      botaoPequeno("Recusar", "botao--perigo", () => desfazerAmizade(outro)),
    ],
  })));

  document.querySelector("#amigos-enviados-secao").hidden = !painel.enviados.length;
  amigosEnviados.replaceChildren(...painel.enviados.map((outro) => cartaoDeAmigo(outro, {
    detalhe: elemento("span", "amigo__detalhe", `@${outro.login || "?"} ainda não respondeu`),
    acoes: [botaoPequeno("Cancelar", "botao--roxo", () => desfazerAmizade(outro))],
  })));
}

async function carregarAmigos() {
  // Com um "Certeza?" armado, a lista não é redesenhada por baixo do clique.
  if (confirmando) return;
  try {
    pintarAmigos(await api.amigos());
  } catch (erro) {
    avisarAmigos(erro.message);
  }
}

function abrirAmigos() {
  abrir(painelAmigos);
  avisarAmigos("");
  carregarAmigos();
  pararAmigos();
  consultaAmigos = setInterval(() => !document.hidden && carregarAmigos(), INTERVALO_AMIGOS_MS);
}

function pararAmigos() {
  if (consultaAmigos) clearInterval(consultaAmigos);
  consultaAmigos = null;
}

/** Ação de amizade: manda, redesenha com a resposta e avisa. */
async function mexerNaAmizade(promessa, mensagemOk) {
  try {
    pintarAmigos(await promessa);
    if (mensagemOk) {
      som.tocar("sucesso");
      avisarAmigos(mensagemOk, true);
    }
  } catch (erro) {
    som.tocar("erro");
    avisarAmigos(erro.message);
  }
}

amigosFormulario.addEventListener("submit", (evento) => {
  evento.preventDefault();
  const login = amigosCampo.value.trim().replace(/^@/, "");
  if (!login) {
    amigosCampo.focus();
    return;
  }
  mexerNaAmizade(api.pedirAmizade(login), "Pedido enviado. Quando aceitar, aparece na sua lista.")
    .then(() => (amigosCampo.value = ""));
});

function aceitarAmizade(outro) {
  mexerNaAmizade(api.aceitarAmizade(outro.id), `Agora você e ${outro.nome} são amigos.`);
}

function desfazerAmizade(outro) {
  som.tocar("voltar");
  mexerNaAmizade(api.desfazerAmizade(outro.id), "");
}

async function entrarNaSalaDoAmigo(codigoDaSala) {
  try {
    som.tocar("entrar");
    const sala = await api.entrarNaSala(codigoDaSala);
    location.href = `/lobby?codigo=${sala.codigo}`;
  } catch (erro) {
    som.tocar("erro");
    avisarAmigos(erro.message);
  }
}

// --- loja ---------------------------------------------------------------

/* Dados e casas para a partida, pagos com os créditos que as partidas dão.
   O que está equipado entra na partida seguinte e aparece para a mesa
   inteira: o dado de quem rola na faixa do resultado, a casa nos terrenos
   de quem é dono. */

let abaDaLoja = "dado";
let vitrine = null;

function avisarLoja(mensagem, ok = false) {
  lojaAviso.textContent = mensagem;
  lojaAviso.hidden = !mensagem;
  lojaAviso.classList.toggle("perfil__aviso--ok", ok);
}

function itemDaLoja(item) {
  const cartao = elemento("li", `item-loja${item.equipado ? " item-loja--equipado" : ""}`);
  let botao;
  if (item.equipado) {
    botao = elemento("button", "botao botao--pequeno botao--verde", "Equipado");
    botao.disabled = true;
  } else if (item.meu) {
    botao = elemento("button", "botao botao--pequeno botao--roxo", "Equipar");
    botao.addEventListener("click", () => equipar(item));
  } else {
    const faltam = item.preco - vitrine.creditos;
    botao = elemento("button", "botao botao--pequeno", `Comprar · ${item.preco}`);
    botao.disabled = faltam > 0;
    botao.title = faltam > 0 ? `Faltam ${faltam} créditos` : "";
    botao.addEventListener("click", () => comprar(item));
  }
  botao.type = "button";
  cartao.append(
    previaDoItem(item),
    elemento("strong", "item-loja__nome", item.nome),
    elemento("span", "item-loja__descricao", item.descricao || ""),
    botao,
  );
  return cartao;
}

function pintarLoja(dados) {
  vitrine = dados;
  lojaCreditos.textContent = String(dados.creditos);
  lojaComo.textContent =
    `Cada vitória vale ${dados.recompensas.vitoria} créditos e cada partida até o fim, ${dados.recompensas.participacao}. `
    + "O que você equipar aparece para toda a mesa na próxima partida.";
  atalhoCoins.textContent = `${dados.creditos} CRÉDITOS`;
  abasLoja.forEach((aba) => {
    const ativa = aba.dataset.lojaAba === abaDaLoja;
    aba.classList.toggle("login__aba--ativa", ativa);
    aba.setAttribute("aria-selected", String(ativa));
  });
  lojaItens.replaceChildren(...dados.itens.filter((item) => item.tipo === abaDaLoja).map(itemDaLoja));
}

async function abrirLoja() {
  abrir(painelLoja);
  avisarLoja("");
  try {
    pintarLoja(await api.loja());
  } catch (erro) {
    avisarLoja(erro.message);
  }
}

async function comprar(item) {
  try {
    pintarLoja(await api.comprarItem(item.slug));
    som.tocar("caixa");
    avisarLoja(`${item.nome} é seu. Equipe para usar na próxima partida.`, true);
  } catch (erro) {
    som.tocar("erro");
    avisarLoja(erro.message);
  }
}

async function equipar(item) {
  try {
    pintarLoja(await api.equiparItem(item.slug));
    som.tocar("confirmar");
    avisarLoja(`${item.nome} equipado.`, true);
  } catch (erro) {
    som.tocar("erro");
    avisarLoja(erro.message);
  }
}

abasLoja.forEach((aba) => aba.addEventListener("click", () => {
  abaDaLoja = aba.dataset.lojaAba;
  som.tocar("selecionar");
  if (vitrine) pintarLoja(vitrine);
}));

// --- som e música ------------------------------------------------------

/* "Som" é o interruptor geral: desligado, cala efeitos E música. "Música"
   cala só a música. Os dois volumes ajustam cada um separado. */

musica.iniciar();

function pintarSom() {
  const ligado = guardado.som();
  botaoSom.setAttribute("aria-pressed", String(ligado));
  botaoSom.textContent = ligado ? "LIGADO" : "DESLIGADO";
}
pintarSom();

function pintarMusica() {
  const ligada = guardado.musica();
  botaoMusica.setAttribute("aria-pressed", String(ligada));
  botaoMusica.textContent = ligada ? "LIGADA" : "DESLIGADA";
}
pintarMusica();

function aplicarAnimacoes(ligadas) {
  document.documentElement.classList.toggle("sem-animacao", !ligadas);
  window.dispatchEvent(new Event("roubopolis:animacoes"));
}

function pintarAnimacoes() {
  const ligadas = guardado.animacoes();
  botaoAnimacoes.setAttribute("aria-pressed", String(ligadas));
  botaoAnimacoes.textContent = ligadas ? "LIGADAS" : "DESLIGADAS";
  aplicarAnimacoes(ligadas);
}

pintarAnimacoes();

function pintarVolumeSom() {
  const volume = guardado.volumeSom();
  controleVolumeSom.value = String(volume);
  valorVolumeSom.textContent = `${volume}%`;
}
pintarVolumeSom();

function pintarVolumeMusica() {
  const volume = guardado.volumeMusica();
  controleVolumeMusica.value = String(volume);
  valorVolumeMusica.textContent = `${volume}%`;
}
pintarVolumeMusica();

botaoSom.addEventListener("click", () => {
  const ligado = !guardado.som();
  guardado.salvarSom(ligado);
  pintarSom();
  musica.atualizarVolume();
  if (ligado) som.tocar("confirmar");
});

botaoMusica.addEventListener("click", () => {
  guardado.salvarMusica(!guardado.musica());
  pintarMusica();
  musica.atualizarVolume();
  som.tocar("clique");
});

controleVolumeMusica.addEventListener("input", () => {
  const volume = Number(controleVolumeMusica.value);
  guardado.salvarVolumeMusica(volume);
  valorVolumeMusica.textContent = `${volume}%`;
  musica.atualizarVolume();
});

botaoAnimacoes.addEventListener("click", () => {
  const ligadas = !guardado.animacoes();
  guardado.salvarAnimacoes(ligadas);
  pintarAnimacoes();
  som.tocar("clique");
});

controleVolumeSom.addEventListener("input", () => {
  const volume = Number(controleVolumeSom.value);
  guardado.salvarVolumeSom(volume);
  valorVolumeSom.textContent = `${volume}%`;
});

controleVolumeSom.addEventListener("change", () => som.tocar("clique"));

/* O Roubopolis é jogado pelo aplicativo instalado — a página nunca é o
   produto final. Tudo que depende da janela passa por esta ponte, e a
   ausência dela é DEFEITO, não um segundo modo de uso. Ter um caminho
   alternativo aqui só serviria para esconder o defeito. */

function ponteDesktop() {
  return window.roubodopolis?.desktop ? window.roubodopolis : null;
}

function avisarSemPonte() {
  toast("Não consegui falar com o aplicativo. Abra o jogo pelo Roubopolis, não pelo navegador.", "erro");
}

function estaEmTelaCheia() {
  return Boolean(ponteDesktop()?.telaCheia?.());
}

function pintarTelaCheia() {
  modoExibicao.value = estaEmTelaCheia() ? "tela-cheia" : "janela";
}

async function aplicarModoExibicao() {
  const desktop = ponteDesktop();
  if (!desktop) {
    // Antes caía em document.requestFullscreen(), que no Electron até
    // funciona — mas é o fullscreen do HTML, e não o da janela nativa.
    // O seletor e a janela real passavam a discordar em silêncio.
    avisarSemPonte();
    return;
  }

  const deveFicarEmTelaCheia = modoExibicao.value === "tela-cheia";
  try {
    if (deveFicarEmTelaCheia !== estaEmTelaCheia()) {
      await desktop.alternarTelaCheia();
    }
    pintarTelaCheia();
  } catch {
    pintarTelaCheia();
    toast("Não foi possível alterar o modo de exibição.", "erro");
  }
}

// Vale na hora, como o resto da configuração: não há botão de aplicar.
modoExibicao.addEventListener("change", () => {
  som.tocar("confirmar");
  aplicarModoExibicao();
});
// Quem avisa que a janela mudou é o processo do Electron (F11 inclusive),
// não o evento `fullscreenchange` do HTML.
ponteDesktop()?.aoMudarTelaCheia?.(pintarTelaCheia);
pintarTelaCheia();

// --- roteamento dos cliques ----------------------------------------

const acoes = {
  jogar,
  "abrir-codigo": () => abrir(painelCodigo),
  "entrar-codigo": entrarComCodigo,
  perfil: abrirPerfil,
  config: abrirConfiguracao,
  fechar: (alvo) => fechar(alvo.closest(".painel")),
  amigos: abrirAmigos,
  loja: abrirLoja,
  sair: () => abrir(painelSaida),
  logout: () => {
    fechar(painelSaida);
    voltarAoLogin();
    toast("Você saiu da conta.", "ok");
  },
  "sair-jogo": () => {
    const desktop = ponteDesktop();
    if (desktop) {
      desktop.sairDoJogo();
      return;
    }
    // Antes caía num `window.close()` que o navegador ignora em silêncio,
    // e o botão parecia simplesmente quebrado.
    avisarSemPonte();
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

// Enter no nome do cadastro cria a conta; no código, entra na sala.
campoNome.addEventListener("keydown", (e) => e.key === "Enter" && acessar());
campoCodigo.addEventListener("keydown", (e) => e.key === "Enter" && entrarComCodigo());

/* Entrada da tela.

   Antes esta decisão esperava a resposta do `GET /api/jogador`, e nessa ida
   e volta pela rede a tela de login aparecia para quem já estava logado —
   o "pisca" ao voltar do lobby. Pior: a troca de DOM acontecia com o cursor
   parado, e o Chromium não reavalia `:hover` nesse caso, então as opções
   ficavam sem realce até o primeiro clique.

   Agora o que está guardado no navegador pinta na hora, antes de qualquer
   rede, e o servidor apenas confirma depois. */

if (guardado.token()) {
  mostrarJogo({ nome: guardado.nome(), foto: guardado.foto() });

  api.quemSouEu()
    .then((jogador) => {
      // O servidor é a verdade: corrige nome/foto se mudaram em outra máquina.
      guardado.salvarSessao(jogador);
      pintarAtalho(jogador);
    })
    .catch((erro) => {
      // Só derruba a sessão se o servidor DISSE que o token não vale mais.
      // Rede fora do ar não pode deslogar quem estava logado.
      if (erro.status === 401) {
        guardado.esquecer();
        voltarAoLogin();
        toast("Sua sessão expirou. Entre de novo.", "erro");
      }
    });
}

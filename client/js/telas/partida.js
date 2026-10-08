/* Partida: o tabuleiro isométrico, com o servidor mandando e a tela só
   contando a história.

  A tela encena o sorteio, a rolagem, o movimento e a compra de terrenos;
  aluguel e efeitos das casas ainda não estão ativos.

   A ordem importa. Quando alguém rola, o servidor JÁ resolveu tudo; o que
   a tela faz depois é encenar na sequência certa: o dado tomba, assenta, o
   peão pula casa por casa, e só então o estado novo entra. Aplicar o estado
   antes disso é o que fazia a partida parecer uma planilha se atualizando. */

import { api, guardado } from "../core/api.js";
import { som } from "../core/som.js";
import { montarChat } from "../ui/chat.js";
import { toast } from "../ui/toast.js";
import { itensDaLegenda, montarTabuleiro } from "../tabuleiro/render.js";
import { iconePixel } from "../tabuleiro/pixel.js";

const elTabuleiro = document.querySelector("#tabuleiro");
const elSvg = document.querySelector("#tabuleiro-svg");
const elPeoes = document.querySelector("#peoes");
const elInicio = document.querySelector("#inicio-marcador");
const elJogadores = document.querySelector("#jogadores");
const elLegenda = document.querySelector("#legenda");
const elAviso = document.querySelector("#aviso");
const elSoma = document.querySelector("#dados-soma");
const elDados = document.querySelector("#dados");
const elAnuncio = document.querySelector("#anuncio");
const elAnuncioTexto = document.querySelector("#anuncio-texto");
const elAnuncioDados = document.querySelector("#anuncio-dados");
const elAnuncioDadosQuem = document.querySelector("#anuncio-dados-quem");
const elAnuncioDadosSoma = document.querySelector("#anuncio-dados-soma");
const cubosGrandes = [document.querySelector("#cubo-grande-a"), document.querySelector("#cubo-grande-b")];
const botaoJogar = document.querySelector("#jogar");
const cubos = [document.querySelector("#cubo-a"), document.querySelector("#cubo-b")];
const dadosEl = [document.querySelector("#dado-a"), document.querySelector("#dado-b")];
const modalOrdem = document.querySelector("#modal-ordem");
const modalCompra = document.querySelector("#modal-compra");
const tituloCompra = document.querySelector("#compra-titulo");
const precoCompra = document.querySelector("#compra-preco");
const saldoCompra = document.querySelector("#compra-saldo");
const tempoCompra = document.querySelector("#compra-tempo");
const botoesCompra = [document.querySelector("#compra-nao"), document.querySelector("#compra-sim")];
const painelConfigPartida = document.querySelector("#painel-config-partida");
const botaoAnimacoesPartida = document.querySelector("#animacoes-partida");
const painelChat = document.querySelector("#chat");
const botaoChat = document.querySelector("#chat-abrir");
const contadorChat = document.querySelector("#chat-contador");
const campoChat = document.querySelector("#chat-texto");
const listaChat = document.querySelector("#chat-mensagens");

const CORES_RESERVA = ["#e94f37", "#7cb342", "#a855f7", "#ffd83d", "#2563c9", "#c9a227"];

function aplicarPreferenciaAnimacoes() {
  document.documentElement.classList.toggle("sem-animacao", !guardado.animacoes());
  window.dispatchEvent(new Event("roubopolis:animacoes"));
}

function pintarPreferenciaAnimacoes() {
  const ligadas = guardado.animacoes();
  botaoAnimacoesPartida.setAttribute("aria-pressed", String(ligadas));
  botaoAnimacoesPartida.textContent = ligadas ? "LIGADAS" : "DESLIGADAS";
  aplicarPreferenciaAnimacoes();
}

pintarPreferenciaAnimacoes();

/* --- ritmo da partida -------------------------------------------------

   Um botão só para o jogo inteiro: 1 é o ritmo normal, 1.5 deixa tudo 50%
   mais lento, 0.8 acelera. Todo tempo de animação sai daqui, então dá para
   calibrar a partida inteira mexendo em um número.

   Por que devagar: o jogador precisa conseguir contar o que aconteceu —
   quanto deu no dado, para onde o boneco foi, em que casa parou. Rápido
   demais vira borrão e ninguém acompanha. */

const RITMO = 1;
const ms = (base) => Math.round(base * RITMO);

/** Tempo de UMA casa: o passo do peão. É também a duração da animação do
    salto no CSS — ver `aplicarRitmo()`, que grava o valor no tabuleiro
    para os dois nunca discordarem. */
const MS_POR_CASA = ms(330);
/** Do arremesso até o dado assentar. */
const MS_ARREMESSO = ms(1150);
/** Os dados grandes da faixa girando até assentar. Um pouco menos que o
    arremesso: o total só bate com eles já parados. */
const MS_GIRO_GRANDE = ms(1050);
/** A faixa do resultado entrando ou saindo da tela. */
const MS_DESLIZE_FAIXA = ms(320);
/** Respiro depois da soma aparecer, para dar tempo de LER antes de andar. */
const MS_LER_RESULTADO = ms(1200);
/** Pausa depois que o peão pousa, antes do estado novo entrar. */
const MS_APOS_CHEGAR = ms(650);
/** Quanto a frase "fulano tirou 7 e parou em Moema" fica embaixo do JOGAR. */
const MS_RESUMO_DA_JOGADA = ms(4500);

/** Para mostrar a face N, quanto o cubo precisa girar. */
const FACES = { 1: [0, 0], 2: [0, -90], 3: [-90, 0], 4: [90, 0], 5: [0, 90], 6: [0, 180] };

const codigo = new URLSearchParams(location.search).get("codigo")?.toUpperCase() || "";

let tabuleiro = null;
/** O que `montarTabuleiro` devolveu: onde fica cada casa na tela. */
let desenho = null;
let estado = null;
let prazoLocalMs = null;
let consulta = null;
let ocupado = false;
let ordemMostrada = false;
let ultimaVez = null;
let voltasDoDado = 0;
/** Último lance já encenado nesta tela. Evita repetir a jogada de alguém. */
let ultimoLanceVisto = 0;
/** Quem está no tabuleiro agora — usado para saber quando remontar os peões. */
let assinaturaDosPeoes = "";
/** Quem está nos cartões — idem, para os cartões. */
let assinaturaDosCartoes = "";
let assinaturaDasPropriedades = "";
/** Impede duas consultas em voo ao mesmo tempo, que voltariam fora de ordem. */
let consultando = false;
/** A última jogada, contada embaixo do JOGAR por alguns segundos. */
let resumo = null;
/** Mensagens de outros que chegaram com o chat fechado. */
let naoLidas = 0;

// O mesmo chat do lobby, com o nome de cada um na cor do peão dele.
const chat = montarChat({
  codigo,
  lista: listaChat,
  formulario: document.querySelector("#chat-formulario"),
  campo: campoChat,
  status: document.querySelector("#chat-status"),
  corDe: (jogadorId) => {
    const i = estado?.jogadores.findIndex((j) => j.jogador_id === jogadorId) ?? -1;
    return i >= 0 ? corDoJogador(estado.jogadores[i], i) : null;
  },
  aoChegar: avisarMensagens,
});

preencherIcones();

if (!codigo || !guardado.token()) {
  toast("Volte ao menu e entre numa sala.", "erro");
  setTimeout(() => (location.href = "/"), 1400);
} else {
  montarDados();
  abrirChat(guardado.chatAberto(), { lembrar: false });
  abrir();
}

async function abrir() {
  try {
    aplicar(await api.verPartida(codigo));
    await chat.atualizar();
    iniciarConsulta();
  } catch (erro) {
    toast(erro.message, "erro");
    setTimeout(() => (location.href = `/lobby?codigo=${codigo}`), 1600);
  }
}

// --- utilidades -------------------------------------------------------

const espera = (duracao) => new Promise((resolver) => setTimeout(resolver, guardado.animacoes() ? duracao : 0));
const reais = (v) => "R$ " + Number(v || 0).toLocaleString("pt-BR");
const inicial = (n) => (n || "?").trim().charAt(0).toUpperCase();

function elemento(tag, classe, texto) {
  const el = document.createElement(tag);
  if (classe) el.className = classe;
  if (texto !== undefined) el.textContent = texto;
  return el;
}

function corDoJogador(jogador, i) {
  return jogador.personagem?.cor || CORES_RESERVA[i % CORES_RESERVA.length];
}

/** Os ícones de pixel art do HUD entram onde o HTML marcou `data-icone`. */
function preencherIcones() {
  for (const lugar of document.querySelectorAll("[data-icone]")) {
    lugar.replaceChildren(iconePixel(lugar.dataset.icone));
  }
}

// --- dados ------------------------------------------------------------

/** As seis faces de um cubo, com os pontos de cada valor. */
function criarFaces() {
  return [1, 2, 3, 4, 5, 6].map((valor) => {
    const face = elemento("div", `dado__face dado__face--${valor}`);
    face.dataset.valor = String(valor);
    for (let p = 0; p < valor; p += 1) face.appendChild(elemento("span", "dado__ponto"));
    return face;
  });
}

/** Gira o cubo até a face pedida. As voltas inteiras são só para tombar. */
function girarCubo(cubo, valor, voltas = 2) {
  const [rx, ry] = FACES[valor] || FACES[1];
  cubo.style.transform =
    `rotateX(${rx + 360 * voltas}deg) rotateY(${ry + 360 * voltas}deg)`;
}

function montarDados() {
  for (const cubo of [...cubos, ...cubosGrandes]) cubo.replaceChildren(...criarFaces());
  mostrarDados([5, 6], { girar: false });
}

function mostrarDados(valores, { girar = true } = {}) {
  if (girar) voltasDoDado += 2;
  valores.forEach((valor, i) => girarCubo(cubos[i], valor, voltasDoDado));
}

/** Joga os dois dados: eles caem de cima, quicam e assentam no valor. */
function arremessar(valores) {
  mostrarDados(valores);
  for (const dado of dadosEl) {
    dado.classList.remove("dado--arremesso");
    void dado.offsetWidth; // reinicia a animação
    dado.classList.add("dado--arremesso");
  }
}

/** A soma, acima dos dados: "3 + 4" pequeno e o total grande embaixo. */
function mostrarSoma(valores) {
  elSoma.replaceChildren(
    elemento("span", "dados__soma-parcelas", valores.join("  +  ")),
    elemento("span", "dados__soma-total", String(valores.reduce((a, b) => a + b, 0))),
  );
  elSoma.classList.remove("dados__soma--novo");
  void elSoma.offsetWidth;
  elSoma.classList.add("dados__soma--novo");
}

function limparSoma() {
  elSoma.classList.remove("dados__soma--novo");
  elSoma.replaceChildren();
}

/* A rolagem inteira, igual para quem rolou e para quem assiste.

   Os dados pequenos no canto do tabuleiro ficam com o último valor, como
   lembrete. O que a mesa LÊ é a faixa: atravessa a tela como o anúncio da
   vez, com os dados grandes girando no meio; eles assentam, o total bate,
   e a faixa sai antes do peão andar — senão cobriria o caminho dele. */
async function encenarDados(quem, valores, { meu = false } = {}) {
  arremessar(valores);
  som.tocar("selecionar");

  // Sem animação a faixa não tem o que mostrar: os dados pequenos e a
  // soma já contam o resultado.
  const comFaixa = guardado.animacoes();
  if (comFaixa) entrarFaixaDosDados(quem, valores);

  await espera(MS_ARREMESSO);
  mostrarSoma(valores);
  if (comFaixa) elAnuncioDados.classList.add("anuncio-dados--revelado");
  if (meu) som.tocar("confirmar");
  await espera(MS_LER_RESULTADO);

  if (!comFaixa) return;
  elAnuncioDados.classList.replace("anuncio-dados--dentro", "anuncio-dados--saindo");
  await espera(MS_DESLIZE_FAIXA);
  // O estado de repouso não tem transição: volta para a esquerda sem
  // atravessar a tela de novo.
  elAnuncioDados.classList.remove("anuncio-dados--saindo", "anuncio-dados--revelado");
}

function entrarFaixaDosDados(quem, valores) {
  elAnuncioDadosQuem.textContent = quem;
  elAnuncioDadosSoma.replaceChildren(
    elemento("span", "dados__soma-parcelas", valores.join("  +  ")),
    elemento("span", "dados__soma-total", String(valores.reduce((a, b) => a + b, 0))),
  );
  elAnuncioDados.classList.remove("anuncio-dados--dentro", "anuncio-dados--saindo", "anuncio-dados--revelado");

  // Os cubos voltam à pose de repouso sem transição, para tombarem as
  // mesmas três voltas toda vez em vez de só o que falta da rolagem anterior.
  for (const cubo of cubosGrandes) {
    cubo.style.transition = "none";
    cubo.style.transform = "";
  }
  void elAnuncioDados.offsetWidth;
  for (const cubo of cubosGrandes) cubo.style.transition = "";

  elAnuncioDados.classList.add("anuncio-dados--dentro");
  valores.forEach((valor, i) => girarCubo(cubosGrandes[i], valor, 3));
}

// --- tabuleiro (desenhado uma vez) ------------------------------------

function assinaturaPropriedades(propriedades = {}) {
  return Object.entries(propriedades)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([indice, propriedade]) => `${indice}:${propriedade.dono}`)
    .join("|");
}

function desenharTabuleiro(dados, propriedades = {}) {
  desenho = montarTabuleiro(elSvg, dados, propriedades);
  assinaturaDasPropriedades = assinaturaPropriedades(propriedades);
  const inicio = desenho.pontoInicio();
  elInicio.style.setProperty("--inicio-x", `${inicio.x}%`);
  elInicio.style.setProperty("--inicio-y", `${inicio.y}%`);
  // O quadro do tabuleiro tem a proporção do desenho: é isso que faz a
  // porcentagem de um peão cair exatamente em cima da casa certa. Vai na
  // mesa, que usa o número para o próprio tamanho, e o tabuleiro herda.
  elTabuleiro.parentElement.style.setProperty("--proporcao", desenho.proporcao.toFixed(4));

  aplicarRitmo();
  montarLegenda(dados);
}

function montarLegenda(dados) {
  elLegenda.replaceChildren(
    ...itensDaLegenda(dados).map(({ rotulo, cor }) => {
      const item = elemento("li", "legenda__item");
      const amostra = elemento("span", "legenda__cor");
      amostra.style.setProperty("--cor", cor);
      item.append(amostra, elemento("span", "", rotulo));
      return item;
    }),
  );
}

/* O CSS anima o salto e o JS espera entre as casas. Se os dois tempos
   discordarem, o peão é arrancado para a casa seguinte antes de pousar e
   parece deslizar em vez de andar. Uma fonte da verdade só: o JS grava o
   valor. */
function aplicarRitmo() {
  elTabuleiro.style.setProperty("--ms-passo", `${MS_POR_CASA}ms`);
  elAnuncioDados.style.setProperty("--ms-giro", `${MS_GIRO_GRANDE}ms`);
  elAnuncioDados.style.setProperty("--ms-deslize", `${MS_DESLIZE_FAIXA}ms`);
}

// --- peões -------------------------------------------------------------

/** Quem ainda está na mesa. Quem abandonou some do tabuleiro. */
function ativos() {
  return estado.jogadores.filter((j) => !j.falido);
}

function montarPeoes() {
  // O índice vem da lista COMPLETA: assim a cor e o lugar na casa de cada
  // jogador não mudam quando alguém sai.
  const itens = estado.jogadores.flatMap((jogador, i) => {
    if (jogador.falido) return [];

    const peao = elemento("div", "peao");
    peao.dataset.jogador = String(jogador.jogador_id);
    peao.dataset.assento = String(i);
    // A cor fica no peão inteiro: a base herda dela.
    peao.style.setProperty("--cor-peao", corDoJogador(jogador, i));

    peao.append(elemento("div", "peao__sombra"), elemento("div", "peao__base"));

    // Daqui para cima tudo fica em pé.
    const pino = elemento("div", "peao__pino");
    if (jogador.personagem?.sprite) {
      const img = elemento("img", "peao__figura");
      img.src = jogador.personagem.sprite;
      img.alt = jogador.nome;
      pino.appendChild(img);
    } else {
      pino.appendChild(elemento("div", "peao__ficha", inicial(jogador.nome)));
    }

    peao.appendChild(pino);
    return [peao];
  });
  elPeoes.replaceChildren(...itens);
  assinaturaDosPeoes = ativos().map((j) => j.jogador_id).join(",");
  posicionarPeoes();
}

function peaoDe(jogadorId) {
  return elPeoes.querySelector(`.peao[data-jogador="${jogadorId}"]`);
}

function posicionarPeoes() {
  estado.jogadores.forEach((jogador) => {
    const peao = peaoDe(jogador.jogador_id);
    if (!peao) return;
    colocarPeao(peao, jogador.posicao);
    peao.classList.toggle("peao--da-vez", jogador.jogador_id === estado.vez.jogador_id);
  });
}

function colocarPeao(peao, indice) {
  const { x, y } = desenho.ponto(indice, Number(peao.dataset.assento || 0));
  peao.style.setProperty("--px", `${x}%`);
  peao.style.setProperty("--py", `${y}%`);
  // Quem está mais embaixo na tela está mais perto: passa na frente.
  peao.style.zIndex = String(Math.round(y * 10));
}

/** Põe o peão numa casa SEM deslizar — para prepará-lo antes de encenar. */
function teleportarPeao(peao, indice) {
  peao.style.transition = "none";
  colocarPeao(peao, indice);
  void peao.offsetWidth;
  peao.style.transition = "";
}

/** Pula de casa em casa até o destino. */
async function andarPeao({ jogador_id, de, passos }) {
  const peao = peaoDe(jogador_id);
  if (!peao || !tabuleiro) return;

  const total = tabuleiro.casas.length;
  if (!guardado.animacoes()) {
    colocarPeao(peao, (de - (passos % total) + total) % total);
    peao.classList.remove("peao--andando");
    desenho.destacar((de - (passos % total) + total) % total);
    return;
  }

  for (let passo = 1; passo <= passos; passo += 1) {
    colocarPeao(peao, (de - (passo % total) + total) % total);
    peao.classList.remove("peao--andando");
    void peao.offsetWidth; // reinicia a animação do salto
    peao.classList.add("peao--andando");
    som.tocar("clique");
    await espera(MS_POR_CASA);
  }
  peao.classList.remove("peao--andando");
  desenho.destacar((de - (passos % total) + total) % total);
}

// --- cartões dos jogadores ----------------------------------------------

/* Um jogador em cada canto, na ordem de jogada: o primeiro em cima à
   esquerda, o segundo em cima à direita, depois os de baixo. Os cartões
   nascem uma vez e só têm o conteúdo trocado — recriar a cada consulta
   fazia os retratos piscarem. */

function montarCartoes() {
  const itens = estado.jogadores.map((jogador, i) => {
    const cartao = elemento("li", `cartao cartao--${i}`);
    cartao.dataset.jogador = String(jogador.jogador_id);
    cartao.style.setProperty("--cor-jogador", corDoJogador(jogador, i));

    const retrato = elemento("div", "cartao__retrato moldura");
    if (jogador.personagem?.sprite) {
      const img = elemento("img");
      img.src = jogador.personagem.sprite;
      img.alt = "";
      retrato.appendChild(img);
    } else {
      retrato.appendChild(elemento("span", "cartao__inicial", inicial(jogador.nome)));
    }

    const nome = elemento("div", "cartao__nome");
    nome.append(
      elemento("span", "cartao__ordem", `${i + 1}º`),
      elemento("span", "cartao__texto", jogador.nome),
      elemento("span", "cartao__eu", "você"),
    );

    const caixa = elemento("div", "cartao__caixa");
    const dinheiro = elemento("img", "cartao__dinheiro");
    dinheiro.src = "/assets/objetos/dinheiro.png";
    dinheiro.alt = "";
    caixa.append(elemento("span", "cartao__valor"), dinheiro);

    const corpo = elemento("div", "cartao__corpo moldura");
    corpo.append(nome, caixa);

    cartao.append(retrato, corpo);
    return cartao;
  });
  elJogadores.replaceChildren(...itens);
  assinaturaDosCartoes = estado.jogadores.map((j) => j.jogador_id).join(",");
}

function pintarCartoes() {
  const agora = estado.jogadores.map((j) => j.jogador_id).join(",");
  if (agora !== assinaturaDosCartoes) montarCartoes();

  for (const jogador of estado.jogadores) {
    const cartao = elJogadores.querySelector(`.cartao[data-jogador="${jogador.jogador_id}"]`);
    if (!cartao) continue;
    cartao.classList.toggle("cartao--da-vez", jogador.jogador_id === estado.vez.jogador_id && estado.fase !== "encerrada");
    cartao.classList.toggle("cartao--eu", jogador.sou_eu);
    cartao.classList.toggle("cartao--fora", jogador.falido);
    cartao.querySelector(".cartao__valor").textContent = jogador.falido ? "SAIU" : reais(jogador.caixa);
  }
}

// --- botão JOGAR ----------------------------------------------------------

function pintarJogar() {
  const minha = estado.vez.sou_eu;
  const podeRolar = minha && estado.fase === "aguardando_rolagem";
  botaoJogar.disabled = !podeRolar || ocupado;
  document.querySelector(".jogar").classList.toggle("jogar--minha-vez", podeRolar && !ocupado);

  let mensagem;
  if (resumo && Date.now() < resumo.ate) {
    mensagem = resumo.texto;
  } else if (estado.fase === "encerrada") {
    resumo = null;
    const vencedor = ativos()[0];
    mensagem = vencedor ? `A partida acabou — ${vencedor.nome} ficou sozinho.` : "A partida acabou.";
  } else if (estado.fase === "decidindo_compra") {
    resumo = null;
    mensagem = minha ? "Escolha se deseja comprar o terreno" : `${estado.vez.nome} está decidindo uma compra`;
  } else {
    resumo = null;
    mensagem = podeRolar ? "Role os dados e faça sua jogada" : `Esperando ${estado.vez.nome} jogar`;
  }

  const restante = segundosRestantes();
  if (restante !== null && estado.fase !== "encerrada" && estado.fase !== "sorteio_ordem") {
    mensagem += ` · ${formatarTempo(restante)}`;
  }
  elAviso.textContent = mensagem;
}

function segundosRestantes() {
  if (prazoLocalMs == null) return null;
  return Math.max(0, Math.ceil((prazoLocalMs - performance.now()) / 1000));
}

function formatarTempo(segundos) {
  const minutos = Math.floor(segundos / 60);
  const resto = segundos % 60;
  return `${String(minutos).padStart(2, "0")}:${String(resto).padStart(2, "0")}`;
}

/** O que o servidor contou da última rolagem vira o aviso por uns segundos. */
function contarJogada(movimento) {
  const linha = [...estado.log].reverse().find((l) => l.tipo === "dado" && l.jogador_id === movimento.jogador_id);
  if (!linha) return;
  resumo = { texto: linha.texto.replace(/\.$/, ""), ate: Date.now() + MS_RESUMO_DA_JOGADA };
  pintarJogar();
  setTimeout(() => estado && pintarJogar(), MS_RESUMO_DA_JOGADA + 50);
}

// --- efeitos -----------------------------------------------------------

/** Quem estava jogando e não está mais: o resto da mesa precisa saber. */
function avisarQuemSaiu(antes) {
  for (const jogador of estado.jogadores) {
    const estava = antes.jogadores.find((j) => j.jogador_id === jogador.jogador_id);
    if (!estava || estava.falido || !jogador.falido) continue;
    som.tocar("aviso");
    toast(`${jogador.nome} saiu da partida.`, "erro");
  }
}

function anunciarVez() {
  if (estado.fase === "encerrada" || estado.vez.jogador_id === ultimaVez) return;
  // Com o sorteio aberto o anúncio passaria por baixo da cortina; quem
  // fecha o sorteio chama de novo.
  if (!modalOrdem.hidden) return;
  ultimaVez = estado.vez.jogador_id;
  elAnuncioTexto.textContent = estado.vez.sou_eu ? "Sua vez!" : `Vez de ${estado.vez.nome}`;
  elAnuncio.classList.remove("anuncio--passando");
  void elAnuncio.offsetWidth;
  elAnuncio.classList.add("anuncio--passando");
}

// --- aplicar estado -----------------------------------------------------

function aplicar(resposta) {
  const primeiraVez = !tabuleiro;
  const antes = estado;
  estado = resposta.partida;
  prazoLocalMs = estado.segundos_restantes == null
    ? null
    : performance.now() + estado.segundos_restantes * 1000;
  if (primeiraVez) {
    tabuleiro = resposta.tabuleiro;
    desenharTabuleiro(tabuleiro, estado.propriedades);
  } else if (assinaturaPropriedades(estado.propriedades) !== assinaturaDasPropriedades) {
    desenho.atualizarPropriedades(estado.propriedades);
    assinaturaDasPropriedades = assinaturaPropriedades(estado.propriedades);
  }

  // Na primeira pintura, o lance que já estava no estado não é encenado:
  // seria repetir uma jogada que aconteceu antes de eu abrir a tela.
  if (primeiraVez) ultimoLanceVisto = estado.ultimo_movimento?.lance ?? 0;

  // Remonta os peões quando alguém entra ou sai da mesa.
  const agora = ativos().map((j) => j.jogador_id).join(",");
  if (primeiraVez || agora !== assinaturaDosPeoes) montarPeoes();
  if (antes) avisarQuemSaiu(antes);

  posicionarPeoes();
  pintarCartoes();
  pintarJogar();
  atualizarModalCompra();

  if (!ordemMostrada && estado.sorteio?.length) mostrarOrdem();
  anunciarVez();
}

function atualizarModalCompra() {
  const pendente = estado?.fase === "decidindo_compra" ? estado.compra_pendente : null;
  const minhaDecisao = Boolean(pendente && estado.vez.sou_eu);
  modalCompra.hidden = !minhaDecisao;
  if (!minhaDecisao) return;

  const casa = tabuleiro.casas[pendente.casa];
  const eu = estado.jogadores.find((jogador) => jogador.sou_eu);
  tituloCompra.textContent = casa?.nome || "Terreno";
  precoCompra.textContent = `Preço: ${reais(pendente.preco)}`;
  saldoCompra.textContent = `Seu caixa: ${reais(eu?.caixa)} · após comprar: ${reais((eu?.caixa || 0) - pendente.preco)}`;
  const restante = segundosRestantes();
  tempoCompra.textContent = restante === null ? "Sem limite de tempo" : `Tempo para decidir: ${formatarTempo(restante)}`;
}

setInterval(() => {
  if (!estado) return;
  pintarJogar();
  if (!modalCompra.hidden) atualizarModalCompra();
}, 1000);

/* Encena o lance de OUTRO jogador.

   Quem rola vê a cena ao vivo; quem assiste recebia só o estado final e o
   peão aparecia no destino, como teletransporte. Aqui a tela reproduz a
   mesma sequência — dado tomba, soma bate, peão anda — a partir do que o
   servidor contou. */
async function encenarLanceDeOutro(resposta) {
  const movimento = resposta.partida.ultimo_movimento;
  if (!movimento || movimento.lance <= ultimoLanceVisto) return false;

  ultimoLanceVisto = movimento.lance;

  // Se fui eu que rolei, já vi acontecer.
  const eu = resposta.partida.jogadores.find((j) => j.sou_eu);
  if (eu && movimento.jogador_id === eu.jogador_id) return false;
  if (!guardado.animacoes()) return false;

  const peao = peaoDe(movimento.jogador_id);
  if (!peao) return false;

  ocupado = true;
  try {
    // Garante que o peão parte da origem, mesmo se uma consulta se perdeu.
    teleportarPeao(peao, movimento.de);

    const quem = resposta.partida.jogadores.find((j) => j.jogador_id === movimento.jogador_id);
    await encenarDados(`${quem?.nome || "Alguém"} tirou`, movimento.dados);

    await andarPeao(movimento);
    await espera(MS_APOS_CHEGAR);
  } finally {
    ocupado = false;
  }
  return true;
}

// --- rolar --------------------------------------------------------------

botaoJogar.addEventListener("click", async () => {
  if (ocupado || botaoJogar.disabled) return;
  ocupado = true;
  pintarJogar();
  // Enquanto o servidor não responde, os dados chacoalham na mão.
  elDados.classList.add("dados--rolando");
  limparSoma();
  som.tocar("clique");

  try {
    const resposta = await api.rolarDados(codigo);
    const movimento = resposta.partida.ultimo_movimento;
    // Marca como já visto: a consulta seguinte não repete a minha jogada.
    ultimoLanceVisto = movimento.lance;

    // 1. o arremesso: a faixa entra com os dados grandes girando
    // 2. só com o dado parado a soma aparece — antes disso não há o que ler
    elDados.classList.remove("dados--rolando");
    await encenarDados("Você tirou", movimento.dados, { meu: true });

    // 3. o peão anda casa por casa
    await andarPeao(movimento);

    // 4. um respiro para ver ONDE parou, antes da tela mudar
    await espera(MS_APOS_CHEGAR);

    // 5. e só agora o estado novo entra
    aplicar(resposta);
    contarJogada(movimento);
  } catch (erro) {
    som.tocar("erro");
    toast(erro.message, "erro");
    atualizar();
  } finally {
    elDados.classList.remove("dados--rolando");
    ocupado = false;
    if (estado) pintarJogar();
  }
});

async function responderCompra(comprar) {
  if (ocupado || modalCompra.hidden) return;
  ocupado = true;
  botoesCompra.forEach((botao) => (botao.disabled = true));
  pintarJogar();
  som.tocar(comprar ? "confirmar" : "voltar");
  try {
    aplicar(await api.decidirCompra(codigo, comprar));
  } catch (erro) {
    som.tocar("erro");
    toast(erro.message, "erro");
  } finally {
    ocupado = false;
    botoesCompra.forEach((botao) => (botao.disabled = false));
    if (estado) pintarJogar();
  }
}

document.querySelector("#compra-nao").addEventListener("click", () => responderCompra(false));
document.querySelector("#compra-sim").addEventListener("click", () => responderCompra(true));

// --- abertura ------------------------------------------------------------

/* A abertura é encenada, não listada: os bonecos entram pulando com os
   dados girando no alto, cai o total de cada um, e só no fim aparecem as
   colocações — de último para primeiro, para o vencedor ser a última coisa
   que a mesa descobre. */

function montarPosto(tirada, posicao, jogador, cor) {
  const posto = elemento("div", "posto");
  posto.style.setProperty("--cor", cor);
  posto.style.setProperty("--ordem", String(posicao));

  const caixaDados = elemento("div", "posto__dados");
  const cubinhos = tirada.dados.map(() => {
    const dado = elemento("div", "dado dado--mini");
    const cubo = elemento("div", "dado__cubo");
    cubo.replaceChildren(...criarFaces());
    dado.appendChild(cubo);
    caixaDados.appendChild(dado);
    return cubo;
  });

  const boneco = elemento("div", "posto__boneco");
  if (jogador?.personagem?.sprite) {
    const img = elemento("img");
    img.src = jogador.personagem.sprite;
    img.alt = tirada.nome;
    boneco.appendChild(img);
  } else {
    boneco.appendChild(elemento("div", "posto__ficha", inicial(tirada.nome)));
  }

  posto.append(
    caixaDados,
    elemento("div", "posto__total", String(tirada.soma)),
    elemento(
      "div",
      "posto__desempate",
      tirada.desempates?.length ? `desempate ${tirada.desempates.join(", ")}` : "",
    ),
    boneco,
    elemento("div", "posto__nome", tirada.nome),
    elemento("div", "posto__lugar", `${posicao + 1}º`),
  );

  return { posto, cubinhos, valores: tirada.dados };
}

async function mostrarOrdem() {
  ordemMostrada = true;
  const cores = new Map(estado.jogadores.map((j, i) => [j.jogador_id, corDoJogador(j, i)]));
  const porId = new Map(estado.jogadores.map((j) => [j.jogador_id, j]));
  const botao = document.querySelector("#ordem-fechar");
  botao.disabled = true;

  const postos = estado.sorteio.map((tirada, i) =>
    montarPosto(tirada, i, porId.get(tirada.jogador_id), cores.get(tirada.jogador_id) || "#7b2fbf"),
  );

  document.querySelector("#sorteio-mesa").replaceChildren(...postos.map((p) => p.posto));
  modalOrdem.hidden = false;

  // 1. entram pulando, com os dados girando no alto
  await espera(950);

  // 2. um a um, os dados caem e o total bate
  for (const { posto, cubinhos, valores } of postos) {
    valores.forEach((valor, i) => girarCubo(cubinhos[i], valor));
    posto.classList.add("posto--revelado");
    som.tocar("selecionar");
    await espera(440);
  }

  // 3. as colocações, do último para o primeiro
  await espera(520);
  for (let i = postos.length - 1; i >= 0; i -= 1) {
    postos[i].posto.classList.add("posto--colocado");
    som.tocar("clique");
    await espera(260);
  }

  postos[0].posto.classList.add("posto--vencedor");
  som.tocar("confirmar");
  botao.disabled = false;
}

document.querySelector("#ordem-fechar").addEventListener("click", () => {
  modalOrdem.hidden = true;
  som.tocar("confirmar");
  anunciarVez();
});

// --- chat ------------------------------------------------------------------

/** `lembrar` é falso só quando a tela restaura a escolha da última
    partida — aí também não puxa o foco para o campo. */
function abrirChat(aberto, { lembrar = true } = {}) {
  painelChat.hidden = !aberto;
  botaoChat.setAttribute("aria-expanded", String(aberto));
  botaoChat.classList.toggle("acao--ativa", aberto);
  if (lembrar) guardado.salvarChatAberto(aberto);
  if (!aberto) return;

  naoLidas = 0;
  pintarNaoLidas();
  listaChat.scrollTop = listaChat.scrollHeight;
  if (lembrar) campoChat.focus();
}

function pintarNaoLidas() {
  contadorChat.hidden = naoLidas === 0;
  contadorChat.textContent = naoLidas > 9 ? "9+" : String(naoLidas);
  botaoChat.classList.toggle("acao--novidade", naoLidas > 0);
}

/** Mensagem nova de outro jogador com o chat fechado: acende o botão. */
function avisarMensagens(novas) {
  const eu = estado?.jogadores.find((j) => j.sou_eu)?.jogador_id;
  const deOutros = novas.filter((m) => m.jogador_id !== eu);
  if (!deOutros.length || !painelChat.hidden) return;
  naoLidas += deOutros.length;
  pintarNaoLidas();
  som.tocar("aviso");
}

botaoChat.addEventListener("click", () => {
  som.tocar("clique");
  abrirChat(painelChat.hidden);
});

document.querySelector("#chat-fechar").addEventListener("click", () => {
  som.tocar("voltar");
  abrirChat(false);
});

// --- opções do canto ------------------------------------------------------

/* REGRAS e RANKING estão no desenho, mas ainda não foram
   construídas nesta tela. O clique responde em voz alta, como AMIGOS e
   LOJA no menu, em vez de não fazer nada. */
for (const [id, nome] of [["regras", "REGRAS"], ["ranking", "RANKING"]]) {
  document.querySelector(`#${id}`).addEventListener("click", () => {
    som.tocar("aviso");
    toast(`${nome} ainda não foi construído aqui. Em breve.`);
  });
}

function abrirConfiguracaoPartida() {
  pintarPreferenciaAnimacoes();
  painelConfigPartida.hidden = false;
  botaoAnimacoesPartida.focus();
}

function fecharConfiguracaoPartida() {
  painelConfigPartida.hidden = true;
  document.querySelector("#config").focus();
}

document.querySelector("#config").addEventListener("click", abrirConfiguracaoPartida);
document.querySelector("#config-partida-fechar").addEventListener("click", fecharConfiguracaoPartida);
botaoAnimacoesPartida.addEventListener("click", () => {
  guardado.salvarAnimacoes(!guardado.animacoes());
  pintarPreferenciaAnimacoes();
  som.tocar("clique");
});
painelConfigPartida.addEventListener("click", (evento) => {
  if (evento.target === painelConfigPartida) fecharConfiguracaoPartida();
});
document.addEventListener("keydown", (evento) => {
  if (evento.key === "Escape" && !painelConfigPartida.hidden) fecharConfiguracaoPartida();
});

document.querySelector("#sair").addEventListener("click", async () => {
  if (!confirm("Sair da partida? Você não volta para esta mesa.")) return;
  som.tocar("voltar");
  pararConsulta();
  try {
    // Avisa o servidor: sem isso a vez ficaria parada esperando alguém que
    // já foi embora, e a mesa travava.
    await api.sairDaPartida(codigo);
  } catch {
    /* sair é melhor esforço — o menu continua sendo o destino */
  }
  location.href = "/";
});

// --- consulta -------------------------------------------------------------

async function atualizar() {
  // Nunca redesenha no meio de uma jogada: o peão está andando.
  // `consultando` evita duas consultas em voo — sem ele, a mais antiga pode
  // voltar por último e reaplicar um estado já vencido.
  if (document.hidden || ocupado || consultando) return;

  consultando = true;
  try {
    const resposta = await api.verPartida(codigo);

    /* A trava do topo foi verificada ANTES da rede responder. Nesses
       ~200ms o jogador pode ter clicado em JOGAR, e aí esta resposta já
       nasceu velha. Descarta: a próxima consulta traz o estado certo. */
    if (ocupado) return;

    // Chegou jogada de outro? Encena antes de aplicar — senão o peão
    // aparece pronto no destino.
    const encenou = await encenarLanceDeOutro(resposta);
    aplicar(resposta);
    if (encenou) contarJogada(resposta.partida.ultimo_movimento);
  } catch (erro) {
    if (erro.status === 404) {
      pararConsulta();
      toast("A partida foi encerrada.", "erro");
      setTimeout(() => (location.href = "/"), 1600);
    }
  } finally {
    consultando = false;
  }
}

function iniciarConsulta() {
  pararConsulta();
  // 1,2s em vez de 2s: com a jogada dos outros sendo encenada, o atraso
  // até a cena começar passa a ser sentido.
  consulta = setInterval(atualizar, 1200);
  chat.iniciar();
}

function pararConsulta() {
  if (consulta) clearInterval(consulta);
  consulta = null;
  chat.parar();
}

document.addEventListener("visibilitychange", () => !document.hidden && atualizar());

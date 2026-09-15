/* Partida: tabuleiro, dados e compra — com o servidor mandando e a tela só
   contando a história.

   A ordem importa. Quando alguém rola, o servidor JÁ resolveu tudo; o que
   a tela faz depois é encenar na sequência certa: o dado tomba, assenta, o
   peão pula casa por casa, e só então o estado novo entra. Aplicar o estado
   antes disso é o que fazia a partida parecer uma planilha se atualizando. */

import { api, guardado } from "../core/api.js";
import { som } from "../core/som.js";
import { toast } from "../ui/toast.js";

const elTabuleiro = document.querySelector("#tabuleiro");
const elPeoes = document.querySelector("#peoes");
const elConstrucoes = document.querySelector("#construcoes");
const elPlacar = document.querySelector("#placar");
const elLog = document.querySelector("#log");
const elVezNome = document.querySelector("#vez-nome");
const elVezRodada = document.querySelector("#vez-rodada");
const elPainelTopo = document.querySelector(".painel__topo");
const elAviso = document.querySelector("#aviso");
const elSoma = document.querySelector("#dados-soma");
const elAnuncio = document.querySelector("#anuncio");
const elAnuncioTexto = document.querySelector("#anuncio-texto");
const elFlutuantes = document.querySelector("#flutuantes");
const botaoRolar = document.querySelector("#rolar");
const cubos = [document.querySelector("#cubo-a"), document.querySelector("#cubo-b")];
const dadosEl = [document.querySelector("#dado-a"), document.querySelector("#dado-b")];
const elDados = document.querySelector("#dados");
const modalCompra = document.querySelector("#modal-compra");
const modalOrdem = document.querySelector("#modal-ordem");

const CORES_RESERVA = ["#e94f37", "#7cb342", "#a855f7", "#ffd83d", "#2563c9", "#c9a227"];

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
/** Respiro depois da soma aparecer, para dar tempo de LER antes de andar. */
const MS_LER_RESULTADO = ms(1200);
/** Pausa depois que o peão pousa, antes do modal ou do estado novo entrar. */
const MS_APOS_CHEGAR = ms(650);
/** Quanto o recibo do aluguel fica na tela. */
const MS_RECIBO = ms(3200);
const MS_RECIBO_FALENCIA = ms(4200);

/** Para mostrar a face N, quanto o cubo precisa girar. */
const FACES = { 1: [0, 0], 2: [0, -90], 3: [-90, 0], 4: [90, 0], 5: [0, 90], 6: [0, 180] };

const codigo = new URLSearchParams(location.search).get("codigo")?.toUpperCase() || "";

let tabuleiro = null;
let estado = null;
let consulta = null;
let ocupado = false;
let ordemMostrada = false;
let ultimaVez = null;
let caixaAnterior = new Map();
let voltasDoDado = 0;
/** Último lance já encenado nesta tela. Evita repetir a jogada de alguém. */
let ultimoLanceVisto = 0;
/** Quem está no tabuleiro agora — usado para saber quando remontar os peões. */
let assinaturaDosPeoes = "";
/** Impede duas consultas em voo ao mesmo tempo, que voltariam fora de ordem. */
let consultando = false;
/** Lance cuja compra o jogador já respondeu. Impede reabrir o mesmo modal. */
let compraRespondida = 0;

if (!codigo || !guardado.token()) {
  toast("Volte ao menu e entre numa sala.", "erro");
  setTimeout(() => (location.href = "/"), 1400);
} else {
  montarDados();
  abrir();
}

async function abrir() {
  try {
    aplicar(await api.verPartida(codigo));
    iniciarConsulta();
  } catch (erro) {
    toast(erro.message, "erro");
    setTimeout(() => (location.href = `/lobby?codigo=${codigo}`), 1600);
  }
}

// --- utilidades -------------------------------------------------------

const espera = (ms) => new Promise((r) => setTimeout(r, ms));
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
  for (const cubo of cubos) cubo.replaceChildren(...criarFaces());
  mostrarDados([1, 1], { girar: false });
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

// --- tabuleiro (desenhado uma vez) ------------------------------------

function desenharTabuleiro(dados) {
  const itens = [];

  const miolo = elemento("div", "tabuleiro__miolo");
  miolo.appendChild(elemento("span", "tabuleiro__marca", "ROUBOPOLIS"));
  itens.push(miolo);

  for (const casa of dados.casas) {
    const el = elemento("div", "casa");
    el.dataset.i = String(casa.i);
    el.style.gridColumn = String(casa.x + 1);
    el.style.gridRow = String(casa.y + 1);

    if (casa.tipo === "propriedade") {
      el.style.setProperty("--cor-grupo", dados.grupos[casa.grupo]?.cor || "#999");
      el.appendChild(elemento("div", "casa__faixa"));
    } else {
      el.classList.add(
        casa.tipo === "inicial" ? "casa--inicial"
        : casa.tipo === "prisao" ? "casa--prisao"
        : casa.tipo === "neutra" ? "casa--neutra"
        : "casa--evento",
      );
    }

    el.appendChild(elemento("span", "casa__nome", casa.nome));
    if (casa.preco) el.appendChild(elemento("span", "casa__preco", reais(casa.preco)));
    itens.push(el);
  }

  // As duas camadas TÊM que ser reinseridas aqui: `replaceChildren` limpa o
  // tabuleiro inteiro, e uma camada esquecida vira um elemento solto fora
  // da página — o JS continua enchendo ela de conteúdo que ninguém vê.
  // Foi exatamente o que aconteceu com as construções.
  elTabuleiro.replaceChildren(...itens, elConstrucoes, elPeoes);
  conferirCamadas();
  aplicarRitmo();
}

/* O CSS anima o salto e o JS espera entre as casas. Se os dois tempos
   discordarem, o peão é arrancado para a casa seguinte antes de pousar e
   parece deslizar em vez de andar — foi o que aconteceu com 175ms no JS
   contra 300ms no CSS. Uma fonte da verdade só: o JS grava o valor. */
function aplicarRitmo() {
  elTabuleiro.style.setProperty("--ms-passo", `${MS_POR_CASA}ms`);
}

const casaDe = (i) => elTabuleiro.querySelector(`.casa[data-i="${i}"]`);

/** Centro da casa em porcentagem da grade — não precisa medir o DOM. */
function posicaoDaCasa(indice, assento = 0) {
  const casa = tabuleiro.casas[indice];
  const desloc = [[-1.2, -1.2], [1.2, -1.2], [-1.2, 1.2], [1.2, 1.2]][assento % 4];
  return {
    x: ((casa.x + 0.5) / tabuleiro.largura) * 100 + desloc[0],
    y: ((casa.y + 0.5) / tabuleiro.altura) * 100 + desloc[1],
  };
}

// --- peões -------------------------------------------------------------

/** Quem ainda está na mesa. Quem abandonou some do tabuleiro e do placar. */
function ativos() {
  return estado.jogadores.filter((j) => !j.falido);
}

function montarPeoes() {
  // O índice vem da lista COMPLETA: assim a cor e o canto da casa de cada
  // jogador não mudam quando alguém sai.
  const itens = estado.jogadores.flatMap((jogador, i) => {
    if (jogador.falido) return [];

    const peao = elemento("div", "peao");
    peao.dataset.jogador = String(jogador.jogador_id);
    peao.dataset.assento = String(i);

    peao.appendChild(elemento("div", "peao__sombra"));

    // A cor fica no peão inteiro: a base e a ficha herdam dela.
    peao.style.setProperty("--cor-peao", corDoJogador(jogador, i));

    // Disco deitado no chão, como peça de tabuleiro.
    peao.appendChild(elemento("div", "peao__base"));

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
  estado.jogadores.forEach((jogador, i) => {
    const peao = peaoDe(jogador.jogador_id);
    if (!peao) return;
    colocarPeao(peao, jogador.posicao, i);
    peao.classList.toggle("peao--da-vez", jogador.jogador_id === estado.vez.jogador_id);
  });
}

function colocarPeao(peao, indice, assento) {
  const { x, y } = posicaoDaCasa(indice, assento);
  peao.style.setProperty("--px", `${x}%`);
  peao.style.setProperty("--py", `${y}%`);
}

/** Põe o peão numa casa SEM deslizar — para prepará-lo antes de encenar. */
function teleportarPeao(peao, indice, assento) {
  peao.style.transition = "none";
  colocarPeao(peao, indice, assento);
  void peao.offsetWidth;
  peao.style.transition = "";
}

/** Pula de casa em casa até o destino. */
async function andarPeao({ jogador_id, de, passos }) {
  const peao = peaoDe(jogador_id);
  if (!peao || !tabuleiro) return;

  const assento = Number(peao.dataset.assento || 0);
  const total = tabuleiro.casas.length;

  for (let passo = 1; passo <= passos; passo += 1) {
    colocarPeao(peao, (de + passo) % total, assento);
    peao.classList.remove("peao--andando");
    void peao.offsetWidth; // reinicia a animação do salto
    peao.classList.add("peao--andando");
    som.tocar("clique");
    await espera(MS_POR_CASA);
  }
  peao.classList.remove("peao--andando");

  const chegada = casaDe((de + passos) % total);
  if (chegada) {
    chegada.classList.add("casa--destacada");
    setTimeout(() => chegada.classList.remove("casa--destacada"), 1600);
  }
}

// --- pintura ------------------------------------------------------------

function construcaoDe(indice) {
  return elConstrucoes.querySelector(`.construcao[data-i="${indice}"]`);
}

/* Guarda contra o bug que já aconteceu: uma camada fora do documento aceita
   tudo que se joga nela e não mostra nada. Falha barulhenta é melhor que
   um tabuleiro sem prédios sem ninguém saber por quê. */
function conferirCamadas() {
  for (const [nome, camada] of [["construcoes", elConstrucoes], ["peoes", elPeoes]]) {
    if (!camada.isConnected) {
      console.error(
        `A camada "${nome}" saiu do documento. Provavelmente um ` +
          "replaceChildren no tabuleiro esqueceu de reinseri-la.",
      );
    }
  }
}

function pintarDonos() {
  const cores = new Map(estado.jogadores.map((j, i) => [j.jogador_id, corDoJogador(j, i)]));
  const donos = estado.propriedades || {};

  for (const el of elTabuleiro.querySelectorAll(".casa")) {
    const indice = Number(el.dataset.i);
    const dono = donos[String(indice)]?.dono;
    const existente = construcaoDe(indice);

    if (dono === undefined) {
      el.classList.remove("casa--comprada");
      existente?.remove();
      continue;
    }

    el.classList.add("casa--comprada");

    // Já construída: só acerta a cor, caso o terreno tenha trocado de dono.
    if (existente) {
      existente.style.setProperty("--cor-dono", cores.get(dono) || "#fff");
      continue;
    }

    // A construção fica na CAMADA, não dentro da casa — por isso é
    // posicionada em porcentagem, igual aos peões.
    const casa = tabuleiro.casas[indice];
    const { x, y } = posicaoDaCasa(indice);
    const grupo = (casa.grupo || "media").replace(/_/g, "-");

    const marca = elemento("div", `construcao construcao--${grupo}`);
    marca.dataset.i = String(indice);
    marca.style.setProperty("--px", `${x}%`);
    marca.style.setProperty("--py", `${y}%`);
    marca.style.setProperty("--cor-dono", cores.get(dono) || "#fff");

    const corpo = elemento("span", "construcao__corpo");
    corpo.append(
      elemento("i", "construcao__lateral"),
      elemento("i", "construcao__janelas"),
      elemento("i", "construcao__porta"),
    );

    const predio = elemento("div", "construcao__predio");
    predio.append(elemento("span", "construcao__telhado"), corpo);
    marca.appendChild(predio);
    elConstrucoes.appendChild(marca);
  }
}

function pintarPlacar() {
  // Índice da lista completa para a cor não trocar quando alguém sai.
  const itens = estado.jogadores.flatMap((jogador, i) => {
    if (jogador.falido) return [];

    const cartao = elemento("div", "jogador");
    cartao.dataset.jogador = String(jogador.jogador_id);
    cartao.style.setProperty("--cor-jogador", corDoJogador(jogador, i));
    if (jogador.jogador_id === estado.vez.jogador_id) cartao.classList.add("jogador--da-vez");
    if (jogador.sou_eu) cartao.classList.add("jogador--eu");

    const retrato = elemento("div", "jogador__retrato");
    if (jogador.personagem?.sprite) {
      const img = elemento("img");
      img.src = jogador.personagem.sprite;
      img.alt = "";
      retrato.appendChild(img);
    } else {
      retrato.textContent = inicial(jogador.nome);
    }

    const dados = elemento("div", "jogador__dados");
    dados.append(
      elemento("div", "jogador__nome", jogador.nome),
      elemento("div", "jogador__caixa", reais(jogador.caixa)),
      elemento("div", "jogador__terrenos", `${jogador.propriedades.length} terreno(s)`),
    );

    cartao.append(retrato, dados);
    return [cartao];
  });
  elPlacar.replaceChildren(...itens);
}

function pintarVez() {
  const minha = estado.vez.sou_eu;
  elVezNome.textContent = minha ? "VOCÊ" : estado.vez.nome;
  elVezRodada.textContent = `rodada ${estado.rodada}`;
  elPainelTopo.classList.toggle("painel__topo--minha", minha);

  const podeRolar = minha && estado.fase === "aguardando_rolagem";
  botaoRolar.disabled = !podeRolar || ocupado;
  elAviso.textContent =
    estado.fase === "encerrada" ? "A partida acabou."
    : estado.fase === "decidindo_compra" && minha ? "Decida se compra o terreno."
    : estado.fase === "decidindo_compra" ? `${estado.vez.nome} está decidindo uma compra.`
    : podeRolar ? "Sua vez! Role os dados."
    : `Esperando ${estado.vez.nome} jogar.`;
}

/* O log é APPEND-ONLY.

   Redesenhar a lista inteira a cada consulta fazia toda linha nascer de
   novo, reiniciando a animação de entrada em todas ao mesmo tempo — era
   isso que piscava de dois em dois segundos.

   O servidor manda uma janela das últimas linhas, então a janela desliza:
   acho o maior trecho do fim do que já está na tela que casa com o começo
   do que chegou, e acrescento só o resto. */

let logNaTela = [];

function pintarLog() {
  const chegou = estado.log.map((l) => `${l.tipo}${l.texto}`);

  let iguais = 0;
  const maximo = Math.min(logNaTela.length, chegou.length);
  for (let n = maximo; n > 0; n -= 1) {
    const cauda = logNaTela.slice(logNaTela.length - n);
    if (cauda.every((v, i) => v === chegou[i])) {
      iguais = n;
      break;
    }
  }

  // Sem sobreposição nenhuma (primeira pintura, ou o log foi reiniciado):
  // aí sim vale redesenhar tudo de uma vez.
  if (iguais === 0 && logNaTela.length) {
    elLog.replaceChildren();
    logNaTela = [];
  }

  // A assinatura serve so para comparar; o conteudo sai do objeto original.
  const novas = estado.log.slice(iguais);
  if (!novas.length) return;

  // Só arrasta para o fim se a pessoa já estava no fim — senão ela perde a
  // linha que estava lendo.
  const estavaNoFim = elLog.scrollHeight - elLog.scrollTop - elLog.clientHeight < 40;

  for (const linha of novas) {
    elLog.appendChild(elemento("li", `log--${linha.tipo}`, linha.texto));
  }

  logNaTela = chegou;

  // Mantém a lista curta: o DOM não precisa guardar o que saiu da janela.
  while (elLog.children.length > 40) elLog.firstElementChild.remove();

  if (estavaNoFim) elLog.scrollTop = elLog.scrollHeight;
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
  if (estado.vez.jogador_id === ultimaVez) return;
  ultimaVez = estado.vez.jogador_id;
  elAnuncioTexto.textContent = estado.vez.sou_eu ? "Sua vez!" : `Vez de ${estado.vez.nome}`;
  elAnuncio.classList.remove("anuncio--passando");
  void elAnuncio.offsetWidth;
  elAnuncio.classList.add("anuncio--passando");
}

/** Número subindo sobre o cartão de quem ganhou ou perdeu dinheiro. */
function mostrarDiferencasDeCaixa() {
  for (const jogador of estado.jogadores) {
    const antes = caixaAnterior.get(jogador.jogador_id);
    caixaAnterior.set(jogador.jogador_id, jogador.caixa);
    if (antes === undefined || antes === jogador.caixa) continue;

    const delta = jogador.caixa - antes;
    const cartao = elPlacar.querySelector(`.jogador[data-jogador="${jogador.jogador_id}"]`);
    if (!cartao) continue;

    const caixa = cartao.getBoundingClientRect();
    const flutuante = elemento(
      "div",
      `flutuante ${delta > 0 ? "flutuante--ganho" : "flutuante--perda"}`,
      `${delta > 0 ? "+" : "−"} ${reais(Math.abs(delta))}`,
    );
    flutuante.style.left = `${caixa.left + caixa.width * 0.5}px`;
    flutuante.style.top = `${caixa.top}px`;
    elFlutuantes.appendChild(flutuante);
    setTimeout(() => flutuante.remove(), 1600);
  }
}

// --- aplicar estado -----------------------------------------------------

function aplicar(resposta) {
  const primeiraVez = !tabuleiro;
  if (primeiraVez) {
    tabuleiro = resposta.tabuleiro;
    desenharTabuleiro(tabuleiro);
  }
  const antes = estado;
  estado = resposta.partida;
  estado.regras = resposta.regras;

  // Na primeira pintura, o lance que já estava no estado não é encenado:
  // seria repetir uma jogada que aconteceu antes de eu abrir a tela.
  if (primeiraVez) {
    ultimoLanceVisto = estado.ultimo_movimento?.lance ?? 0;
    ultimoAluguelVisto = estado.ultimo_aluguel?.lance ?? 0;
  }

  // Remonta os peões quando alguém entra ou sai da mesa.
  const agora = ativos().map((j) => j.jogador_id).join(",");
  if (primeiraVez || agora !== assinaturaDosPeoes) montarPeoes();
  if (antes) avisarQuemSaiu(antes);

  pintarDonos();
  posicionarPeoes();
  pintarPlacar();
  pintarVez();
  pintarLog();
  mostrarDiferencasDeCaixa();
  anunciarVez();

  if (!ordemMostrada && estado.sorteio?.length) mostrarOrdem();
  if (estado.fase === "decidindo_compra" && estado.vez.sou_eu) abrirCompra();
}

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

  const peao = peaoDe(movimento.jogador_id);
  if (!peao) return false;

  ocupado = true;
  try {
    // Garante que o peão parte da origem, mesmo se uma consulta se perdeu.
    teleportarPeao(peao, movimento.de, Number(peao.dataset.assento || 0));

    arremessar(movimento.dados);
    som.tocar("selecionar");
    await espera(MS_ARREMESSO);

    mostrarSoma(movimento.dados);
    await espera(MS_LER_RESULTADO);

    await andarPeao(movimento);
    await espera(MS_APOS_CHEGAR);
    await mostrarAluguel(resposta.partida.ultimo_aluguel);
  } finally {
    ocupado = false;
  }
  return true;
}

// --- rolar --------------------------------------------------------------

botaoRolar.addEventListener("click", async () => {
  if (ocupado || botaoRolar.disabled) return;
  ocupado = true;
  botaoRolar.disabled = true;
  // Enquanto o servidor não responde, os dados chacoalham na mão.
  elDados.classList.add("dados--rolando");
  limparSoma();
  som.tocar("clique");

  try {
    const resposta = await api.rolarDados(codigo);
    const movimento = resposta.partida.ultimo_movimento;
    // Marca como já visto: a consulta seguinte não repete a minha jogada.
    ultimoLanceVisto = movimento.lance;

    // 1. o arremesso: caem de cima, quicam e assentam no valor
    elDados.classList.remove("dados--rolando");
    arremessar(movimento.dados);
    som.tocar("selecionar");
    await espera(MS_ARREMESSO);

    // 2. só com o dado parado a soma aparece — antes disso não há o que ler
    mostrarSoma(movimento.dados);
    som.tocar("confirmar");
    await espera(MS_LER_RESULTADO);

    // 3. o peão anda casa por casa
    await andarPeao(movimento);

    // 4. um respiro para ver ONDE parou, antes da tela mudar
    await espera(MS_APOS_CHEGAR);

    // 5. e só agora o estado novo entra
    aplicar(resposta);

    // 5. se parou em terreno alheio, o recibo do aluguel
    await mostrarAluguel(resposta.partida.ultimo_aluguel);
  } catch (erro) {
    som.tocar("erro");
    toast(erro.message, "erro");
    atualizar();
  } finally {
    elDados.classList.remove("dados--rolando");
    ocupado = false;
    if (estado) pintarVez();
  }
});

// --- recibo do aluguel ----------------------------------------------------

const modalAluguel = document.querySelector("#modal-aluguel");
let ultimoAluguelVisto = 0;

/** Mostra quem pagou a quem, quanto e onde. Some sozinho. */
async function mostrarAluguel(cobranca) {
  if (!cobranca || cobranca.lance <= ultimoAluguelVisto) return;
  ultimoAluguelVisto = cobranca.lance;

  const caixa = modalAluguel.querySelector(".recibo");
  caixa.classList.toggle("recibo--falencia", Boolean(cobranca.faliu));

  document.querySelector("#aluguel-titulo").textContent = cobranca.faliu ? "Faliu" : "Aluguel";
  document.querySelector("#aluguel-casa").textContent = cobranca.casa_nome;
  document.querySelector("#aluguel-de").textContent = cobranca.de;
  document.querySelector("#aluguel-para").textContent = cobranca.para;
  document.querySelector("#aluguel-valor").textContent = reais(cobranca.valor);

  const detalhe = document.querySelector("#aluguel-detalhe");
  const texto = cobranca.faliu
    ? `Só tinha ${reais(cobranca.pago)} — os terrenos voltaram ao banco.`
    : cobranca.detalhe || "";
  detalhe.textContent = texto;
  detalhe.hidden = !texto;

  modalAluguel.hidden = false;
  som.tocar(cobranca.faliu ? "erro" : "aviso");
  await espera(cobranca.faliu ? MS_RECIBO_FALENCIA : MS_RECIBO);
  modalAluguel.hidden = true;
}

// --- compra --------------------------------------------------------------

function abrirCompra() {
  const pendente = estado.compra_pendente;
  if (!pendente || !modalCompra.hidden) return;

  /* Já respondi a compra DESTE lance: uma resposta atrasada do servidor
     ainda traz `decidindo_compra`, e sem esta trava ela reabriria o modal
     de um terreno que o jogador já decidiu. */
  if ((estado.ultimo_movimento?.lance ?? 0) === compraRespondida) return;

  const casa = tabuleiro.casas[pendente.casa];
  const grupo = tabuleiro.grupos[casa.grupo] || {};
  const eu = estado.jogadores.find((j) => j.sou_eu);
  const sobra = (eu?.caixa || 0) - pendente.preco;
  const fracaoAluguel = estado.regras?.aluguel?.base ?? 0.2;

  const cabecalho = document.querySelector("#compra-cabecalho");
  cabecalho.style.setProperty("--cor-grupo", grupo.cor || "#7b2fbf");
  document.querySelector("#compra-grupo").textContent = grupo.rotulo || "Terreno";
  document.querySelector("#compra-titulo").textContent = casa.nome;
  document.querySelector("#compra-preco").textContent = reais(pendente.preco);
  document.querySelector("#compra-aluguel").textContent = reais(pendente.preco * fracaoAluguel);
  document.querySelector("#compra-caixa").textContent = reais(eu?.caixa);

  const elSobra = document.querySelector("#compra-sobra");
  elSobra.textContent = reais(sobra);
  // Ficar com menos de um quinto do que tinha é aperto — o número avisa.
  elSobra.classList.toggle("apertado", sobra < (eu?.caixa || 0) * 0.2);

  modalCompra.hidden = false;
  som.tocar("aviso");
}

async function responderCompra(comprar) {
  modalCompra.hidden = true;
  // Marca ANTES de chamar a rede: qualquer consulta que já estava em voo
  // volta com o estado velho e precisa ser ignorada.
  compraRespondida = estado.ultimo_movimento?.lance ?? 0;
  ocupado = true;
  try {
    som.tocar(comprar ? "confirmar" : "voltar");
    aplicar(await api.decidirCompra(codigo, comprar));
  } catch (erro) {
    som.tocar("erro");
    toast(erro.message, "erro");
    atualizar();
  } finally {
    ocupado = false;
  }
}

document.querySelector("#comprar-sim").addEventListener("click", () => responderCompra(true));
document.querySelector("#comprar-nao").addEventListener("click", () => responderCompra(false));

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

document.querySelector("#sair").addEventListener("click", async () => {
  if (!confirm("Sair da partida? Seus terrenos voltam para o banco.")) return;
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
       ~200ms o jogador pode ter clicado em algo, e aí esta resposta já
       nasceu velha. Descarta: a próxima consulta traz o estado certo.
       Era isto que reabria o modal de compra depois de respondido. */
    if (ocupado) return;

    // Chegou jogada de outro? Encena antes de aplicar — senão o peão
    // aparece pronto no destino.
    await encenarLanceDeOutro(resposta);
    aplicar(resposta);
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
}

function pararConsulta() {
  if (consulta) clearInterval(consulta);
  consulta = null;
}

document.addEventListener("visibilitychange", () => !document.hidden && atualizar());

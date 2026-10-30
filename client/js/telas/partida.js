/* Partida: o tabuleiro isométrico, com o servidor mandando e a tela só
   contando a história.

   A tela encena o sorteio, a rolagem, o movimento (com o Portal no meio do
   caminho), a compra de terrenos, o aluguel, as melhorias, as casas de
   evento e os eventos temáticos; no fim, o pódio. Quem é amigo de alguém da
   mesa pode assistir: vê tudo, não joga.

   A ordem importa. Quando alguém rola, o servidor JÁ resolveu tudo; o que
   a tela faz depois é encenar na sequência certa: o dado tomba, assenta, o
   peão pula casa por casa, e só então o estado novo entra. Aplicar o estado
   antes disso é o que fazia a partida parecer uma planilha se atualizando. */

import { api, ErroDaApi, guardado } from "../core/api.js";
import { musica } from "../core/musica.js";
import { som } from "../core/som.js";
import { anunciar, anuncioAberto, fecharAnuncio, limparAnuncios } from "../ui/anuncios.js";
import { montarChat } from "../ui/chat.js";
import { elemento, formatarTempo, inicial, porcento, reais } from "../ui/comum.js";
import { contando, contarDinheiro, flutuarDinheiro } from "../ui/dinheiro_flutuante.js";
import { toast } from "../ui/toast.js";
import { itensDaLegenda, montarTabuleiro } from "../tabuleiro/render.js";
import { iconePixel } from "../tabuleiro/pixel.js";
import { decisaoDoBonus } from "../modais/bonus_banco.js";
import { decisaoDoCoringa } from "../modais/coringa.js";
import { abrirDecisao, decisaoAberta, definirExecutor, definirTempoDaDecisao, fecharDecisao } from "../modais/decisao.js";
import { fecharFimDePartida, fimAberto, mostrarFimDePartida } from "../modais/fim_de_partida.js";
import {
  definirLanceDoLeilao,
  esconderLeilao,
  escolhaDoLeilao,
  fecharFimDoLeilao,
  fecharLeilao,
  fimDoLeilaoAberto,
  leilaoEscondido,
  mostrarFimDoLeilao,
  pintarLeilao,
  reabrirLeilao,
} from "../modais/leilao.js";
import { decisaoDoPrejuizo } from "../modais/prejuizo.js";
import { decisaoDaReconstrucao } from "../modais/reconstrucao.js";

const elTabuleiro = document.querySelector("#tabuleiro");
const elSvg = document.querySelector("#tabuleiro-svg");
const elPeoes = document.querySelector("#peoes");
const elInicio = document.querySelector("#inicio-marcador");
const elJogadores = document.querySelector("#jogadores");
const elLegenda = document.querySelector("#legenda");
const botaoLegenda = document.querySelector("#legenda-alternar");
const elAviso = document.querySelector("#aviso");
const elChipEspectador = document.querySelector("#chip-espectador");
const elChipTempo = document.querySelector("#chip-tempo");
const elChipTempoValor = document.querySelector("#chip-tempo-valor");
const elChipRodada = document.querySelector("#chip-rodada");
const elChipColetor = document.querySelector("#chip-coletor");
const elChipColetorValor = document.querySelector("#chip-coletor-valor");
const elEventoChip = document.querySelector("#evento-chip");
const elEventoChipNome = document.querySelector("#evento-chip-nome");
const elEventoChipTexto = document.querySelector("#evento-chip-texto");
const painelCasaInfo = document.querySelector("#painel-casa-info");
const tipoCasaInfo = document.querySelector("#casa-info-tipo");
const tituloCasaInfo = document.querySelector("#casa-info-titulo");
const detalhesCasaInfo = document.querySelector("#casa-info-detalhes");
const elAnuncio = document.querySelector("#anuncio");
const elAnuncioTexto = document.querySelector("#anuncio-texto");
const elAnuncioDados = document.querySelector("#anuncio-dados");
const elAnuncioDadosQuem = document.querySelector("#anuncio-dados-quem");
const elAnuncioDadosSoma = document.querySelector("#anuncio-dados-soma");
const cubosGrandes = [document.querySelector("#cubo-grande-a"), document.querySelector("#cubo-grande-b")];
const botaoJogar = document.querySelector("#jogar");
const botaoVenderBonus = document.querySelector("#vender-bonus");
const botaoLeiloar = document.querySelector("#leiloar");
const botoesLeiloarNaDecisao = document.querySelectorAll("[data-leiloar]");
const botaoVerLeilao = document.querySelector("#ver-leilao");
const modalOrdem = document.querySelector("#modal-ordem");
const modalCompra = document.querySelector("#modal-compra");
const chamadaCompra = document.querySelector(".compra__chamada");
const tituloCompra = document.querySelector("#compra-titulo");
const vendedorCompra = document.querySelector("#compra-vendedor");
const precoCompra = document.querySelector("#compra-preco");
const aluguelCompra = document.querySelector("#compra-aluguel");
const saldoCompra = document.querySelector("#compra-saldo");
const tempoCompra = document.querySelector("#compra-tempo");
const botoesCompra = [document.querySelector("#compra-nao"), document.querySelector("#compra-sim")];
const modalLiquidacao = document.querySelector("#modal-liquidacao");
const casaLiquidacao = document.querySelector("#liquidacao-casa");
const dividaLiquidacao = document.querySelector("#liquidacao-divida");
const caixaLiquidacao = document.querySelector("#liquidacao-caixa");
const tempoLiquidacao = document.querySelector("#liquidacao-tempo");
const listaLiquidacao = document.querySelector("#liquidacao-lista");
const modalSair = document.querySelector("#modal-sair");
const painelConfigPartida = document.querySelector("#painel-config-partida");
const botaoAnimacoesPartida = document.querySelector("#animacoes-partida");
const menuAcoes = document.querySelector("#acoes-menu");
const botaoMenuAcoes = document.querySelector("#acoes-alternar");
const painelChat = document.querySelector("#chat");
const botaoChat = document.querySelector("#chat-abrir");
const contadorChat = document.querySelector("#chat-contador");
const formularioChat = document.querySelector("#chat-formulario");
const campoChat = document.querySelector("#chat-texto");
const listaChat = document.querySelector("#chat-mensagens");
const painelDev = document.querySelector("#painel-dev");
const formCaixaDev = document.querySelector("#dev-form-caixa");
const formIrDev = document.querySelector("#dev-form-ir");
const formAndarDev = document.querySelector("#dev-form-andar");
const campoCaixaDev = document.querySelector("#dev-caixa");
const seletorCasaDev = document.querySelector("#dev-casa");
const campoPassosDev = document.querySelector("#dev-passos");

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
/** O peão subindo pelo feixe do portal — e de novo, descendo na casa sorteada. */
const MS_PORTAL = ms(560);
/** O feixe de luz acendendo (e apagando) numa casa. */
const MS_FEIXE = ms(260);
/** O "?" da Coringa girando antes do resultado. */
const MS_SUSPENSE = ms(1500);
/** Quanto a frase "fulano tirou 7 e parou em Moema" fica embaixo do JOGAR. */
const MS_RESUMO_DA_JOGADA = ms(4500);

/** Para mostrar a face N, quanto o cubo precisa girar. */
const FACES = { 1: [0, 0], 2: [0, -90], 3: [-90, 0], 4: [90, 0], 5: [0, 90], 6: [0, 180] };

const codigo = new URLSearchParams(location.search).get("codigo")?.toUpperCase() || "";

let tabuleiro = null;
/** O que `montarTabuleiro` devolveu: onde fica cada casa na tela. */
let desenho = null;
let estado = null;
/** Quem não está na mesa e só assiste (amigo de alguém dela). */
let espectador = false;
/** Os números do balanceamento que a tela mostra (envelope `regras`): casas,
    bônus do Morro e leilão. */
let regras = {};
/** Números das casas, para a tela explicar cada uma (`regras.casas`). */
let valores = {};
/** As frases de sátira das janelas de evento (data/eventos/), buscadas uma
    vez ao abrir a partida. */
let frases = { tematicos: {}, casas: {} };
/** Cores dos itens da loja que a mesa está usando, por slug. */
let cosmeticos = {};
/** Créditos que esta pessoa ganhou, quando a partida acaba. */
let ultimaRecompensa = null;
let prazoLocalMs = null;
let prazoPartidaLocalMs = null;
let consulta = null;
let ocupado = false;
let ordemMostrada = false;
let ultimaVez = null;
/** Último lance já encenado nesta tela. Evita repetir a jogada de alguém. */
let ultimoLanceVisto = 0;
/** Última linha do log já anunciada (o número `n` que o motor dá a cada uma). */
let ultimoLogVisto = 0;
/** Último resultado da Coringa já encenado, e o que espera ser revelado. */
let ultimoCoringaVisto = 0;
let coringaParaRevelar = null;
let fimMostrado = false;
/** A janela do Bônus do banco aberta pelo botão, antes de rolar. */
let bonusNaMao = false;
/** A escolha do que leiloar, aberta pelo botão, antes de rolar. */
let leilaoNaMao = false;
/** O último leilão que abriu (pelo `n`) e o último resultado já mostrado. */
let ultimoLeilaoAberto = 0;
let ultimoLeilaoVisto = 0;
/** Sobe a cada lance que esta tela manda: a consulta que saiu antes dele
    volta com o estado sem o lance e precisa ser descartada. */
let geracao = 0;
/** Se o servidor aceita o modo dev (MODO_DEV em server/config.py). */
let devDisponivel = false;
let ritmoDaConsulta = null;
/** Quem está no tabuleiro agora — usado para saber quando remontar os peões. */
let assinaturaDosPeoes = "";
/** Quem está nos cartões — idem, para os cartões. */
let assinaturaDosCartoes = "";
let assinaturaDasPropriedades = "";
let assinaturaDaRegiao = "";
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
  formulario: formularioChat,
  campo: campoChat,
  status: document.querySelector("#chat-status"),
  corDe: corPeloId,
  aoChegar: avisarMensagens,
  aoComando: tratarComando,
});

preencherIcones();
// A música continua de onde o lobby parou.
musica.iniciar();
abrirLegenda(guardado.legendaAberta(), { lembrar: false });
abrirMenuAcoes(guardado.opcoesAbertas(), { lembrar: false });

if (!codigo || !guardado.token()) {
  toast("Volte ao menu e entre numa sala.", "erro");
  setTimeout(() => (location.href = "/"), 1400);
} else {
  montarDados();
  abrirChat(guardado.chatAberto(), { lembrar: false });
  abrir();
}

async function abrir() {
  // As frases só enfeitam a janela do evento: sem elas a partida segue,
  // mas a falta aparece em vez de sumir calada.
  api.frasesDosEventos()
    .then((recebidas) => (frases = recebidas))
    .catch(() => toast("Não consegui carregar as frases dos eventos.", "erro"));
  try {
    aplicar(await api.verPartida(codigo));
    if (espectador) toast("Você está assistindo. Dá para ver tudo, mas não jogar.", "ok", 4200);
    await chat.atualizar();
    iniciarConsulta();
  } catch (erro) {
    toast(erro.message, "erro");
    // Espectador barrado volta ao menu; jogador volta ao lobby da sala.
    setTimeout(() => (location.href = erro.status === 403 ? "/" : `/lobby?codigo=${codigo}`), 1600);
  }
}

// --- utilidades -------------------------------------------------------

const espera = (duracao) => new Promise((resolver) => setTimeout(resolver, guardado.animacoes() ? duracao : 0));

function corDoJogador(jogador, i) {
  return jogador.personagem?.cor || CORES_RESERVA[i % CORES_RESERVA.length];
}

/** A mesma cor do peão, para o nome no chat e o dono no tabuleiro. */
function corPeloId(jogadorId) {
  const i = estado?.jogadores.findIndex((j) => j.jogador_id === jogadorId) ?? -1;
  return i >= 0 ? corDoJogador(estado.jogadores[i], i) : null;
}

/** O item da loja (`tipo` "dado" ou "casa") que o jogador trouxe para a mesa. */
function visualDe(jogadorId, tipo) {
  const jogador = estado?.jogadores.find((j) => j.jogador_id === jogadorId);
  const slug = jogador?.visual?.[tipo];
  return slug && cosmeticos[slug] ? { slug, visual: cosmeticos[slug].visual } : null;
}

const euNaMesa = () => estado?.jogadores.find((j) => j.sou_eu) || null;
const nomeDe = (jogador) => (jogador?.sou_eu ? "Você" : jogador?.nome || "Alguém");

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
  for (const cubo of cubosGrandes) cubo.replaceChildren(...criarFaces());
}

/** As cores do dado da loja de quem rola. O CSS dos dados lê as variáveis
    do pai (css/componentes/dados.css); sem item equipado, vale o clássico. */
function vestirDados(alvo, jogadorId) {
  const loja = visualDe(jogadorId, "dado")?.visual;
  const cores = {
    "--dado-face-a": loja?.face?.[0],
    "--dado-face-b": loja?.face?.[1],
    "--dado-borda": loja?.borda,
    "--dado-ponto": loja?.ponto,
  };
  for (const [nome, valor] of Object.entries(cores)) {
    if (valor) alvo.style.setProperty(nome, valor);
    else alvo.style.removeProperty(nome);
  }
}

/* A rolagem, igual para quem rolou e para quem assiste: uma faixa que
   atravessa a tela como o anúncio da vez, com os dados grandes no meio.
   No tabuleiro não há dado — é a faixa que a mesa lê.

   Três tempos: `abrirFaixaDosDados` entra com os cubos rodando soltos (na
   minha jogada, isso cobre a espera pelo servidor); `encenarDados` assenta
   os cubos no valor e bate o total; `fecharFaixaDosDados` sai antes do peão
   andar — senão a faixa cobriria o caminho dele. */

function abrirFaixaDosDados(quem, jogadorId) {
  vestirDados(elAnuncioDados, jogadorId);
  elAnuncioDadosQuem.textContent = quem;
  elAnuncioDadosSoma.replaceChildren();
  elAnuncioDados.classList.remove("anuncio-dados--saindo", "anuncio-dados--revelado");
  elAnuncioDados.classList.add("anuncio-dados--dentro", "anuncio-dados--rolando");
  som.tocar("vento");
}

async function encenarDados(quem, valores, jogadorId) {
  // Sem animação não há faixa: o aviso embaixo do JOGAR conta o resultado.
  if (!guardado.animacoes()) {
    som.tocar("resultado");
    await fecharFaixaDosDados();
    return;
  }

  if (!elAnuncioDados.classList.contains("anuncio-dados--dentro")) abrirFaixaDosDados(quem, jogadorId);
  elAnuncioDadosSoma.replaceChildren(
    elemento("span", "anuncio-dados__parcelas", valores.join("  +  ")),
    elemento("span", "anuncio-dados__total", String(valores.reduce((a, b) => a + b, 0))),
  );

  // Param de rodar soltos e tombam até o valor. Antes, voltam à pose de
  // repouso sem transição: assim tombam as mesmas três voltas toda vez, em
  // vez de só o que falta da rolagem anterior.
  elAnuncioDados.classList.remove("anuncio-dados--rolando");
  for (const cubo of cubosGrandes) {
    cubo.style.transition = "none";
    cubo.style.transform = "";
  }
  void elAnuncioDados.offsetWidth;
  for (const cubo of cubosGrandes) cubo.style.transition = "";
  valores.forEach((valor, i) => girarCubo(cubosGrandes[i], valor, 3));
  som.tocar("dado");

  // Só com o dado parado o total aparece — antes disso não há o que ler.
  await espera(MS_ARREMESSO);
  elAnuncioDados.classList.add("anuncio-dados--revelado");
  som.tocar("resultado");
  await espera(MS_LER_RESULTADO);

  await fecharFaixaDosDados();
}

async function fecharFaixaDosDados() {
  if (!elAnuncioDados.classList.contains("anuncio-dados--dentro")) return;
  elAnuncioDados.classList.remove("anuncio-dados--rolando");
  elAnuncioDados.classList.replace("anuncio-dados--dentro", "anuncio-dados--saindo");
  await espera(MS_DESLIZE_FAIXA);
  // O estado de repouso não tem transição: volta para a esquerda sem
  // atravessar a tela de novo.
  elAnuncioDados.classList.remove("anuncio-dados--saindo", "anuncio-dados--revelado");
}

// --- tabuleiro (desenhado uma vez) ------------------------------------

function assinaturaPropriedades(propriedades = {}) {
  return Object.entries(propriedades)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([indice, propriedade]) => `${indice}:${propriedade.dono}:${propriedade.nivel || 0}`)
    .join("|");
}

function desenharTabuleiro(dados, propriedades = {}) {
  desenho = montarTabuleiro(elSvg, dados, propriedades, {
    corDoDono: corPeloId,
    visualDoDono: (jogadorId) => visualDe(jogadorId, "casa"),
  });
  assinaturaDasPropriedades = assinaturaPropriedades(propriedades);
  const inicio = desenho.pontoInicio();
  elInicio.style.setProperty("--inicio-x", `${inicio.x}%`);
  elInicio.style.setProperty("--inicio-y", `${inicio.y}%`);
  // O quadro do tabuleiro tem a proporção do desenho: é isso que faz a
  // porcentagem de um peão cair exatamente em cima da casa certa. Vai na
  // mesa, que usa o número para o próprio tamanho, e o tabuleiro herda.
  elTabuleiro.parentElement.style.setProperty("--proporcao", desenho.proporcao.toFixed(4));
  // A altura do peão é a que o desenho reservou no topo: com outra, a
  // cabeça do boneco no canto de cima sai da tela.
  elTabuleiro.style.setProperty("--peao-alt", `${(desenho.alturaDoPeao * 100).toFixed(2)}cqw`);

  aplicarRitmo();
  montarLegenda(dados);
}

function montarLegenda(dados) {
  elLegenda.replaceChildren(
    ...itensDaLegenda(dados).map(({ chave, rotulo, cor }) => {
      const item = elemento("li", "legenda__item");
      const amostra = elemento("span", "legenda__cor");
      amostra.style.setProperty("--cor", cor);
      item.append(amostra, elemento("span", "", chave ? rotuloDoGrupo(chave) : rotulo));
      return item;
    }),
  );
}

/** O nome do grupo, e "· Morro" no grupo das casas de favela — é ele que
    dá o bônus (`morro.grupo` no balanceamento). */
function rotuloDoGrupo(chave) {
  const rotulo = tabuleiro?.grupos?.[chave]?.rotulo || chave;
  return chave === regras.morro?.grupo ? `${rotulo} · Morro` : rotulo;
}

const vezes = (multiplicador) => `${Number(multiplicador).toLocaleString("pt-BR", { minimumFractionDigits: 1 })}×`;

/** "2 casas 1,2× · 3 casas 1,4× ..." — a tabela do balanceamento. */
function faixasDoMorro() {
  return Object.entries(regras.morro?.multiplicadores || {})
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([casas, multiplicador]) => `${casas} casas ${vezes(multiplicador)}`)
    .join(" · ");
}

/* O CSS anima o salto e o JS espera entre as casas. Se os dois tempos
   discordarem, o peão é arrancado para a casa seguinte antes de pousar e
   parece deslizar em vez de andar. Uma fonte da verdade só: o JS grava o
   valor. */
function aplicarRitmo() {
  elTabuleiro.style.setProperty("--ms-passo", `${MS_POR_CASA}ms`);
  elTabuleiro.style.setProperty("--ms-portal", `${MS_PORTAL}ms`);
  elTabuleiro.style.setProperty("--ms-feixe", `${MS_FEIXE}ms`);
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
    peao.classList.toggle("peao--preso", jogador.preso > 0);
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

/** Pula `passos` casas a partir de `de`, uma de cada vez. */
async function pular(peao, de, passos, total) {
  for (let passo = 1; passo <= passos; passo += 1) {
    colocarPeao(peao, (de - (passo % total) + total) % total);
    peao.classList.remove("peao--andando");
    void peao.offsetWidth; // reinicia a animação do salto
    peao.classList.add("peao--andando");
    som.tocar("passo");
    await espera(MS_POR_CASA);
  }
}

/** Um feixe de luz em pé na casa, no lugar dos pés do peão: a coluna, o
    miolo branco, o anel no chão e as faíscas subindo. */
function acenderFeixe(indice, assento) {
  const { x, y } = desenho.ponto(indice, assento);
  const feixe = elemento("div", "feixe");
  feixe.style.setProperty("--px", `${x}%`);
  feixe.style.setProperty("--py", `${y}%`);
  // Logo atrás do peão daquele ponto: a luz o envolve sem apagar o boneco.
  feixe.style.zIndex = String(Math.round(y * 10) - 1);
  feixe.appendChild(elemento("span", "feixe__nucleo"));
  for (let i = 0; i < 7; i += 1) {
    const faisca = elemento("i", "feixe__faisca");
    faisca.style.setProperty("--x", `${18 + Math.random() * 64}%`);
    faisca.style.setProperty("--atraso", `${(Math.random() * 0.7).toFixed(2)}s`);
    feixe.appendChild(faisca);
  }
  elPeoes.appendChild(feixe);
  return feixe;
}

function apagarFeixe(feixe) {
  feixe.classList.add("feixe--apagando");
  setTimeout(() => feixe.remove(), MS_FEIXE + 40);
}

/** O feixe de luz desce no portal e leva o peão para cima; na casa
    sorteada, outro feixe o traz de volta para o chão. */
async function atravessarPortal(peao, casaDoPortal, destino) {
  const assento = Number(peao.dataset.assento || 0);
  peao.classList.remove("peao--andando");

  const entrada = acenderFeixe(casaDoPortal, assento);
  som.tocar("portal");
  await espera(MS_FEIXE);
  peao.classList.add("peao--portal");
  await espera(MS_PORTAL);
  apagarFeixe(entrada);

  teleportarPeao(peao, destino);
  const saida = acenderFeixe(destino, assento);
  som.tocar("teleporte");
  await espera(MS_FEIXE);
  peao.classList.replace("peao--portal", "peao--saindo-do-portal");
  await espera(MS_PORTAL);
  peao.classList.remove("peao--saindo-do-portal");
  desenho.destacar(destino);
  apagarFeixe(saida);
}

/** Pula de casa em casa até o destino — com o portal, em dois trechos. */
async function andarPeao({ jogador_id, de, passos, para, portal }) {
  const peao = peaoDe(jogador_id);
  if (!peao || !tabuleiro) return;

  const total = tabuleiro.casas.length;
  const destino = para ?? (de - (passos % total) + total) % total;
  if (!guardado.animacoes()) {
    colocarPeao(peao, destino);
    peao.classList.remove("peao--andando");
    desenho.destacar(destino);
    return;
  }

  if (portal) {
    await pular(peao, de, portal.apos, total);
    await atravessarPortal(peao, portal.casa, portal.destino);
    await pular(peao, portal.destino, passos - portal.apos, total);
  } else {
    await pular(peao, de, passos, total);
  }
  peao.classList.remove("peao--andando");
  desenho.destacar(destino);
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

    // A bandeira na cor do jogador é a mesma que ele finca nos terrenos
    // dele: é o que liga a cor do tabuleiro a esta pessoa.
    const terrenos = elemento("span", "cartao__terrenos");
    terrenos.title = "Terrenos";
    terrenos.append(elemento("span", "cartao__bandeira"), elemento("span", "cartao__terrenos-total"));

    const nome = elemento("div", "cartao__nome");
    nome.append(
      elemento("span", "cartao__ordem", `${i + 1}º`),
      elemento("span", "cartao__texto", jogador.nome),
      elemento("span", "cartao__eu", "você"),
      elemento("span", "cartao__preso", "preso"),
      terrenos,
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

  const terrenosDe = new Map();
  for (const { dono } of Object.values(estado.propriedades || {})) {
    terrenosDe.set(dono, (terrenosDe.get(dono) || 0) + 1);
  }

  for (const jogador of estado.jogadores) {
    const cartao = elJogadores.querySelector(`.cartao[data-jogador="${jogador.jogador_id}"]`);
    if (!cartao) continue;
    cartao.classList.toggle("cartao--da-vez", jogador.jogador_id === estado.vez.jogador_id && estado.fase !== "encerrada");
    cartao.classList.toggle("cartao--eu", jogador.sou_eu);
    cartao.classList.toggle("cartao--fora", jogador.falido);
    cartao.classList.toggle("cartao--preso", jogador.preso > 0 && !jogador.falido);
    // Com o número correndo (`reagirAoDinheiro`), quem escreve é a contagem.
    const valor = cartao.querySelector(".cartao__valor");
    if (!contando(valor)) valor.textContent = jogador.falido ? (jogador.abandonou ? "SAIU" : "FALIU") : reais(jogador.caixa);
    cartao.querySelector(".cartao__terrenos-total").textContent = String(terrenosDe.get(jogador.jogador_id) || 0);
  }
}

// --- botão JOGAR e a situação da mesa ------------------------------------

/** O que o aviso diz em cada decisão: [para quem decide, para quem espera]. */
const FRASES_DA_FASE = {
  decidindo_compra: ["Escolha se deseja comprar o terreno", (n) => `${n} está decidindo uma compra`],
  decidindo_compra_jogador: ["Você caiu numa propriedade. Decida se deseja comprar", (n) => `${n} caiu numa propriedade e está decidindo se compra`],
  decidindo_melhoria: ["Decida se quer construir mais um andar", (n) => `${n} está decidindo se constrói mais um andar`],
  liquidando_para_aluguel: ["Venda uma propriedade para pagar o aluguel", (n) => `${n} está vendendo uma propriedade para pagar o aluguel`],
  decidindo_coringa: ["Arrisque ou deixe quieto na Casa Coringa", (n) => `${n} está decidindo se arrisca na Casa Coringa`],
  decidindo_reconstrucao: ["Escolha uma propriedade para reformar com desconto", (n) => `${n} está escolhendo uma reforma`],
  escolhendo_prejuizo: ["Escolha a propriedade que o líder perde", (n) => `${n} está escolhendo o golpe da Casa do Prejuízo`],
  decidindo_bonus_banco: ["Venda uma propriedade ao banco com bônus, ou passe", (n) => `${n} pode vender ao banco com bônus`],
  leiloando: ["Seu leilão está aberto: espere os lances", (n) => `${n} está leiloando uma propriedade`],
};

function mensagemDoFim() {
  const vencedores = estado.jogadores.filter((jogador) => estado.vencedores?.includes(jogador.jogador_id));
  if (estado.motivo_fim === "tempo" && vencedores.length > 1) {
    return `Tempo! Empate: ${vencedores.map((j) => j.nome).join(", ")}`;
  }
  if (vencedores.length === 1) return `Fim de partida — ${vencedores[0].nome} venceu`;
  return "A partida acabou.";
}

function pintarJogar() {
  const minha = estado.vez.sou_eu && !espectador;
  const encerrada = estado.fase === "encerrada";
  const podeRolar = minha && estado.fase === "aguardando_rolagem";
  // Depois do fim, o JOGAR vira o caminho de volta para o pódio.
  botaoJogar.textContent = encerrada ? "Pódio" : "Jogar";
  botaoJogar.disabled = encerrada ? false : !podeRolar || ocupado;
  document.querySelector(".jogar").classList.toggle("jogar--minha-vez", podeRolar && !ocupado);
  botaoVenderBonus.hidden = !(podeRolar && estado.pode_vender_no_bonus);
  botaoVenderBonus.disabled = ocupado;
  botaoLeiloar.hidden = !(podeRolar && estado.leilao_disponivel?.pode);
  // No meio de uma decisão a janela dela cobre o botão de baixo: o leilão
  // aparece dentro da própria janela.
  const leiloarNaDecisao = minha && !encerrada && !podeRolar && estado.fase !== "leiloando"
    && Boolean(estado.leilao_disponivel?.pode) && !leilaoNaMao;
  for (const botao of botoesLeiloarNaDecisao) {
    botao.hidden = !leiloarNaDecisao;
    botao.disabled = ocupado;
  }
  pintarModoDev(podeRolar);
  botaoLeiloar.disabled = ocupado;
  botaoVerLeilao.hidden = !(estado.fase === "leiloando" && leilaoEscondido());

  let mensagem;
  if (resumo && Date.now() < resumo.ate) {
    mensagem = resumo.texto;
  } else if (encerrada) {
    resumo = null;
    mensagem = mensagemDoFim();
  } else if (FRASES_DA_FASE[estado.fase]) {
    resumo = null;
    const [minhaFrase, deOutro] = FRASES_DA_FASE[estado.fase];
    mensagem = minha ? minhaFrase : deOutro(estado.vez.nome);
  } else {
    resumo = null;
    mensagem = podeRolar ? "Role os dados e faça sua jogada" : `Esperando ${estado.vez.nome} jogar`;
  }
  if (espectador && !encerrada) mensagem = `Assistindo · ${mensagem}`;

  const restante = segundosRestantes();
  if (restante !== null && !encerrada && estado.fase !== "sorteio_ordem") {
    mensagem += ` · ${formatarTempo(restante)}`;
  }
  elAviso.textContent = mensagem;
  pintarSituacao();
}

/** Os chips do alto: relógio da partida, rodada e Coletor. */
function pintarSituacao() {
  const encerrada = estado.fase === "encerrada";
  const restante = segundosPartidaRestantes();
  const ultima = estado.encerrar_apos_rodada != null;
  elChipTempo.hidden = !encerrada && restante === null && !ultima;
  elChipTempoValor.textContent = encerrada ? "Fim" : ultima ? "Última rodada" : formatarTempo(restante ?? 0);
  elChipTempo.classList.toggle("chip--alerta", !encerrada && (ultima || (restante !== null && restante <= 60)));
  elChipRodada.textContent = `Rodada ${estado.rodada}`;
  elChipColetorValor.textContent = reais(estado.coletor);
}

/** O evento temático da rodada no chip, e a região do Bônus do banco acesa. */
function pintarEvento() {
  const evento = estado.evento;
  elEventoChip.hidden = !evento;
  if (evento) {
    elEventoChipNome.textContent = evento.nome;
    elEventoChipTexto.textContent = evento.resumo || evento.texto;
    elEventoChip.title = `${evento.texto} (clique para ver de novo)`;
  }
  const regiao = evento?.tipo === "bonus_do_banco" ? evento.regiao : [];
  const assinatura = regiao.join(",");
  if (assinatura !== assinaturaDaRegiao) {
    desenho.marcarRegiao(regiao);
    assinaturaDaRegiao = assinatura;
  }
}

function segundosRestantes() {
  if (prazoLocalMs == null) return null;
  return Math.max(0, Math.ceil((prazoLocalMs - performance.now()) / 1000));
}

function segundosPartidaRestantes() {
  if (prazoPartidaLocalMs == null) return null;
  return Math.max(0, Math.ceil((prazoPartidaLocalMs - performance.now()) / 1000));
}

function textoDoPrazo(rotulo) {
  const restante = segundosRestantes();
  return restante === null ? "Sem limite de tempo" : `${rotulo}: ${formatarTempo(restante)}`;
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
    toast(jogador.abandonou ? `${jogador.nome} saiu da partida.` : `${jogador.nome} faliu e foi eliminado.`, "erro");
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
  som.tocar(estado.vez.sou_eu ? "vez" : "vento");
}

/* O dinheiro de cada um, comparado com o estado anterior.

   Não importa o motivo — compra, aluguel, casa do ganho: a tela só vê o
   caixa mudar, e conta a diferença. Assim cada regra nova de dinheiro que
   o motor ganhar já chega encenada, sem mexer aqui. O som diz o motivo
   quando dá para saber: terreno novo é caixa registradora. */
function reagirAoDinheiro(antes) {
  const comprados = Object.keys(estado.propriedades || {}).filter((i) => !antes.propriedades?.[i]);
  const melhorados = Object.entries(estado.propriedades || {})
    .filter(([i, posse]) => antes.propriedades?.[i] && (posse.nivel || 0) > (antes.propriedades[i].nivel || 0))
    .map(([i]) => i);
  const animar = guardado.animacoes();
  let ganhou = false;
  let perdeu = false;
  let euMudei = 0;

  for (const jogador of estado.jogadores) {
    const estava = antes.jogadores.find((j) => j.jogador_id === jogador.jogador_id);
    const diferenca = estava ? jogador.caixa - estava.caixa : 0;
    if (!diferenca || jogador.falido) continue;

    if (diferenca > 0) ganhou = true;
    else perdeu = true;
    if (jogador.sou_eu) euMudei = diferenca;

    const cartao = elJogadores.querySelector(`.cartao[data-jogador="${jogador.jogador_id}"]`);
    if (!cartao || !animar) continue;
    flutuarDinheiro(cartao.querySelector(".cartao__caixa"), diferenca, reais);
    contarDinheiro(cartao.querySelector(".cartao__valor"), estava.caixa, jogador.caixa, reais);
  }

  // O Coletor também conta: a mesa inteira vê o pote crescer e esvaziar.
  const coletor = (estado.coletor || 0) - (antes.coletor || 0);
  if (coletor && animar) flutuarDinheiro(elChipColetor, coletor, reais);

  // O prédio brota no terreno comprado — ou ganha um andar na melhoria: a
  // casa pula e o som de obra vem logo depois da gaveta.
  for (const indice of [...comprados, ...melhorados]) desenho.destacar(Number(indice));

  if (comprados.length || melhorados.length) {
    som.tocar("caixa");
    setTimeout(() => som.tocar("construir"), 450);
  } else if (euMudei) {
    som.tocar(euMudei > 0 ? "moedas" : "perda");
  } else if (ganhou || perdeu) {
    som.tocar(ganhou ? "moedas" : "perda");
  }
}

/* --- o que as casas de evento fizeram ---------------------------------------

   O motor numera cada linha do log; o que chegou desde a última vez e é de
   casa de evento ou de evento temático abre a janela do evento
   (js/ui/anuncios.js), com uma frase de sátira de data/eventos/. O dinheiro
   já sobe do cartão do jogador sozinho — a janela conta o porquê. A
   Coringa tem encenação própria (`encenarCoringa`). */

const ANUNCIO_DO_LOG = {
  ganho: { chamada: "Casa do Ganho", titulo: "Dinheiro no bolso!", icone: "saco", tom: "bom" },
  roubo: { chamada: "Casa do Roubo", titulo: "Roubado!", icone: "ladrao", tom: "ruim" },
  coletor: { chamada: "Casa do Imposto", titulo: "Levou o Coletor!", icone: "documento", tom: "bom" },
  coletor_vazio: { chamada: "Casa do Imposto", titulo: "Cofre vazio", icone: "documento", tom: "neutro" },
  prisao: { chamada: "Prisão", titulo: "Atrás das grades", icone: "cela", tom: "ruim", som: "prisao" },
  portal: { chamada: "Casa Portal", titulo: "Teleporte!", icone: "portal", tom: "neutro" },
  easter_egg: { chamada: "Surpresa no caminho", titulo: "Que distração...", icone: "interrogacao", tom: "ruim" },
  prejuizo: { chamada: "Casa do Prejuízo", titulo: "Golpe no líder", icone: "prejuizo", tom: "ruim" },
  reconstrucao: { chamada: "Casa da Reconstrução", titulo: "Obra na vila", icone: "capacete", tom: "neutro" },
  bonus_banco: { chamada: "Bônus do banco", titulo: "Vendeu com bônus", icone: "saco", tom: "bom" },
  morro: { chamada: "Bônus do Morro", titulo: "Dono do Morro", icone: "saco", tom: "bom" },
  // O leilão que abre e o que fecha têm janela própria (js/modais/leilao.js).
  leilao_cancelado: { chamada: "Leilão", titulo: "Leilão cancelado", icone: "martelo", tom: "neutro" },
};

const ICONE_DO_EVENTO = {
  colheita_ruim: "arvore",
  baile_na_vila: "balao",
  final_de_ano: "trofeu",
  presidente: "coroa_cheia",
  bonus_do_banco: "saco",
};

/** Os eventos que valem a rodada inteira, e não só na hora em que caem. */
const EVENTO_DA_RODADA = new Set(["final_de_ano", "bonus_do_banco"]);

/** Uma frase da lista, escolhida por um número que a mesa inteira tem igual
    (a linha do log, a rodada): todo mundo lê a mesma piada. */
const fraseDe = (lista, semente) => (lista?.length ? lista[Math.abs(semente) % lista.length] : undefined);

function anunciarEvento(evento) {
  if (!evento) return;
  anunciar({
    chamada: evento.rodada ? `Evento da rodada ${evento.rodada}` : "Evento na vila",
    titulo: evento.nome,
    frase: fraseDe(frases.tematicos[evento.tipo], evento.rodada ?? 0),
    texto: evento.texto,
    nota: EVENTO_DA_RODADA.has(evento.tipo) ? "Vale até o fim desta rodada." : undefined,
    icone: ICONE_DO_EVENTO[evento.tipo] || "trofeu",
    tom: "evento",
    duracao: 8000,
    aoMostrar: () => som.tocar("evento"),
  });
}

/** Aluguel pago: a janela conta do ponto de vista de quem olha — quem pagou
    vê em vermelho, quem recebeu em verde, o resto da mesa em roxo. */
function anunciarAluguel(linha) {
  const dados = linha.dados || {};
  const pagador = estado.jogadores.find((j) => j.jogador_id === linha.jogador_id);
  const dono = estado.jogadores.find((j) => j.jogador_id === dados.dono_id);
  const casa = tabuleiro.casas[dados.casa];
  const paguei = Boolean(pagador?.sou_eu);
  const recebi = Boolean(dono?.sou_eu);
  // Linha antiga, sem os dados: o texto do motor serve como está.
  const texto = pagador && dono && dados.valor != null
    ? `${paguei ? "Você" : pagador.nome} pagou ${reais(dados.valor)} de aluguel a ${recebi ? "você" : dono.nome}${casa ? ` por ${casa.nome}` : ""}.`
    : linha.texto;
  const motivos = [];
  if (dados.morro) motivos.push(`bônus do Morro de ${dono?.nome || "quem cobrou"} (${vezes(dados.morro)})`);
  if (dados.final_de_ano) motivos.push(`final de ano (+${porcento(dados.final_de_ano)})`);
  anunciar({
    chamada: casa ? `Aluguel · ${casa.nome}` : "Aluguel",
    titulo: paguei ? "Você pagou aluguel" : recebi ? "Aluguel no bolso!" : "Aluguel pago",
    frase: fraseDe(frases.casas.aluguel, linha.n ?? 0),
    texto,
    nota: motivos.length ? `Mais caro por causa do ${motivos.join(" e do ")}.` : undefined,
    icone: recebi ? "saco" : "documento",
    tom: paguei ? "ruim" : recebi ? "bom" : "neutro",
  });
}

function anunciarNovidades(primeiraVez) {
  const novas = estado.log.filter((linha) => (linha.n ?? 0) > ultimoLogVisto);
  ultimoLogVisto = Math.max(ultimoLogVisto, ...estado.log.map((linha) => linha.n ?? 0));
  // Na primeira pintura tudo já é velho: quem acabou de abrir a tela não
  // precisa ver de novo o que aconteceu antes de chegar.
  if (primeiraVez) return;

  for (const linha of novas) {
    if (linha.tipo === "evento_tematico") {
      // O texto da linha é "Nome! descrição": o chip tem os dois separados.
      const evento = estado.evento && linha.texto.startsWith(estado.evento.nome)
        ? estado.evento
        : { nome: "Evento na vila", texto: linha.texto };
      anunciarEvento(evento);
      continue;
    }
    if (linha.tipo === "aluguel") {
      anunciarAluguel(linha);
      continue;
    }
    if (linha.tipo === "dev") {
      // Trapaça às claras: a mesa inteira fica sabendo.
      toast(linha.texto, "ok");
      continue;
    }
    const modelo = ANUNCIO_DO_LOG[linha.tipo];
    if (!modelo) continue;
    anunciar({
      chamada: modelo.chamada,
      titulo: modelo.titulo,
      frase: fraseDe(frases.casas[linha.tipo], linha.n ?? 0),
      texto: linha.texto,
      icone: modelo.icone,
      tom: modelo.tom,
      aoMostrar: modelo.som ? () => som.tocar(modelo.som) : undefined,
    });
  }
}

/** A Coringa decidindo: o "?" gira com o tambor antes de o estado novo
    entrar — para quem arriscou e para a mesa inteira. O resultado aparece
    depois, junto com o dinheiro (`revelarCoringa`). */
async function encenarCoringa(resposta) {
  const resultado = resposta.partida.ultimo_coringa;
  if (!resultado || resultado.n <= ultimoCoringaVisto) return;
  ultimoCoringaVisto = resultado.n;
  coringaParaRevelar = resultado;
  if (!resultado.arriscou || !guardado.animacoes()) return;

  const quem = resposta.partida.jogadores.find((j) => j.jogador_id === resultado.jogador_id);
  await anunciar({
    chamada: "Casa Coringa",
    titulo: "Valendo...",
    texto: `${nomeDe(quem)} arriscou com ${porcento(resultado.chance)} de chance...`,
    icone: "interrogacao",
    tom: "suspense",
    duracao: MS_SUSPENSE,
    aoMostrar: () => som.tocar("suspense"),
  });
}

function revelarCoringa() {
  const resultado = coringaParaRevelar;
  coringaParaRevelar = null;
  if (!resultado) return;
  const quem = estado.jogadores.find((j) => j.jogador_id === resultado.jogador_id);
  const nome = nomeDe(quem);
  const comum = { chamada: "Casa Coringa", duracao: 4000 };
  if (!resultado.arriscou) {
    anunciar({
      ...comum,
      titulo: "Deixou quieto",
      frase: fraseDe(frases.casas.coringa_nao_arriscou, resultado.n),
      texto: `${nome} preferiu não arriscar.`,
      icone: "interrogacao",
      tom: "neutro",
    });
  } else if (resultado.ganhou) {
    anunciar({
      ...comum,
      titulo: "Ganhou!",
      frase: fraseDe(frases.casas.coringa_ganhou, resultado.n),
      texto: `${nome} levou ${reais(resultado.valor)}.`,
      icone: "saco",
      tom: "bom",
    });
  } else {
    anunciar({
      ...comum,
      titulo: "Perdeu!",
      frase: fraseDe(frases.casas.coringa_perdeu, resultado.n),
      texto: `${nome} perdeu ${reais(resultado.valor)}.`,
      icone: "prejuizo",
      tom: "ruim",
    });
  }
}

// --- aplicar estado -----------------------------------------------------

function aplicar(resposta) {
  const primeiraVez = !tabuleiro;
  const antes = estado;
  estado = resposta.partida;
  espectador = Boolean(resposta.espectador);
  regras = resposta.regras || regras;
  valores = regras.casas || valores;
  devDisponivel = Boolean(resposta.modo_dev);
  cosmeticos = resposta.cosmeticos || cosmeticos;
  if (resposta.recompensa != null) ultimaRecompensa = resposta.recompensa;
  prazoLocalMs = estado.segundos_restantes == null
    ? null
    : performance.now() + estado.segundos_restantes * 1000;
  prazoPartidaLocalMs = estado.segundos_partida_restantes == null
    ? null
    : performance.now() + estado.segundos_partida_restantes * 1000;
  if (primeiraVez) {
    tabuleiro = resposta.tabuleiro;
    desenharTabuleiro(tabuleiro, estado.propriedades);
    pintarModoEspectador();
  } else if (assinaturaPropriedades(estado.propriedades) !== assinaturaDasPropriedades) {
    desenho.atualizarPropriedades(estado.propriedades);
    assinaturaDasPropriedades = assinaturaPropriedades(estado.propriedades);
  }

  // Na primeira pintura, o lance que já estava no estado não é encenado:
  // seria repetir uma jogada que aconteceu antes de eu abrir a tela.
  if (primeiraVez) {
    ultimoLanceVisto = estado.ultimo_movimento?.lance ?? 0;
    ultimoCoringaVisto = estado.ultimo_coringa?.n ?? 0;
    ultimoLeilaoVisto = estado.ultimo_leilao?.n ?? 0;
  }

  // Remonta os peões quando alguém entra ou sai da mesa.
  const agora = ativos().map((j) => j.jogador_id).join(",");
  if (primeiraVez || agora !== assinaturaDosPeoes) montarPeoes();

  posicionarPeoes();
  pintarCartoes();
  if (antes) reagirAoDinheiro(antes);
  pintarEvento();
  pintarJogar();
  atualizarModalCompra();
  atualizarModalLiquidacao();
  atualizarModalDecisao();
  atualizarLeilao(antes);

  if (antes) avisarQuemSaiu(antes);
  anunciarNovidades(primeiraVez);
  revelarCoringa();
  // Abrir a tela no meio da partida não repete a abertura.
  if (!ordemMostrada && estado.sorteio?.length && !estado.ultimo_movimento && !espectador) mostrarOrdem();
  ordemMostrada = ordemMostrada || Boolean(estado.ultimo_movimento) || espectador;
  anunciarVez();
  talvezComemorar(primeiraVez);
  ajustarRitmoDaConsulta();
}

/* O leilão abre para a mesa inteira, não só para quem tem a vez: a janela
   aparece com o martelo, cada lance novo toca para todo mundo, e o
   resultado sobe quando o relógio fecha. */
function atualizarLeilao(antes) {
  const leilao = estado.fase === "leiloando" ? estado.leilao : null;
  if (leilao && leilao.n !== ultimoLeilaoAberto) {
    ultimoLeilaoAberto = leilao.n;
    fecharFimDoLeilao();
    som.tocar("martelo");
  } else if (leilao && leilao.lances.length > (antes?.leilao?.lances.length ?? 0)) {
    som.tocar("lance");
  }
  pintarLeilao({ estado, tabuleiro, eu: euNaMesa(), espectador, regras });

  const resultado = estado.ultimo_leilao;
  if (resultado && resultado.n > ultimoLeilaoVisto) {
    ultimoLeilaoVisto = resultado.n;
    mostrarFimDoLeilao({ resultado, estado, tabuleiro, eu: euNaMesa(), regras });
    som.tocar("arrematado");
  }
}

function pintarModoEspectador() {
  document.body.classList.toggle("modo-espectador", espectador);
  elChipEspectador.hidden = !espectador;
  campoChat.disabled = espectador;
  formularioChat.querySelector("button").disabled = espectador;
  if (espectador) campoChat.placeholder = "Quem assiste só lê o chat";
}

/** A partida acabou: as janelas de decisão fecham e o pódio sobe. Quem
    abre a tela de uma partida já encerrada vê o pódio na hora. */
function talvezComemorar(primeiraVez) {
  if (estado.fase !== "encerrada" || fimMostrado) return;
  fimMostrado = true;
  // O estado não muda mais; o chat continua.
  if (consulta) clearInterval(consulta);
  consulta = null;
  fecharDecisao();
  fecharLeilao();
  fecharFimDoLeilao();
  limparAnuncios();
  modalCompra.hidden = true;
  modalLiquidacao.hidden = true;
  setTimeout(abrirPodio, primeiraVez ? 0 : ms(1400));
}

function abrirPodio() {
  mostrarFimDePartida({ estado, recompensa: ultimaRecompensa, espectador, corDe: corDoJogador });
}

/* A mesma janela serve para as três decisões de "pagar ou não" ao parar
   numa propriedade: terreno livre, casa de outro jogador e melhoria na
   própria casa. Só os textos e a rota mudam. */
function atualizarModalCompra() {
  const melhoria = estado?.fase === "decidindo_melhoria" ? estado.melhoria_pendente : null;
  const pendente = ["decidindo_compra", "decidindo_compra_jogador"].includes(estado?.fase)
    ? estado.compra_pendente
    : melhoria;
  const minhaDecisao = Boolean(pendente && estado.vez.sou_eu && !espectador);
  if (minhaDecisao && modalCompra.hidden) som.tocar("oferta");
  modalCompra.hidden = !minhaDecisao;
  if (!minhaDecisao) {
    vendedorCompra.hidden = true;
    aluguelCompra.hidden = true;
    return;
  }

  const casa = tabuleiro.casas[pendente.casa];
  const eu = euNaMesa();
  tempoCompra.textContent = textoDoPrazo("Tempo para decidir");

  if (melhoria) {
    chamadaCompra.textContent = melhoria.origem === "compra" ? "Construir agora?" : "Você caiu na sua propriedade";
    tituloCompra.textContent = casa?.nome || "Propriedade";
    vendedorCompra.hidden = false;
    vendedorCompra.textContent = `Nível ${melhoria.nivel} → ${melhoria.nivel + 1}`;
    precoCompra.textContent = `Melhoria: ${reais(melhoria.custo)}`;
    aluguelCompra.hidden = false;
    aluguelCompra.textContent = `Aluguel passa de ${reais(melhoria.aluguel_atual)} para ${reais(melhoria.aluguel_novo)}`;
    saldoCompra.textContent = `Seu caixa: ${reais(eu?.caixa)} · após melhorar: ${reais((eu?.caixa || 0) - melhoria.custo)}`;
    botoesCompra[0].textContent = "Deixar como está";
    botoesCompra[1].textContent = "Melhorar";
    return;
  }

  const compraDeJogador = pendente.tipo === "jogador";
  const vendedor = compraDeJogador
    ? estado.jogadores.find((jogador) => jogador.jogador_id === pendente.vendedor_id)
    : null;
  chamadaCompra.textContent = compraDeJogador ? "Você caiu numa propriedade" : "Terreno disponível";
  tituloCompra.textContent = casa?.nome || "Terreno";
  vendedorCompra.hidden = !compraDeJogador;
  vendedorCompra.textContent = vendedor ? `Propriedade de ${vendedor.nome}` : "";
  precoCompra.textContent = `Preço: ${reais(pendente.preco)}`;
  aluguelCompra.hidden = !compraDeJogador;
  aluguelCompra.textContent = compraDeJogador
    ? `Se não comprar, pagará ${reais(pendente.aluguel)} de aluguel`
    : "";
  saldoCompra.textContent = `Seu caixa: ${reais(eu?.caixa)} · após comprar: ${reais((eu?.caixa || 0) - pendente.preco)}`;
  botoesCompra[0].textContent = compraDeJogador ? "Recusar e pagar aluguel" : "Deixar passar";
  botoesCompra[1].textContent = "Comprar";
}

/* Coringa, Reconstrução, Prejuízo e Bônus do banco: cada casa monta a
   própria pergunta (js/modais/), e a janela é uma só. Só abre para quem
   decide; a mesa lê no aviso quem está decidindo o quê. */
function atualizarModalDecisao() {
  const minha = Boolean(estado?.vez.sou_eu && !espectador);
  const contexto = { estado, tabuleiro, eu: euNaMesa(), codigo };
  let decisao = null;
  // A escolha do leilão passa na frente: aberta no meio de uma decisão, ela
  // cobre a decisão, que volta quando a escolha fecha ou o leilão acaba.
  if (minha && leilaoNaMao && estado.fase !== "leiloando" && estado.leilao_disponivel?.pode) {
    decisao = escolhaDoLeilao({ ...contexto, regras });
  } else if (minha && estado.fase === "decidindo_coringa" && estado.coringa_pendente) {
    decisao = decisaoDoCoringa(estado.coringa_pendente, codigo);
  } else if (minha && estado.fase === "decidindo_reconstrucao" && estado.reconstrucao_pendente) {
    decisao = decisaoDaReconstrucao(estado.reconstrucao_pendente, contexto);
  } else if (minha && estado.fase === "escolhendo_prejuizo" && estado.prejuizo_pendente) {
    decisao = decisaoDoPrejuizo(estado.prejuizo_pendente, contexto);
  } else if (minha && estado.fase === "decidindo_bonus_banco") {
    decisao = decisaoDoBonus({ ...contexto, naDecisao: true });
  } else if (minha && bonusNaMao && estado.fase === "aguardando_rolagem" && estado.pode_vender_no_bonus) {
    decisao = decisaoDoBonus({ ...contexto, naDecisao: false });
  } else {
    bonusNaMao = false;
  }
  // A escolha do leilão só sobrevive enquanto ainda dá para leiloar.
  if (!(minha && estado?.fase !== "leiloando" && estado?.leilao_disponivel?.pode)) leilaoNaMao = false;

  if (!decisao) {
    if (decisaoAberta()) fecharDecisao();
    return;
  }
  if (!decisaoAberta() && !bonusNaMao && !leilaoNaMao) som.tocar("oferta");
  abrirDecisao(decisao);
  definirTempoDaDecisao(textoDoPrazo("Tempo para decidir"));
}

definirExecutor(async (acao) => {
  if (ocupado) return;
  ocupado = true;
  pintarJogar();
  som.tocar("clique");
  try {
    const resposta = await acao();
    // "Voltar" do Bônus do banco ou do leilão aberto na mão: só fecha.
    if (!resposta) {
      bonusNaMao = false;
      leilaoNaMao = false;
      fecharDecisao();
      return;
    }
    fecharDecisao();
    await encenarCoringa(resposta);
    aplicar(resposta);
  } catch (erro) {
    som.tocar("erro");
    toast(erro.message, "erro");
  } finally {
    ocupado = false;
    if (estado) {
      pintarJogar();
      atualizarModalDecisao();
    }
  }
});

botaoVenderBonus.addEventListener("click", () => {
  if (ocupado) return;
  som.tocar("clique");
  leilaoNaMao = false;
  bonusNaMao = true;
  atualizarModalDecisao();
});

/** Abre a escolha do que leiloar: antes de rolar, pelo botão embaixo do
    JOGAR, ou no meio de uma decisão, pelo botão dentro da janela dela. */
function abrirEscolhaDoLeilao() {
  if (ocupado) return;
  som.tocar("clique");
  bonusNaMao = false;
  leilaoNaMao = true;
  atualizarModalDecisao();
  pintarJogar();
}

botaoLeiloar.addEventListener("click", abrirEscolhaDoLeilao);
for (const botao of botoesLeiloarNaDecisao) botao.addEventListener("click", abrirEscolhaDoLeilao);

botaoVerLeilao.addEventListener("click", () => {
  som.tocar("clique");
  reabrirLeilao();
  pintarJogar();
});

document.querySelector("#leilao-esconder").addEventListener("click", () => {
  som.tocar("voltar");
  esconderLeilao();
  pintarJogar();
});

/* O lance não trava a mesa como as outras ações: o relógio do leilão
   continua andando e as consultas seguem chegando. A geração descarta a
   consulta que saiu antes do lance e voltaria depois dele, sem ele. */
definirLanceDoLeilao(async (valor) => {
  geracao += 1;
  try {
    const resposta = await api.darLance(codigo, valor);
    geracao += 1;
    aplicar(resposta);
  } catch (erro) {
    som.tocar("erro");
    toast(erro.message, "erro");
    atualizar();
  }
});

/* --- informação: casa clicada, regras e ranking ----------------------------

   As três usam o mesmo painel. Os números saem do envelope do servidor
   (`regras.casas`): refazer a conta aqui deixaria a tela explicando um valor
   e o motor cobrando outro. */

const NOMES_TIPOS_CASA = {
  propriedade: "Propriedade",
  neutra: "Casa neutra",
  inicial: "Início",
  ganho: "Casa do Ganho",
  roubo: "Casa do Roubo",
  coletor: "Coletor de Impostos",
  coringa: "Casa Coringa",
  portal: "Casa Portal",
  prisao: "Prisão",
  reconstrucao: "Casa da Reconstrução",
  prejuizo: "Casa do Prejuízo",
};

function descricaoDaCasa(tipo) {
  const v = valores;
  switch (tipo) {
    case "inicial":
      return `Ponto de partida. Quem passa por aqui recebe ${reais(v.salario)} de salário.`;
    case "ganho":
      return `Você roubou: ganha ${reais(v.ganho)} na hora.`;
    case "roubo":
      return `Você foi roubado: perde ${reais(v.roubo)} na hora — no máximo o que tiver em caixa.`;
    case "coletor":
      return `Junta os impostos da partida (a Casa do Prejuízo e o imposto do leilão mandam dinheiro para cá). Quem parar aqui leva tudo. Agora: ${reais(estado?.coletor)}.`;
    case "coringa":
      return `Arrisca ou deixa quieto: ganha ${reais(v.coringa_ganho)} ou perde até ${reais(v.coringa_perda)}. Quem está atrás na mesa tem mais chance de ganhar.`;
    case "portal":
      return v.portal_ao_passar
        ? "Quem passa por aqui é teleportado para uma casa sorteada e anda dali os passos que faltavam."
        : "Quem para aqui é teleportado para uma casa sorteada do tabuleiro.";
    case "prisao":
      return `Quem para aqui perde ${v.prisao_rodadas > 1 ? `as próximas ${v.prisao_rodadas} vezes` : "a próxima vez"}.`;
    case "reconstrucao":
      return `Melhora uma propriedade sua com ${porcento(v.reconstrucao_desconto)} de desconto.`;
    case "prejuizo":
      return `Quem lidera a mesa perde uma propriedade média ou barata, escolhida por quem pisou; ${porcento(v.prejuizo_ao_coletor)} do valor vai para o Coletor. Sem média ou barata, o líder perde ${porcento(v.prejuizo_do_caixa)} do caixa.`;
    default:
      return "Não tem cobrança nem efeito especial.";
  }
}

function textoDoLeilao() {
  const l = regras.leilao || {};
  const quem = l.so_abaixo_de == null
    ? "Qualquer jogador"
    : `Quem está abaixo de ${porcento(l.so_abaixo_de)} da média da mesa`;
  const frequencia = (l.rodadas_entre || 1) > 1 ? `uma vez a cada ${l.rodadas_entre} rodadas` : "uma vez por rodada";
  return `${quem} pode pôr uma propriedade em leilão a qualquer momento da própria vez, até no meio de uma decisão (${frequencia}). `
    + `A mesa dá lances por ${l.segundos} segundos e o maior leva, pagando mais ${porcento(l.imposto_sobre_tabela)} `
    + `do valor de tabela de imposto para o Coletor. Sem lance, o banco compra por ${porcento(l.compra_do_banco)} do valor.`;
}

function linhaInfoCasa(rotulo, valor, nota = "") {
  const linha = elemento("p", nota ? "casa-info__linha casa-info__nota" : "casa-info__linha");
  const nome = elemento("strong", "", `${rotulo}: `);
  linha.append(nome, document.createTextNode(valor));
  return linha;
}

function abrirPainelInfo(tipo, titulo, linhas) {
  tipoCasaInfo.textContent = tipo;
  tituloCasaInfo.textContent = titulo;
  detalhesCasaInfo.replaceChildren(...linhas);
  painelCasaInfo.hidden = false;
  document.querySelector("#casa-info-fechar").focus();
}

function mostrarInfoCasa(indice) {
  const casa = tabuleiro?.casas[indice];
  if (!casa) return;

  const tipo = casa.inicio ? "inicial" : casa.tipo;
  const rotuloTipo = casa.grupo
    ? `${NOMES_TIPOS_CASA[tipo] || tipo} · ${rotuloDoGrupo(casa.grupo)}`
    : NOMES_TIPOS_CASA[tipo] || tipo;

  const detalhes = [];
  const propriedade = estado.propriedades?.[String(indice)];
  const doMorro = Boolean(casa.grupo) && casa.grupo === regras.morro?.grupo;
  if (tipo === "propriedade") {
    detalhes.push(linhaInfoCasa("Grupo", rotuloDoGrupo(casa.grupo)));
    detalhes.push(linhaInfoCasa("Preço", reais(casa.preco)));
    if (!propriedade) {
      detalhes.push(linhaInfoCasa("Situação", "Sem dono — disponível para compra quando alguém cair aqui."));
      if (doMorro) {
        detalhes.push(linhaInfoCasa("Bônus do Morro", `Casa de favela: quem junta várias cobra mais aluguel em todas (${faixasDoMorro()}).`, true));
      }
    } else {
      // Valores calculados pelo servidor: refazer a conta aqui deixaria a
      // tela discordando do motor a cada ajuste no balanceamento.
      const dono = estado.jogadores.find((j) => j.jogador_id === propriedade.dono);
      const nivel = Number(propriedade.nivel || 0);
      detalhes.push(linhaInfoCasa("Dono", dono?.nome || "Jogador"));
      detalhes.push(linhaInfoCasa("Melhorias", `${nivel} de ${propriedade.nivel_maximo} níveis`));
      detalhes.push(linhaInfoCasa("Aluguel atual", reais(propriedade.aluguel)));
      if (propriedade.morro) {
        const { casas, multiplicador } = propriedade.morro;
        const quem = dono?.sou_eu ? "Você tem" : `${dono?.nome || "O dono"} tem`;
        detalhes.push(linhaInfoCasa(
          "Bônus do Morro",
          multiplicador > 1
            ? `${quem} ${casas} casas do Morro: o aluguel de todas é multiplicado por ${vezes(multiplicador)}.`
            : `${quem} 1 casa do Morro. O bônus começa na segunda (${faixasDoMorro()}).`,
        ));
      }
      if (dono?.sou_eu && estado.leilao_disponivel) {
        const { pode, motivo } = estado.leilao_disponivel;
        detalhes.push(linhaInfoCasa(
          "Leilão",
          pode ? "Você pode leiloar agora: botão LEILOAR, embaixo do JOGAR ou dentro da janela da decisão." : motivo,
          true,
        ));
      }
      if (propriedade.custo_melhoria !== null) {
        detalhes.push(linhaInfoCasa(
          "Próxima melhoria",
          `${reais(propriedade.custo_melhoria)} · aluguel passa para ${reais(propriedade.aluguel_proximo_nivel)}`,
        ));
      }
      if (dono?.sou_eu) {
        detalhes.push(linhaInfoCasa(
          "Ao cair aqui",
          propriedade.custo_melhoria !== null
            ? "É sua: não paga aluguel e pode construir mais um andar."
            : "É sua: não paga aluguel. Já está no nível máximo.",
        ));
      } else {
        detalhes.push(linhaInfoCasa("Ao cair aqui", `Pode comprar por ${reais(propriedade.preco_compra)} ou pagar o aluguel se recusar.`));
      }
    }
    if (casa.easter_egg) detalhes.push(linhaInfoCasa("Curiosidade", casa.easter_egg, true));
  } else {
    detalhes.push(linhaInfoCasa("O que acontece", descricaoDaCasa(tipo)));
    if (casa.easter_egg) detalhes.push(linhaInfoCasa("Curiosidade", casa.easter_egg, true));
  }
  if (estado.evento?.tipo === "bonus_do_banco" && estado.evento.regiao?.includes(indice)) {
    detalhes.push(linhaInfoCasa("Bônus do banco", "Esta casa está na região sorteada nesta rodada."));
  }

  abrirPainelInfo(rotuloTipo, casa.nome, detalhes);
}

function mostrarRegras() {
  const tipos = ["inicial", "ganho", "roubo", "coletor", "coringa", "portal", "prisao", "reconstrucao", "prejuizo", "neutra"];
  abrirPainelInfo("Regras rápidas", "Como a vila funciona", [
    linhaInfoCasa("Vitória", "Quando o tempo acaba, a rodada é concluída e vence o maior patrimônio: caixa mais o valor das propriedades e melhorias. Se todos os outros falirem antes, acaba na hora."),
    linhaInfoCasa("Propriedade", "Compre ao parar num terreno livre. Na casa de outro jogador, compre dele pelo valor investido ou pague aluguel. Na sua, construa mais um andar."),
    linhaInfoCasa("Bônus do Morro", `As casas de favela (${rotuloDoGrupo(regras.morro?.grupo)}) cobram mais aluguel quanto mais delas o mesmo dono tiver, em todas: ${faixasDoMorro()}.`),
    linhaInfoCasa("Leilão", textoDoLeilao()),
    ...tipos.map((tipo) => linhaInfoCasa(NOMES_TIPOS_CASA[tipo], descricaoDaCasa(tipo))),
    linhaInfoCasa(
      "Eventos temáticos",
      "No começo de uma rodada pode acontecer: A colheita foi ruim, Baile na vila, Evento de final de ano, O Presidente passou aqui ou Bônus do banco. Eles valem para a mesa inteira.",
      true,
    ),
  ]);
}

function mostrarRanking() {
  const ordem = [...estado.jogadores].sort((a, b) => Number(a.falido) - Number(b.falido) || b.patrimonio - a.patrimonio);
  abrirPainelInfo("Ranking", "Quem lidera agora", ordem.map((jogador, i) => {
    if (jogador.falido) return linhaInfoCasa(`${i + 1}º ${jogador.nome}`, jogador.abandonou ? "saiu da partida" : "faliu", true);
    const casas = Object.values(estado.propriedades || {}).filter((p) => p.dono === jogador.jogador_id).length;
    return linhaInfoCasa(
      `${i + 1}º ${jogador.nome}${jogador.sou_eu ? " (você)" : ""}`,
      `${reais(jogador.patrimonio)} de patrimônio · ${reais(jogador.caixa)} em caixa · ${casas} propriedade(s)`,
    );
  }));
}

function fecharInfoCasa() {
  painelCasaInfo.hidden = true;
}

elSvg.addEventListener("click", (evento) => {
  const casa = evento.target.closest?.(".casa__alvo-clique[data-i]");
  if (!casa || !elSvg.contains(casa)) return;
  casa.blur();
  mostrarInfoCasa(Number(casa.dataset.i));
});

elSvg.addEventListener("keydown", (evento) => {
  if (evento.key !== "Enter" && evento.key !== " ") return;
  const casa = evento.target.closest?.(".casa__alvo-clique[data-i]");
  if (!casa || !elSvg.contains(casa)) return;
  evento.preventDefault();
  mostrarInfoCasa(Number(casa.dataset.i));
});

document.querySelector("#casa-info-fechar").addEventListener("click", fecharInfoCasa);
painelCasaInfo.addEventListener("click", (evento) => {
  if (evento.target === painelCasaInfo) fecharInfoCasa();
});

elEventoChip.addEventListener("click", () => anunciarEvento(estado?.evento));

function atualizarModalLiquidacao() {
  const pendente = estado?.fase === "liquidando_para_aluguel" ? estado.aluguel_pendente : null;
  const jogador = euNaMesa();
  const minhaDecisao = Boolean(pendente && estado.vez.sou_eu && jogador && !jogador.falido && !espectador);
  modalLiquidacao.hidden = !minhaDecisao;
  if (!minhaDecisao) return;

  const casa = tabuleiro.casas[pendente.casa];
  const dono = estado.jogadores.find((item) => item.jogador_id === pendente.dono_id);
  casaLiquidacao.textContent = `Aluguel de ${casa?.nome || "propriedade"}${dono ? ` para ${dono.nome}` : ""}`;
  dividaLiquidacao.textContent = `Dívida: ${reais(pendente.divida)}`;
  caixaLiquidacao.textContent = `Seu caixa: ${reais(jogador.caixa)} · faltam ${reais(Math.max(0, pendente.divida - jogador.caixa))}`;
  const restante = segundosRestantes();
  tempoLiquidacao.textContent = restante === null ? "Resolva a dívida para continuar" : `Tempo para vender: ${formatarTempo(restante)}`;

  const propriedades = Object.entries(estado.propriedades || {})
    .filter(([, propriedade]) => propriedade.dono === jogador.jogador_id)
    .map(([indice, posse]) => ({ casa: tabuleiro.casas[Number(indice)], valor: posse.valor_banco }))
    .filter(({ casa: casaPropria }) => casaPropria?.tipo === "propriedade")
    .sort((a, b) => a.casa.i - b.casa.i);

  listaLiquidacao.replaceChildren(...propriedades.map(({ casa: propriedade, valor }) => {
    const botao = elemento(
      "button",
      "liquidacao__vender",
      `Vender ${propriedade.nome} · recebe ${reais(valor)}`,
    );
    botao.type = "button";
    botao.disabled = ocupado;
    botao.addEventListener("click", () => venderPropriedadeParaPagarAluguel(propriedade.i));
    const item = elemento("li", "liquidacao__item");
    item.appendChild(botao);
    return item;
  }));
}

/** O último segundo em que o relógio tiquetaqueou — o intervalo pode cair
    duas vezes no mesmo segundo. */
let ultimoTique = null;

setInterval(() => {
  if (!estado) return;
  pintarJogar();
  if (!modalCompra.hidden) atualizarModalCompra();
  if (!modalLiquidacao.hidden) atualizarModalLiquidacao();
  if (decisaoAberta()) definirTempoDaDecisao(textoDoPrazo("Tempo para decidir"));

  // Os últimos 5 segundos da MINHA vez tiquetaqueiam: o prazo acabando sem
  // ninguém olhar para o relógio era jogada perdida em silêncio. O leilão
  // tem relógio próprio, que tiquetaqueia para a mesa inteira.
  const restante = segundosRestantes();
  const decidindo = estado.fase === "aguardando_rolagem" || (Boolean(FRASES_DA_FASE[estado.fase]) && estado.fase !== "leiloando");
  if (estado.vez.sou_eu && !espectador && decidindo && !ocupado && restante > 0 && restante <= 5 && restante !== ultimoTique) {
    som.tocar("tique");
  }
  ultimoTique = restante;
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
    // Jogada do modo dev não tem dados: o peão só anda.
    if (!movimento.dev) await encenarDados(`${quem?.nome || "Alguém"} tirou`, movimento.dados, movimento.jogador_id);

    await andarPeao(movimento);
    await espera(MS_APOS_CHEGAR);
  } finally {
    ocupado = false;
  }
  return true;
}

// --- rolar --------------------------------------------------------------

botaoJogar.addEventListener("click", async () => {
  // Depois do fim, o JOGAR reabre o pódio.
  if (estado?.fase === "encerrada") {
    som.tocar("clique");
    abrirPodio();
    return;
  }
  if (ocupado || botaoJogar.disabled || espectador) return;
  // A janela do evento não segura a vez: rolar fecha a que estiver aberta.
  fecharAnuncio();
  ocupado = true;
  pintarJogar();
  const meuId = euNaMesa()?.jogador_id;
  // Enquanto o servidor não responde, a faixa já entra com os dados
  // rodando soltos na mão.
  if (guardado.animacoes()) abrirFaixaDosDados("Você tirou", meuId);
  som.tocar("clique");

  try {
    const resposta = await api.rolarDados(codigo);
    const movimento = resposta.partida.ultimo_movimento;
    // Marca como já visto: a consulta seguinte não repete a minha jogada.
    ultimoLanceVisto = movimento.lance;

    // 1-2. os dados assentam no valor, o total bate e a faixa sai
    await encenarDados("Você tirou", movimento.dados, meuId);

    // 3. o peão anda casa por casa (e atravessa o portal, se pisar nele)
    await andarPeao(movimento);

    // 4. um respiro para ver ONDE parou, antes da tela mudar
    await espera(MS_APOS_CHEGAR);

    // 5. e só agora o estado novo entra
    aplicar(resposta);
    contarJogada(movimento);
  } catch (erro) {
    som.tocar("erro");
    toast(erro.message, "erro");
    fecharFaixaDosDados();
    atualizar();
  } finally {
    ocupado = false;
    if (estado) pintarJogar();
  }
});

async function responderCompra(comprar) {
  if (ocupado || modalCompra.hidden) return;
  ocupado = true;
  botoesCompra.forEach((botao) => (botao.disabled = true));
  pintarJogar();
  // Comprando, o som de verdade é a caixa registradora, quando o estado
  // novo chega (`reagirAoDinheiro`); aqui é só o clique do botão.
  som.tocar(comprar ? "clique" : "voltar");
  try {
    const compraDeJogador = estado.fase === "decidindo_compra_jogador";
    let resposta;
    if (estado.fase === "decidindo_melhoria") resposta = await api.decidirMelhoria(codigo, comprar);
    else if (compraDeJogador) resposta = await api.decidirCompraPropriedade(codigo, comprar);
    else resposta = await api.decidirCompra(codigo, comprar);
    aplicar(resposta);
    if (compraDeJogador && comprar) {
      toast("Propriedade comprada. O pagamento foi para o dono anterior.", "sucesso");
    }
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

async function venderPropriedadeParaPagarAluguel(casa) {
  if (ocupado || modalLiquidacao.hidden) return;
  ocupado = true;
  pintarJogar();
  atualizarModalLiquidacao();
  som.tocar("clique");
  try {
    aplicar(await api.venderPropriedadeParaAluguel(codigo, casa));
  } catch (erro) {
    som.tocar("erro");
    toast(erro.message, "erro");
    try {
      aplicar(await api.verPartida(codigo));
    } catch {
      // A consulta periódica recupera o estado quando o servidor responder.
    }
  } finally {
    ocupado = false;
    if (estado) {
      atualizarModalLiquidacao();
      pintarJogar();
    }
  }
}

// --- abertura ------------------------------------------------------------

/* A abertura é encenada, não listada: os bonecos entram pulando com os
   dados girando no alto, cai o total de cada um, e só no fim aparecem as
   colocações — de último para primeiro, para o vencedor ser a última coisa
   que a mesa descobre. */

function montarPosto(tirada, posicao, jogador, cor) {
  const posto = elemento("div", "posto");
  posto.style.setProperty("--cor", cor);
  posto.style.setProperty("--ordem", String(posicao));
  // Cada um já joga a abertura com o dado que trouxe da loja.
  vestirDados(posto, tirada.jogador_id);

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
  for (const { posto, cubinhos, valores: dados } of postos) {
    dados.forEach((valor, i) => girarCubo(cubinhos[i], valor));
    posto.classList.add("posto--revelado");
    som.tocar("dado");
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
  som.tocar("sucesso");
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
  if (lembrar && !espectador) campoChat.focus();
}

function pintarNaoLidas() {
  contadorChat.hidden = naoLidas === 0;
  contadorChat.textContent = naoLidas > 9 ? "9+" : String(naoLidas);
  botaoChat.classList.toggle("acao--novidade", naoLidas > 0);
}

/** Mensagem nova de outro jogador com o chat fechado: acende o botão. */
function avisarMensagens(novas) {
  const eu = euNaMesa()?.jogador_id;
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

// --- modo dev ---------------------------------------------------------------

/* Trapaças de teste: /dev on no chat abre o painel, /dev off fecha. Quem
   decide se valem é o servidor (MODO_DEV em server/config.py); a tela só
   abre o painel quando ele avisa que sim. O comando não vai para a mesa,
   mas cada trapaça vai, como [dev]. */

function tratarComando(texto) {
  const comando = texto.trim().toLowerCase().match(/^\/dev\s+(on|off)$/);
  if (!comando) return false;
  if (comando[1] === "off") {
    abrirModoDev(false);
    toast("Modo dev desligado.", "ok");
  } else if (!devDisponivel) {
    som.tocar("erro");
    toast("O modo dev está desligado neste servidor.", "erro");
  } else if (espectador) {
    som.tocar("erro");
    toast("Quem assiste não usa o modo dev.", "erro");
  } else {
    abrirModoDev(true);
    toast("Modo dev ligado: caixa, ir para e andar.", "ok");
  }
  return true;
}

function abrirModoDev(aberto) {
  painelDev.hidden = !aberto;
  if (!aberto) return;
  if (!seletorCasaDev.options.length) {
    seletorCasaDev.replaceChildren(...tabuleiro.casas.map((casa) => {
      const opcao = elemento("option", "", `${casa.i} · ${casa.nome}`);
      opcao.value = String(casa.i);
      return opcao;
    }));
  }
  campoCaixaDev.value = String(euNaMesa()?.caixa ?? 0);
  pintarJogar();
}

/** Ir e Andar trocam a rolagem: só na minha vez, antes de rolar. */
function pintarModoDev(podeRolar) {
  if (painelDev.hidden) return;
  if (!devDisponivel || espectador) {
    painelDev.hidden = true;
    return;
  }
  const emAndamento = !["sorteio_ordem", "encerrada"].includes(estado.fase);
  formCaixaDev.querySelector("button").disabled = ocupado || !emAndamento;
  formIrDev.querySelector("button").disabled = ocupado || !podeRolar;
  formAndarDev.querySelector("button").disabled = ocupado || !podeRolar;
}

/** Manda a trapaça; Ir e Andar encenam o peão andando, como no JOGAR. */
async function acaoDev(pedido, anda) {
  if (ocupado) return;
  ocupado = true;
  pintarJogar();
  som.tocar("clique");
  try {
    const resposta = await pedido();
    if (anda) {
      fecharAnuncio();
      const movimento = resposta.partida.ultimo_movimento;
      ultimoLanceVisto = movimento.lance;
      await andarPeao(movimento);
      await espera(MS_APOS_CHEGAR);
      aplicar(resposta);
      contarJogada(movimento);
    } else {
      aplicar(resposta);
    }
  } catch (erro) {
    som.tocar("erro");
    toast(erro.message, "erro");
  } finally {
    ocupado = false;
    if (estado) pintarJogar();
  }
}

formCaixaDev.addEventListener("submit", (evento) => {
  evento.preventDefault();
  const valor = Number(campoCaixaDev.value);
  if (!Number.isInteger(valor) || valor < 0) {
    toast("Informe um valor inteiro, sem centavos.", "erro");
    return;
  }
  acaoDev(() => api.devCaixa(codigo, valor), false);
});

formIrDev.addEventListener("submit", (evento) => {
  evento.preventDefault();
  acaoDev(() => api.devIr(codigo, Number(seletorCasaDev.value)), true);
});

formAndarDev.addEventListener("submit", (evento) => {
  evento.preventDefault();
  const passos = Number(campoPassosDev.value);
  if (!Number.isInteger(passos) || passos < 1) {
    toast("Informe quantas casas andar.", "erro");
    return;
  }
  acaoDev(() => api.devAndar(codigo, passos), true);
});

document.querySelector("#dev-fechar").addEventListener("click", () => {
  som.tocar("voltar");
  abrirModoDev(false);
});

// --- o que recolhe: legenda e menu de opções ---------------------------------

/* A mesa limpa é o padrão: a legenda e as opções começam recolhidas, cada
   uma com o seu botão, e lembram como ficaram na partida seguinte. */

function abrirLegenda(aberta, { lembrar = true } = {}) {
  elLegenda.hidden = !aberta;
  botaoLegenda.setAttribute("aria-expanded", String(aberta));
  if (lembrar) guardado.salvarLegendaAberta(aberta);
}

function abrirMenuAcoes(aberto, { lembrar = true } = {}) {
  menuAcoes.hidden = !aberto;
  botaoMenuAcoes.setAttribute("aria-expanded", String(aberto));
  botaoMenuAcoes.classList.toggle("acao--ativa", aberto);
  if (lembrar) guardado.salvarOpcoesAbertas(aberto);
}

botaoLegenda.addEventListener("click", () => {
  som.tocar("clique");
  abrirLegenda(elLegenda.hidden);
});

botaoMenuAcoes.addEventListener("click", () => {
  som.tocar("clique");
  abrirMenuAcoes(menuAcoes.hidden);
});

// --- opções do canto ------------------------------------------------------

document.querySelector("#regras").addEventListener("click", () => {
  som.tocar("clique");
  mostrarRegras();
});

document.querySelector("#ranking").addEventListener("click", () => {
  som.tocar("clique");
  if (estado) mostrarRanking();
});

/* Os dois volumes do menu, aqui também: quem quer baixar a música no meio
   da partida não precisa abandonar a mesa. Cada controle grava a mesma
   preferência que o do menu. */
const volumesPartida = [
  {
    controle: document.querySelector("#volume-musica-partida"),
    valor: document.querySelector("#valor-volume-musica-partida"),
    ler: guardado.volumeMusica,
    salvar: guardado.salvarVolumeMusica,
    aoMudar: () => musica.atualizarVolume(),
  },
  {
    controle: document.querySelector("#volume-som-partida"),
    valor: document.querySelector("#valor-volume-som-partida"),
    ler: guardado.volumeSom,
    salvar: guardado.salvarVolumeSom,
    aoMudar: () => {},
  },
];

function pintarVolumesPartida() {
  for (const { controle, valor, ler } of volumesPartida) {
    controle.value = String(ler());
    valor.textContent = `${ler()}%`;
  }
}

for (const { controle, valor, salvar, aoMudar } of volumesPartida) {
  controle.addEventListener("input", () => {
    salvar(Number(controle.value));
    valor.textContent = `${controle.value}%`;
    aoMudar();
  });
  controle.addEventListener("change", () => som.tocar("clique"));
}

function abrirConfiguracaoPartida() {
  pintarPreferenciaAnimacoes();
  pintarVolumesPartida();
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

// --- sair -------------------------------------------------------------------

/* Sair tem janela própria, na moldura das outras janelas da partida — o
   confirm() do navegador destoava de todo o resto. A frase muda com quem
   sai: jogador perde a mesa (e os créditos); espectador só volta ao menu. */

function abrirSair() {
  if (!estado || estado.fase === "encerrada") {
    irParaOMenu();
    return;
  }
  document.querySelector("#sair-chamada").textContent = espectador ? "Assistindo" : "Sair da partida";
  document.querySelector("#sair-titulo").textContent = espectador ? "Parar de assistir?" : "Vai largar a mesa?";
  document.querySelector("#sair-explica").textContent = espectador
    ? "Você volta para o menu. A partida continua sem você."
    : "Você não volta para esta partida. Seus terrenos voltam para o banco e você não ganha créditos.";
  document.querySelector("#sair-confirmar").textContent = espectador ? "Parar de assistir" : "Sair da partida";
  modalSair.hidden = false;
  som.tocar("aviso");
  document.querySelector("#sair-ficar").focus();
}

function fecharSair() {
  modalSair.hidden = true;
}

function irParaOMenu() {
  som.tocar("voltar");
  pararConsulta();
  location.href = "/";
}

async function confirmarSaida() {
  som.tocar("voltar");
  pararConsulta();
  if (!espectador && estado?.fase !== "encerrada") {
    try {
      // Avisa o servidor: sem isso a vez ficaria parada esperando alguém que
      // já foi embora, e a mesa travava.
      await api.sairDaPartida(codigo);
    } catch {
      /* sair é melhor esforço — o menu continua sendo o destino */
    }
  }
  location.href = "/";
}

document.querySelector("#sair").addEventListener("click", abrirSair);
document.querySelector("#sair-ficar").addEventListener("click", () => {
  som.tocar("clique");
  fecharSair();
});
document.querySelector("#sair-confirmar").addEventListener("click", confirmarSaida);
modalSair.addEventListener("click", (evento) => {
  if (evento.target === modalSair) fecharSair();
});

// O pódio: ver o tabuleiro final (o JOGAR reabre) ou voltar ao menu.
document.querySelector("#fim-tabuleiro").addEventListener("click", () => {
  som.tocar("clique");
  fecharFimDePartida();
});
document.querySelector("#fim-menu").addEventListener("click", irParaOMenu);

document.addEventListener("keydown", (evento) => {
  if (evento.key !== "Escape") return;
  if (anuncioAberto()) fecharAnuncio();
  else if (!modalSair.hidden) fecharSair();
  else if (!painelCasaInfo.hidden) fecharInfoCasa();
  else if (!painelConfigPartida.hidden) fecharConfiguracaoPartida();
  else if (fimAberto()) fecharFimDePartida();
  else if (fimDoLeilaoAberto()) fecharFimDoLeilao();
});

// --- consulta -------------------------------------------------------------

async function atualizar() {
  // Nunca redesenha no meio de uma jogada: o peão está andando.
  // `consultando` evita duas consultas em voo — sem ele, a mais antiga pode
  // voltar por último e reaplicar um estado já vencido.
  if (document.hidden || ocupado || consultando) return;

  consultando = true;
  const geracaoNaSaida = geracao;
  try {
    const resposta = await api.verPartida(codigo);

    /* A trava do topo foi verificada ANTES da rede responder. Nesses
       ~200ms o jogador pode ter clicado em JOGAR (ou dado um lance), e aí
       esta resposta já nasceu velha. Descarta: a próxima consulta traz o
       estado certo. */
    if (ocupado || geracaoNaSaida !== geracao) return;

    // Chegou jogada de outro? Encena antes de aplicar — senão o peão
    // aparece pronto no destino. A Coringa de outro, idem: o suspense vem
    // antes do dinheiro mudar.
    const encenou = await encenarLanceDeOutro(resposta);
    await encenarCoringa(resposta);
    aplicar(resposta);
    if (encenou) contarJogada(resposta.partida.ultimo_movimento);
  } catch (erro) {
    if (erro.status === 404 || erro.status === 403) {
      pararConsulta();
      toast(erro.status === 403 ? erro.message : "A partida foi encerrada.", "erro");
      setTimeout(() => (location.href = "/"), 1600);
    } else if (!(erro instanceof ErroDaApi)) {
      // Rede caída a próxima consulta resolve; erro da própria tela, não —
      // calado, ele some e a mesa só "não mostra" alguma coisa.
      console.error(erro);
    }
  } finally {
    consultando = false;
  }
}

// 1,2s em vez de 2s: com a jogada dos outros sendo encenada, o atraso até a
// cena começar passa a ser sentido. No leilão, metade: os lances dos outros
// precisam chegar antes do relógio fechar.
const CONSULTA_MS = 1200;
const CONSULTA_NO_LEILAO_MS = 600;

const ritmoDesejado = () => (estado?.fase === "leiloando" ? CONSULTA_NO_LEILAO_MS : CONSULTA_MS);

function iniciarConsulta() {
  pararConsulta();
  ritmoDaConsulta = ritmoDesejado();
  if (estado?.fase !== "encerrada") consulta = setInterval(atualizar, ritmoDaConsulta);
  chat.iniciar();
}

function ajustarRitmoDaConsulta() {
  if (!consulta || ritmoDesejado() === ritmoDaConsulta) return;
  clearInterval(consulta);
  ritmoDaConsulta = ritmoDesejado();
  consulta = setInterval(atualizar, ritmoDaConsulta);
}

function pararConsulta() {
  if (consulta) clearInterval(consulta);
  consulta = null;
  chat.parar();
}

document.addEventListener("visibilitychange", () => !document.hidden && atualizar());

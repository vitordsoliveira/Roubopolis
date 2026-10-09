/* A música do Roubopolis: "Samba de 8 Bits", composta aqui mesmo.

   Como os efeitos (core/som.js), não há arquivo de áudio: a partitura está
   nas tabelas abaixo e o Web Audio toca nota por nota. É som de videogame
   antigo com balanço de samba — baixo sincopado em onda triangular,
   melodia em onda de pulso estreita (o timbre clássico de 8 bits), arpejo
   dos acordes e uma bateria de ruído com tamborim nos contratempos. Lá
   menor com o Mi maior de dominante: o clima de quem está tramando alguma
   coisa.

   Cada tela é uma página nova, e a música recomeçaria a cada troca. Por
   isso a posição fica guardada na aba (sessionStorage): o lobby continua
   do compasso em que o menu parou.

   Mexer na música é mexer nas tabelas: ACORDES, SECOES e FORMA. Cada
   compasso da melodia tem 16 casas (semicolcheias): uma nota ("A4", "G#5")
   começa ali, "-" segura a nota anterior e "." é silêncio. Compasso com
   outra quantidade de casas é erro — a música não toca, e o console diz
   onde. */

import { guardado } from "./api.js";
import { obterContexto } from "./som.js";

const BPM = 116;
const SEMICOLCHEIA = 60 / BPM / 4;
const CASAS_POR_COMPASSO = 16;
/** O "balanço": a semicolcheia do contratempo atrasa um tiquinho. */
const SUINGUE = SEMICOLCHEIA * 0.12;
/** Quanto à frente as notas são marcadas. A folga é o que deixa o relógio
    do navegador atrasar sem a música engasgar. */
const ANTECEDENCIA = 0.15;
/** A música no volume máximo fica abaixo dos efeitos: ela é fundo. */
const TETO = 0.5;
const CHAVE_POSICAO = "roubopolis.musica-passo";

// --- partitura ---------------------------------------------------------------

/** Baixo: fundamental, quinta e oitava. Arpejo: o acorde invertido para
    ficar sempre na mesma região, sem saltos. */
const ACORDES = {
  Am: { baixo: ["A2", "E3", "A3"], arpejo: ["A3", "C4", "E4", "A4"] },
  Dm: { baixo: ["D3", "A3", "D4"], arpejo: ["A3", "D4", "F4", "A4"] },
  G: { baixo: ["G2", "D3", "G3"], arpejo: ["G3", "B3", "D4", "G4"] },
  C: { baixo: ["C3", "G3", "C4"], arpejo: ["G3", "C4", "E4", "G4"] },
  F: { baixo: ["F2", "C3", "F3"], arpejo: ["A3", "C4", "F4", "A4"] },
  E: { baixo: ["E2", "B2", "E3"], arpejo: ["G#3", "B3", "E4", "G#4"] },
  Em: { baixo: ["E2", "B2", "E3"], arpejo: ["G3", "B3", "E4", "G4"] },
};

const SECOES = {
  // A: o tema, malandro, subindo e descendo a escala.
  A: {
    acordes: ["Am", "Dm", "G", "C", "F", "Dm", "E", "E"],
    melodia: [
      "A4 - . C5 . E5 - . D5 - C5 - B4 - A4 -",
      "F4 - . A4 . D5 - . F5 - E5 - D5 - C5 -",
      "B4 - . D5 . G5 - . F5 - E5 - D5 - B4 -",
      "C5 - - - E5 - G5 - E5 - - - . . . .",
      "A5 - . G5 . F5 - . E5 - F5 - G5 - A5 -",
      "F5 - . E5 . D5 - . C5 - D5 - E5 - F5 -",
      "E5 - . G#5 . B5 - . G#5 - E5 - D5 - B4 -",
      "E5 - - - - - - - . . B4 - C5 - D5 -",
    ],
  },
  // B: a ponte, de notas longas, abrindo para o agudo antes de voltar.
  B: {
    acordes: ["F", "G", "Em", "Am", "Dm", "G", "C", "E"],
    melodia: [
      "C5 - - - A4 - - - C5 - F5 - - - E5 -",
      "D5 - - - B4 - - - D5 - G5 - - - F5 -",
      "E5 - - - G5 - - - B5 - - - A5 - G5 -",
      "A5 - - - - - - - E5 - - - C5 - - -",
      "D5 - F5 - A5 - F5 - D5 - F5 - A5 - D6 -",
      "B5 - - - G5 - - - D5 - - - B4 - - -",
      "C5 - E5 - G5 - C6 - B5 - G5 - E5 - G5 -",
      "G#5 - - - - - - - B5 - - - E5 - - -",
    ],
  },
};

const FORMA = ["A", "A", "B", "A"];

/* O groove de um compasso, casa por casa. O baixo é o do partido-alto:
   [casa, grau] com 0 = fundamental, 1 = quinta, 2 = oitava. */
const BAIXO = [[0, 0], [3, 0], [6, 1], [8, 2], [10, 0], [11, 1], [14, 0]];
const BUMBO = [0, 7, 8];
const CAIXA = [4, 12];
const TAMBORIM = [3, 6, 10, 13];

const NOTAS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

function frequencia(nome) {
  const partes = /^([A-G])(#|b)?(\d)$/.exec(nome);
  if (!partes) throw new Error(`Música: nota "${nome}" não existe.`);
  const [, letra, acidente, oitava] = partes;
  const midi = 12 * (Number(oitava) + 1) + NOTAS[letra] + (acidente === "#" ? 1 : acidente === "b" ? -1 : 0);
  return 440 * 2 ** ((midi - 69) / 12);
}

/** A partitura vira uma lista plana de casas, cada uma dizendo o que soa. */
function compilar() {
  const casas = [];
  for (const nomeDaSecao of FORMA) {
    const secao = SECOES[nomeDaSecao];
    secao.acordes.forEach((nomeDoAcorde, compasso) => {
      const acorde = ACORDES[nomeDoAcorde];
      const tokens = secao.melodia[compasso].trim().split(/\s+/);
      if (tokens.length !== CASAS_POR_COMPASSO) {
        throw new Error(`Música: compasso ${compasso + 1} da seção ${nomeDaSecao} tem ${tokens.length} casas, e não 16.`);
      }
      // O último compasso da seção ganha uma virada de caixa.
      const virada = compasso === secao.acordes.length - 1;

      for (let c = 0; c < CASAS_POR_COMPASSO; c += 1) {
        const casa = {};
        const token = tokens[c];
        if (token !== "-" && token !== ".") {
          let duracao = 1;
          while (tokens[c + duracao] === "-") duracao += 1;
          casa.melodia = { freq: frequencia(token), casas: duracao };
        }
        const baixo = BAIXO.find(([onde]) => onde === c);
        if (baixo) casa.baixo = frequencia(acorde.baixo[baixo[1]]);
        if (c % 2 === 0) casa.arpejo = frequencia(acorde.arpejo[(c / 2) % 4]);
        casa.bumbo = BUMBO.includes(c);
        casa.caixa = CAIXA.includes(c) || (virada && c >= 12);
        casa.chimbal = c % 2 === 0 ? (c % 4 === 0 ? 2 : 1) : 0;
        casa.tamborim = TAMBORIM.includes(c);
        casas.push(casa);
      }
    });
  }
  return casas;
}

const PARTITURA = compilar();

// --- instrumentos ----------------------------------------------------------------

let audio = null;
/** Onde os instrumentos se ligam: o volume geral da música e o eco da
    melodia. Montada uma vez, na primeira vez que a música toca. */
let mesa = null;

function montarMesa() {
  const geral = audio.createGain();
  geral.gain.value = 0.0001;
  geral.connect(audio.destination);

  // Eco da melodia a três semicolcheias, que é o que dá o ar de fliperama.
  const envio = audio.createGain();
  envio.gain.value = 0.35;
  const eco = audio.createDelay(1);
  eco.delayTime.value = SEMICOLCHEIA * 3;
  const retorno = audio.createGain();
  retorno.gain.value = 0.3;
  envio.connect(eco);
  eco.connect(retorno);
  retorno.connect(eco);
  retorno.connect(geral);

  // Onda de pulso de 25%: mais fina e "nasal" que a quadrada comum.
  const harmonicos = 32;
  const real = new Float32Array(harmonicos);
  const imag = new Float32Array(harmonicos);
  for (let k = 1; k < harmonicos; k += 1) {
    real[k] = Math.sin(2 * Math.PI * k * 0.25) / (k * Math.PI);
    imag[k] = (1 - Math.cos(2 * Math.PI * k * 0.25)) / (k * Math.PI);
  }
  const pulso = audio.createPeriodicWave(real, imag);

  const ruido = audio.createBuffer(1, audio.sampleRate, audio.sampleRate);
  const amostras = ruido.getChannelData(0);
  for (let i = 0; i < amostras.length; i += 1) amostras[i] = Math.random() * 2 - 1;

  mesa = { geral, envio, pulso, ruido };
}

/** Uma nota com ataque curto, leve queda e soltura no fim. */
function nota(t, freq, duracao, { forma = "square", onda, volume, destinos = [mesa.geral] }) {
  const oscilador = audio.createOscillator();
  if (onda) oscilador.setPeriodicWave(onda);
  else oscilador.type = forma;
  oscilador.frequency.setValueAtTime(freq, t);

  const ganho = audio.createGain();
  const soltura = Math.min(0.05, duracao / 3);
  ganho.gain.setValueAtTime(0.0001, t);
  ganho.gain.exponentialRampToValueAtTime(volume, t + 0.006);
  ganho.gain.exponentialRampToValueAtTime(volume * 0.6, t + duracao - soltura);
  ganho.gain.exponentialRampToValueAtTime(0.0001, t + duracao);

  oscilador.connect(ganho);
  for (const destino of destinos) ganho.connect(destino);
  oscilador.start(t);
  oscilador.stop(t + duracao + 0.02);
}

/** Ruído filtrado: caixa, chimbal, a pele do tamborim. */
function ruido(t, duracao, { filtro, freq, q = 1, volume }) {
  const fonte = audio.createBufferSource();
  fonte.buffer = mesa.ruido;
  const corte = audio.createBiquadFilter();
  corte.type = filtro;
  corte.frequency.value = freq;
  corte.Q.value = q;
  const ganho = audio.createGain();
  ganho.gain.setValueAtTime(volume, t);
  ganho.gain.exponentialRampToValueAtTime(0.0001, t + duracao);
  fonte.connect(corte).connect(ganho).connect(mesa.geral);
  fonte.start(t, Math.random() * 0.5, duracao + 0.02);
}

function bumbo(t) {
  const oscilador = audio.createOscillator();
  oscilador.type = "sine";
  oscilador.frequency.setValueAtTime(150, t);
  oscilador.frequency.exponentialRampToValueAtTime(45, t + 0.12);
  const ganho = audio.createGain();
  ganho.gain.setValueAtTime(0.7, t);
  ganho.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
  oscilador.connect(ganho).connect(mesa.geral);
  oscilador.start(t);
  oscilador.stop(t + 0.2);
}

function tocarCasa(casa, t) {
  if (casa.melodia) {
    nota(t, casa.melodia.freq, casa.melodia.casas * SEMICOLCHEIA * 0.95, {
      onda: mesa.pulso,
      volume: 0.13,
      destinos: [mesa.geral, mesa.envio],
    });
  }
  if (casa.baixo) nota(t, casa.baixo, SEMICOLCHEIA * 1.8, { forma: "triangle", volume: 0.5 });
  if (casa.arpejo) nota(t, casa.arpejo, 0.07, { forma: "square", volume: 0.03 });
  if (casa.bumbo) bumbo(t);
  if (casa.caixa) {
    ruido(t, 0.12, { filtro: "bandpass", freq: 1800, q: 0.7, volume: 0.32 });
    nota(t, 190, 0.06, { forma: "triangle", volume: 0.14 });
  }
  if (casa.chimbal) ruido(t, 0.03, { filtro: "highpass", freq: 7000, volume: casa.chimbal === 2 ? 0.14 : 0.08 });
  if (casa.tamborim) {
    nota(t, 1100, 0.035, { forma: "square", volume: 0.04 });
    ruido(t, 0.02, { filtro: "highpass", freq: 4000, volume: 0.07 });
  }
}

// --- relógio -----------------------------------------------------------------------

let passo = lerPosicao();
let proximo = 0;
let relogio = null;

function lerPosicao() {
  try {
    const salvo = Number(sessionStorage.getItem(CHAVE_POSICAO));
    return Number.isInteger(salvo) && salvo >= 0 ? salvo % PARTITURA.length : 0;
  } catch {
    return 0;
  }
}

function guardarPosicao() {
  try {
    sessionStorage.setItem(CHAVE_POSICAO, String(passo));
  } catch {
    /* sem armazenamento: a próxima tela começa do início da música */
  }
}

function volumeAlvo() {
  if (!guardado.som() || document.hidden) return 0;
  return (TETO * Math.max(0, Math.min(100, guardado.volumeMusica()))) / 100;
}

/* Marca as notas que caem na próxima fração de segundo. O setInterval é
   impreciso; o relógio do áudio, não — por isso cada nota sai com hora
   marcada, e o intervalo só precisa passar a tempo de marcar a seguinte. */
function agendar() {
  // Atrasou demais (janela minimizada, máquina ocupada): retoma de agora,
  // em vez de despejar de uma vez as notas que ficaram para trás.
  if (proximo < audio.currentTime) proximo = audio.currentTime + 0.05;
  const muda = volumeAlvo() === 0;
  while (proximo < audio.currentTime + ANTECEDENCIA) {
    // Mudo, a música segue andando sem criar nota: ao voltar o volume, ela
    // está onde estaria.
    if (!muda) tocarCasa(PARTITURA[passo], proximo + (passo % 2 ? SUINGUE : 0));
    passo = (passo + 1) % PARTITURA.length;
    proximo += SEMICOLCHEIA;
  }
}

function aplicarVolume(suavidade = 0.08) {
  if (!mesa) return;
  const agora = audio.currentTime;
  mesa.geral.gain.cancelScheduledValues(agora);
  mesa.geral.gain.setTargetAtTime(Math.max(0.0001, volumeAlvo()), agora, suavidade);
}

export const musica = {
  /** Cada tela chama ao abrir. A música entra subindo devagar. */
  iniciar() {
    if (relogio) return;
    audio = obterContexto();
    if (!audio) return;
    if (!mesa) montarMesa();

    // O Electron deixa tocar sem clique; se algum dia o contexto nascer
    // suspenso, o primeiro toque do jogador destrava.
    if (audio.state === "suspended") {
      audio.resume().catch(() => {});
      const destravar = () => audio.resume();
      window.addEventListener("pointerdown", destravar, { once: true });
      window.addEventListener("keydown", destravar, { once: true });
    }

    proximo = audio.currentTime + 0.1;
    agendar();
    relogio = setInterval(agendar, 25);
    aplicarVolume(0.6);

    document.addEventListener("visibilitychange", () => aplicarVolume(0.15));
    window.addEventListener("pagehide", guardarPosicao);
  },

  /** A configuração mudou (volume da música ou o som inteiro). */
  atualizarVolume() {
    aplicarVolume();
  },
};

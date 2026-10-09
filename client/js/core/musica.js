/* A música do Roubopolis: "Golpe Perfeito", composta aqui mesmo.

   Trilha de filme de assalto em 8 bits, contando o golpe em quatro partes
   que se repetem:

   1. ESGUEIRADA — o baixo sorrateiro, estalo de dedos no 2 e no 4, e o
      "toque": notinhas na ponta dos pés que chegam de meio em meio tom.
   2. PLANO — entra o sax noir, que escorrega para dentro de cada nota,
      sobre o acorde de filme de espião (Mi menor com sétima maior).
   3. COFRE — suspense: o baixo vira coração batendo, o segredo do cofre
      tiqueteia, a melodia desce de meio em meio tom e as travas estalam.
   4. FUGA — sirene, baixo de perseguição de série policial, bateria sem
      balanço. E volta para o PLANO, como quem escapou.

   Como os efeitos (core/som.js), não há arquivo de áudio: a partitura está
   nas tabelas abaixo e o Web Audio toca nota por nota.

   Cada tela é uma página nova, e a música recomeçaria a cada troca. Por
   isso a posição fica guardada na aba (sessionStorage): o lobby continua
   do compasso em que o menu parou.

   Mexer na música é mexer nas tabelas — INSTRUMENTOS, SECOES e FORMA. Cada
   compasso de uma voz tem 16 casas (semicolcheias): uma nota ("A4", "D#5")
   começa ali, "-" segura a nota anterior e "." é silêncio. Na bateria, "x"
   toca e "X" toca forte. Compasso com outra quantidade de casas é erro: a
   música não toca, e o console diz onde. */

import { guardado } from "./api.js";
import { obterContexto } from "./som.js";

const BPM = 100;
const SEMICOLCHEIA = 60 / BPM / 4;
const CASAS_POR_COMPASSO = 16;
/** Quanto à frente as notas são marcadas. A folga é o que deixa o relógio
    do navegador atrasar sem a música engasgar. */
const ANTECEDENCIA = 0.15;
/** A música no volume máximo fica abaixo dos efeitos: ela é fundo. */
const TETO = 0.5;
const CHAVE_POSICAO = "roubopolis.musica-passo";

// --- instrumentos ----------------------------------------------------------------

/* O timbre de cada voz.
   - onda: "square", "triangle" ou "pulso" (pulso de 25%, o som de 8 bits);
   - filtro: corta o agudo acima dessa frequência — deixa a voz mais escura;
   - ataque: quanto a nota leva para chegar ao volume (pad entra devagar);
   - beliscado: a nota cai logo depois do ataque, como corda beliscada;
   - escorrega: começa meio tom abaixo e sobe — o "scoop" do sax;
   - deslize: vai da nota anterior até esta nesse tempo — a sirene;
   - vibrato: o tremido da nota, em fração da frequência;
   - eco: manda a voz para o eco de três semicolcheias;
   - minimo/maximo: limites da duração, em segundos. */
const INSTRUMENTOS = {
  baixo: { onda: "square", filtro: 650, volume: 0.24, beliscado: true, minimo: 0.18 },
  fundo: { onda: "triangle", volume: 0.05, ataque: 0.15 },
  fundo2: { onda: "triangle", volume: 0.045, ataque: 0.15 },
  toque: { onda: "square", filtro: 2400, volume: 0.07, beliscado: true, maximo: 0.08 },
  sax: { onda: "pulso", filtro: 3200, volume: 0.1, escorrega: true, vibrato: 0.007, eco: true },
  sirene: { onda: "square", filtro: 2000, volume: 0.05, deslize: 0.18, vibrato: 0.012 },
};

// --- partitura ----------------------------------------------------------------------

const PAUSA = ". . . . . . . . . . . . . . . .";
const vezes = (n, compasso) => Array(n).fill(compasso);

/* O baixo sorrateiro e o "clichê de linha" do filme noir: o acorde fica
   parado e uma voz do meio desce de meio em meio tom (Mi, Ré#, Ré, Dó#).
   PLANO usa o mesmo chão da ESGUEIRADA. */
const BAIXO_SORRATEIRO = [
  "E2 . . . E2 . G2 . E2 . . . A#2 . B2 .",
  "E2 . . . E2 . G2 . E2 . . . A#2 . B2 .",
  "E2 . . . E2 . G2 . E2 . . . A#2 . B2 .",
  "E2 . . . E2 . G2 . A2 . A#2 . B2 . D3 .",
  "A2 . . . A2 . C3 . A2 . . . D#3 . E3 .",
  "A2 . . . A2 . C3 . A2 . G2 . F#2 . F2 .",
  "C3 . . . C3 . E3 . G2 . . . A#2 . . .",
  "B2 . . . B2 . D#3 . F#2 . . . F#2 . D#2 .",
];
const CLICHE = [
  "E4 - - - - - - - - - - - - - - -",
  "D#4 - - - - - - - - - - - - - - -",
  "D4 - - - - - - - - - - - - - - -",
  "C#4 - - - - - - - - - - - - - - -",
  "A3 - - - - - - - G#3 - - - - - - -",
  "G3 - - - - - - - F#3 - - - - - - -",
  "A#3 - - - - - - - - - - - - - - -",
  "A3 - - - - - - - - - - - - - - -",
];
const CLICHE_APOIO = [
  ...vezes(4, "G3 - - - - - - - - - - - - - - -"),
  ...vezes(2, "C4 - - - - - - - - - - - - - - -"),
  "E4 - - - - - - - - - - - - - - -",
  "D#4 - - - - - - - - - - - - - - -",
];
const DEDOS_E_PRATO = {
  // O prato de condução do jazz: "tin, tin-da tin, tin-da" com o balanço.
  prato: "x...x.x.x...x.x.",
  estalo: "....x.......x...",
  bumbo: "x.......x.......",
};

const SECOES = {
  esgueirada: {
    suingue: 0.55,
    vozes: {
      baixo: BAIXO_SORRATEIRO,
      fundo: CLICHE,
      fundo2: CLICHE_APOIO,
      // Na ponta dos pés: sempre chegando à nota pelo meio tom de baixo.
      toque: [
        ". . . . . . . . D#4 . E4 . . . . .",
        ". . . . . . . . F#4 . G4 . . . . .",
        ". . . . . . . . A#4 . B4 . . . . .",
        ". . . . B4 . A#4 . A4 . G#4 . G4 . . .",
        ". . . . . . . . G#4 . A4 . . . . .",
        ". . . . . . . . B4 . C5 . . . . .",
        ". . . . . . . . A#4 . . . G4 . . .",
        "D#5 . . . B4 . . . F#4 . . . A4 . . .",
      ],
    },
    bateria: DEDOS_E_PRATO,
  },

  plano: {
    suingue: 0.55,
    vozes: {
      baixo: BAIXO_SORRATEIRO,
      fundo: CLICHE,
      fundo2: CLICHE_APOIO,
      sax: [
        "B4 - - - E5 - G5 - F#5 - E5 - D#5 - - -",
        "E5 - - - . . . . . . B4 - C5 - B4 -",
        "A#4 - B4 - - - . . G5 - F#5 - F5 - E5 -",
        "D#5 - - - - - - - . . . . B4 - - -",
        "C5 - - - E5 - A5 - G#5 - - - E5 - - -",
        "A5 - G5 - E5 - C5 - D#5 - - - E5 - - -",
        "G5 - - - E5 - A#4 - - - G4 - A#4 - C5 -",
        "B4 - - - D#5 - F#5 - A5 - - - - - . .",
      ],
    },
    bateria: { ...DEDOS_E_PRATO, escova: "....x.......x..." },
    virada: { escova: "....x.....x.x.xx" },
  },

  cofre: {
    suingue: 0.55,
    vozes: {
      // Coração batendo: tum-tum, e espera.
      baixo: [
        ...vezes(6, "E2 . E2 . . . . . . . . . . . . ."),
        ...vezes(2, "B2 . B2 . . . . . . . . . . . . ."),
      ],
      // Si e Ré# por cima do Mi: o acorde de espião, parado no ar.
      fundo: [
        ...vezes(2, "B3 - - - - - - - - - - - - - - -"),
        ...vezes(2, "C4 - - - - - - - - - - - - - - -"),
        ...vezes(4, "A3 - - - - - - - - - - - - - - -"),
      ],
      fundo2: [
        ...vezes(2, "D#4 - - - - - - - - - - - - - - -"),
        ...vezes(2, "E4 - - - - - - - - - - - - - - -"),
        ...vezes(2, "C4 - - - - - - - - - - - - - - -"),
        ...vezes(2, "D#4 - - - - - - - - - - - - - - -"),
      ],
      // Descendo de meio em meio tom, uma oitava inteira, até a trava abrir.
      sax: [
        "B5 - - - - - - - A#5 - - - - - - -",
        "A5 - - - - - - - G#5 - - - - - - -",
        "G5 - - - - - - - . . . . E5 - G5 -",
        "F#5 - - - - - - - - - - - . . . .",
        "E5 - - - - - - - D#5 - - - - - - -",
        "D5 - - - - - - - C#5 - - - - - - -",
        "C5 - - - - - - - B4 - - - - - - -",
        "A#4 - - - - - - - B4 - - - - - . .",
      ],
    },
    // O segredo do cofre girando, clique a clique.
    bateria: { tique: "x.x.x.x.x.x.x.x." },
    // E as travas cedendo, uma de cada vez.
    virada: { tique: "x.x.x.x.........", trava: "........X...X..X" },
  },

  fuga: {
    suingue: 0,
    vozes: {
      // Baixo de perseguição: oitava pra cá, oitava pra lá.
      baixo: [
        "E2 . E3 . E2 . E3 . E2 . E3 . E2 . D3 .",
        "E2 . E3 . E2 . E3 . E2 . E3 . E2 . D3 .",
        "C2 . C3 . C2 . C3 . C2 . C3 . C2 . C#2 .",
        "D2 . D3 . D2 . D3 . D2 . D3 . D2 . D#2 .",
        "E2 . E3 . E2 . E3 . E2 . E3 . E2 . D3 .",
        "E2 . E3 . E2 . E3 . E2 . E3 . E2 . D3 .",
        "C2 . C3 . C2 . C3 . C2 . C3 . C2 . C3 .",
        "B2 . B3 . B2 . B3 . F#2 . F#3 . D#2 . D#3 .",
      ],
      // A sirene chega, vai embora, volta.
      sirene: [
        "B4 - - - - - - - E5 - - - - - - -",
        "B4 - - - - - - - E5 - - - - - - -",
        PAUSA,
        PAUSA,
        "B4 - - - - - - - E5 - - - - - - -",
        "B4 - - - - - - - E5 - - - - - - -",
        PAUSA,
        PAUSA,
      ],
      // Entre uma sirene e outra, o sax correndo.
      sax: [
        PAUSA,
        PAUSA,
        "E5 . G5 . E5 . G5 . A5 . G5 . E5 . D5 .",
        "F#5 . A5 . F#5 . A5 . B5 . A5 . F#5 . D5 .",
        PAUSA,
        PAUSA,
        "G5 . E5 . C5 . E5 . G5 . A5 . A#5 . B5 .",
        "B5 - - - . . . . D#5 . F#5 . A5 . B5 .",
      ],
    },
    bateria: {
      bumbo: "X.....x.x.....x.",
      caixa: "....X.......X...",
      chimbal: "x.x.x.x.x.x.x.x.",
    },
    virada: { caixa: "....X...x.x.xXXX" },
  },
};

const FORMA = ["esgueirada", "plano", "cofre", "fuga", "plano"];

// --- compilação ------------------------------------------------------------------

const NOTAS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

function frequencia(nome) {
  const partes = /^([A-G])(#|b)?(\d)$/.exec(nome);
  if (!partes) throw new Error(`Música: nota "${nome}" não existe.`);
  const [, letra, acidente, oitava] = partes;
  const midi = 12 * (Number(oitava) + 1) + NOTAS[letra] + (acidente === "#" ? 1 : acidente === "b" ? -1 : 0);
  return 440 * 2 ** ((midi - 69) / 12);
}

function casasDoCompasso(texto, onde) {
  const tokens = texto.trim().split(/\s+/);
  if (tokens.length !== CASAS_POR_COMPASSO) {
    throw new Error(`Música: ${onde} tem ${tokens.length} casas, e não ${CASAS_POR_COMPASSO}.`);
  }
  return tokens;
}

/** A partitura vira uma lista plana de casas, cada uma dizendo o que soa
    e com quanto atraso (o balanço). */
function compilar() {
  const casas = [];
  for (const nomeDaSecao of FORMA) {
    const secao = SECOES[nomeDaSecao];
    const vozes = Object.entries(secao.vozes);
    const compassos = vozes[0][1].length;
    for (const [voz, lista] of vozes) {
      if (!INSTRUMENTOS[voz]) throw new Error(`Música: a voz "${voz}" não tem instrumento.`);
      if (lista.length !== compassos) {
        throw new Error(`Música: em ${nomeDaSecao}, a voz ${voz} tem ${lista.length} compassos, e não ${compassos}.`);
      }
    }
    // A nota anterior de cada voz, para quem desliza de uma nota à outra.
    const anterior = {};

    for (let compasso = 0; compasso < compassos; compasso += 1) {
      const ritmo = { ...secao.bateria, ...(compasso === compassos - 1 ? secao.virada : {}) };
      for (const [peca, padrao] of Object.entries(ritmo)) {
        if (!BATERIA[peca]) throw new Error(`Música: a bateria não tem "${peca}".`);
        if (padrao.length !== CASAS_POR_COMPASSO) {
          throw new Error(`Música: em ${nomeDaSecao}, o padrão de ${peca} não tem ${CASAS_POR_COMPASSO} casas.`);
        }
      }
      const tokens = Object.fromEntries(vozes.map(([voz, lista]) => [
        voz,
        casasDoCompasso(lista[compasso], `o compasso ${compasso + 1} de ${voz} em ${nomeDaSecao}`),
      ]));

      for (let c = 0; c < CASAS_POR_COMPASSO; c += 1) {
        // Balanço: o contratempo da colcheia atrasa mais, as semicolcheias
        // do meio atrasam metade.
        const fracao = c % 4 === 2 ? 1 : c % 2 === 1 ? 0.5 : 0;
        const casa = { atraso: secao.suingue * fracao * SEMICOLCHEIA, notas: [], bateria: [] };

        for (const [voz] of vozes) {
          const lista = tokens[voz];
          const token = lista[c];
          if (token === "-" || token === ".") continue;
          let duracao = 1;
          while (lista[c + duracao] === "-") duracao += 1;
          const freq = frequencia(token);
          casa.notas.push({ voz, freq, casas: duracao, de: anterior[voz] });
          anterior[voz] = freq;
        }
        for (const [peca, padrao] of Object.entries(ritmo)) {
          if (padrao[c] === "x" || padrao[c] === "X") casa.bateria.push({ peca, forte: padrao[c] === "X" });
        }
        casas.push(casa);
      }
    }
  }
  return casas;
}

// --- como cada coisa soa ----------------------------------------------------------

let audio = null;
/** Onde os instrumentos se ligam: o volume geral da música e o eco do sax.
    Montada uma vez, na primeira vez que a música toca. */
let mesa = null;

function montarMesa() {
  const geral = audio.createGain();
  geral.gain.value = 0.0001;
  geral.connect(audio.destination);

  // Eco a três semicolcheias: a rua vazia de madrugada devolvendo o som.
  const envio = audio.createGain();
  envio.gain.value = 0.32;
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

function tocarNota(t, { voz, freq, casas, de }) {
  const inst = INSTRUMENTOS[voz];
  let duracao = casas * SEMICOLCHEIA * 0.92;
  if (inst.minimo) duracao = Math.max(duracao, inst.minimo);
  if (inst.maximo) duracao = Math.min(duracao, inst.maximo);

  const oscilador = audio.createOscillator();
  if (inst.onda === "pulso") oscilador.setPeriodicWave(mesa.pulso);
  else oscilador.type = inst.onda;

  // Por onde a nota entra: deslizando da anterior, escorregando de meio
  // tom abaixo, ou direto.
  const partida = inst.deslize && de ? de : inst.escorrega ? freq * 0.944 : freq;
  oscilador.frequency.setValueAtTime(partida, t);
  if (partida !== freq) oscilador.frequency.exponentialRampToValueAtTime(freq, t + (inst.deslize || 0.05));

  const fim = t + duracao;
  if (inst.vibrato) {
    const lfo = audio.createOscillator();
    lfo.frequency.value = 5.5;
    const profundidade = audio.createGain();
    profundidade.gain.value = freq * inst.vibrato;
    lfo.connect(profundidade).connect(oscilador.frequency);
    lfo.start(t);
    lfo.stop(fim + 0.05);
  }

  const ganho = audio.createGain();
  const ataque = inst.ataque ?? 0.006;
  const soltura = Math.min(0.06, duracao / 3);
  const sustento = Math.max(t + ataque + 0.005, fim - soltura);
  ganho.gain.setValueAtTime(0.0001, t);
  ganho.gain.exponentialRampToValueAtTime(inst.volume, t + ataque);
  ganho.gain.exponentialRampToValueAtTime(inst.volume * (inst.beliscado ? 0.25 : 0.7), sustento);
  ganho.gain.exponentialRampToValueAtTime(0.0001, Math.max(sustento + 0.01, fim));

  let saida = oscilador;
  if (inst.filtro) {
    const corte = audio.createBiquadFilter();
    corte.type = "lowpass";
    corte.frequency.value = inst.filtro;
    saida = saida.connect(corte);
  }
  saida.connect(ganho).connect(mesa.geral);
  if (inst.eco) ganho.connect(mesa.envio);
  oscilador.start(t);
  oscilador.stop(fim + 0.05);
}

/** Ruído filtrado: estalo de dedo, escova, prato, caixa. */
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

/** Um tom curto de percussão, que pode cair de `freq` até `ate`. */
function pancada(t, duracao, { forma = "sine", freq, ate = freq, volume }) {
  const oscilador = audio.createOscillator();
  oscilador.type = forma;
  oscilador.frequency.setValueAtTime(freq, t);
  if (ate !== freq) oscilador.frequency.exponentialRampToValueAtTime(ate, t + duracao * 0.7);
  const ganho = audio.createGain();
  ganho.gain.setValueAtTime(volume, t);
  ganho.gain.exponentialRampToValueAtTime(0.0001, t + duracao);
  oscilador.connect(ganho).connect(mesa.geral);
  oscilador.start(t);
  oscilador.stop(t + duracao + 0.02);
}

/** Cada peça recebe a hora e a força (1, ou mais quando é "X"). */
const BATERIA = {
  bumbo: (t, f) => pancada(t, 0.2, { freq: 120, ate: 45, volume: 0.45 * f }),
  // Estalo de dedo: o som de quem anda de mansinho.
  estalo: (t, f) => {
    ruido(t, 0.05, { filtro: "bandpass", freq: 2300, q: 2.5, volume: 0.45 * f });
    ruido(t, 0.012, { filtro: "highpass", freq: 6000, volume: 0.2 * f });
  },
  escova: (t, f) => ruido(t, 0.22, { filtro: "bandpass", freq: 3200, q: 0.5, volume: 0.07 * f }),
  prato: (t, f) => {
    ruido(t, 0.28, { filtro: "highpass", freq: 6500, volume: 0.045 * f });
    pancada(t, 0.22, { forma: "square", freq: 5100, volume: 0.006 * f });
  },
  // O segredo do cofre girando.
  tique: (t, f) => {
    pancada(t, 0.018, { forma: "square", freq: 2100, volume: 0.04 * f });
    ruido(t, 0.01, { filtro: "highpass", freq: 5000, volume: 0.08 * f });
  },
  // A trava do cofre cedendo: um "clac" metálico e grave.
  trava: (t, f) => {
    ruido(t, 0.07, { filtro: "lowpass", freq: 1400, volume: 0.35 * f });
    pancada(t, 0.06, { forma: "square", freq: 190, ate: 90, volume: 0.1 * f });
  },
  caixa: (t, f) => {
    ruido(t, 0.13, { filtro: "bandpass", freq: 1800, q: 0.7, volume: 0.28 * f });
    pancada(t, 0.06, { forma: "triangle", freq: 190, volume: 0.12 * f });
  },
  chimbal: (t, f) => ruido(t, 0.03, { filtro: "highpass", freq: 7500, volume: 0.07 * f }),
};

const PARTITURA = compilar();

function tocarCasa(casa, t) {
  const quando = t + casa.atraso;
  for (const nota of casa.notas) tocarNota(quando, nota);
  for (const { peca, forte } of casa.bateria) BATERIA[peca](quando, forte ? 1.6 : 1);
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
    if (!muda) tocarCasa(PARTITURA[passo], proximo);
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

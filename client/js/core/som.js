/* Os sons do jogo, sintetizados na hora com Web Audio. O projeto não tem
   arquivo de áudio, e é de propósito: cada som é uma receita curta de tons
   e ruído, e tudo obedece ao liga/desliga e ao volume da configuração.

   Dois tipos:
   - `notas`: os bipes da interface, uma escadinha de notas quadradas;
   - `efeitos`: os sons da mesa — caixa registradora, moedas, dado, passo
     do peão —, cada um uma pequena função que monta o som. */

import { guardado } from "./api.js";

let contexto;
/** Um segundo de ruído branco, criado uma vez: é a matéria-prima da gaveta,
    da moeda batendo e do dado na mesa. */
let ruido;

const notas = {
  clique: [440],
  confirmar: [523.25, 659.25],
  voltar: [392, 293.66],
  erro: [180, 140],
  selecionar: [392, 523.25],
  copiar: [659.25, 783.99],
  entrar: [261.63, 392, 523.25],
  pronto: [440, 554.37, 659.25],
  sucesso: [523.25, 659.25, 783.99, 1046.5],
  aviso: [293.66, 349.23],
};

/** O mesmo contexto para os efeitos e a música (core/musica.js). */
export function obterContexto() {
  if (!contexto) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return null;
    contexto = new AudioContext();
  }
  return contexto;
}

const volumeGeral = () => Math.max(0, Math.min(100, guardado.volumeSom())) / 100;
const sorteio = (min, max) => min + Math.random() * (max - min);

/** Ataque curto e queda exponencial — o "tic" de todo som de 8 bits. */
function envelope(ganho, inicio, duracao, volume) {
  const pico = Math.max(0.0001, volume * volumeGeral());
  ganho.gain.setValueAtTime(0.0001, inicio);
  ganho.gain.exponentialRampToValueAtTime(pico, inicio + Math.min(0.01, duracao / 4));
  ganho.gain.exponentialRampToValueAtTime(0.0001, inicio + duracao);
}

/** Um tom, que pode deslizar de `freq` até `ate`. */
function tom(audio, inicio, { freq, ate = freq, forma = "square", duracao = 0.1, volume = 0.1 }) {
  const oscilador = audio.createOscillator();
  const ganho = audio.createGain();
  oscilador.type = forma;
  oscilador.frequency.setValueAtTime(freq, inicio);
  if (ate !== freq) oscilador.frequency.exponentialRampToValueAtTime(ate, inicio + duracao);
  envelope(ganho, inicio, duracao, volume);
  oscilador.connect(ganho).connect(audio.destination);
  oscilador.start(inicio);
  oscilador.stop(inicio + duracao + 0.02);
}

/** Um estalo de ruído filtrado, que pode varrer o filtro até `ate`. */
function estalo(audio, inicio, { freq, ate = freq, filtro = "bandpass", q = 1, duracao = 0.04, volume = 0.2 }) {
  if (!ruido) {
    ruido = audio.createBuffer(1, audio.sampleRate, audio.sampleRate);
    const amostras = ruido.getChannelData(0);
    for (let i = 0; i < amostras.length; i += 1) amostras[i] = Math.random() * 2 - 1;
  }
  const fonte = audio.createBufferSource();
  fonte.buffer = ruido;
  const corte = audio.createBiquadFilter();
  corte.type = filtro;
  corte.Q.value = q;
  corte.frequency.setValueAtTime(freq, inicio);
  if (ate !== freq) corte.frequency.exponentialRampToValueAtTime(ate, inicio + duracao);
  const ganho = audio.createGain();
  envelope(ganho, inicio, duracao, volume);
  fonte.connect(corte).connect(ganho).connect(audio.destination);
  fonte.start(inicio, Math.random() * 0.5, duracao + 0.02);
}

const efeitos = {
  /** Caixa registradora abrindo: duas teclas, a gaveta batendo e o sino. */
  caixa(audio, t) {
    estalo(audio, t, { freq: 3800, q: 3, duracao: 0.025, volume: 0.28 });
    estalo(audio, t + 0.07, { freq: 3300, q: 3, duracao: 0.025, volume: 0.28 });
    estalo(audio, t + 0.15, { freq: 900, filtro: "lowpass", duracao: 0.14, volume: 0.5 });
    tom(audio, t + 0.15, { freq: 150, ate: 70, forma: "triangle", duracao: 0.12, volume: 0.28 });
    tom(audio, t + 0.24, { freq: 2637, forma: "sine", duracao: 0.8, volume: 0.13 });
    tom(audio, t + 0.24, { freq: 3951, forma: "sine", duracao: 0.45, volume: 0.05 });
    tom(audio, t + 0.31, { freq: 3520, forma: "sine", duracao: 0.7, volume: 0.09 });
  },

  /** Chuva de moedas e um arpejo subindo: dinheiro entrando. */
  moedas(audio, t) {
    for (let i = 0; i < 9; i += 1) {
      const quando = t + i * 0.055 + sorteio(0, 0.02);
      tom(audio, quando, { freq: sorteio(2600, 4200), forma: "sine", duracao: 0.14, volume: 0.07 });
      estalo(audio, quando, { freq: 6000, filtro: "highpass", duracao: 0.015, volume: 0.09 });
    }
    [784, 988, 1175, 1568].forEach((freq, i) => {
      tom(audio, t + 0.5 + i * 0.07, { freq, duracao: i === 3 ? 0.25 : 0.1, volume: 0.07 });
    });
  },

  /** Trombone triste: dinheiro saindo sem ninguém querer — aluguel, imposto. */
  perda(audio, t) {
    [392, 370, 349].forEach((freq, i) => {
      tom(audio, t + i * 0.2, { freq, forma: "triangle", duracao: 0.18, volume: 0.17 });
    });
    tom(audio, t + 0.6, { freq: 330, ate: 220, forma: "triangle", duracao: 0.55, volume: 0.17 });
  },

  /** O prédio brotando no terreno recém-comprado: dois pulinhos para cima. */
  construir(audio, t) {
    tom(audio, t, { freq: 330, ate: 660, duracao: 0.09, volume: 0.08 });
    tom(audio, t + 0.09, { freq: 495, ate: 990, duracao: 0.12, volume: 0.08 });
    estalo(audio, t + 0.2, { freq: 1200, filtro: "lowpass", duracao: 0.06, volume: 0.25 });
  },

  /** Os dados batendo na mesa, cada batida mais espaçada: perdendo força. */
  dado(audio, t) {
    let quando = t;
    for (let i = 0; i < 7; i += 1) {
      estalo(audio, quando, { freq: sorteio(1800, 3200), q: 4, duracao: 0.03, volume: 0.32 });
      tom(audio, quando, { freq: sorteio(160, 240), forma: "triangle", duracao: 0.04, volume: 0.09 });
      quando += 0.05 + i * 0.022;
    }
  },

  /** O total do dado batendo na faixa: um baque grave e um brilho. */
  resultado(audio, t) {
    tom(audio, t, { freq: 110, ate: 55, forma: "sine", duracao: 0.25, volume: 0.4 });
    tom(audio, t, { freq: 659.25, duracao: 0.09, volume: 0.07 });
    tom(audio, t + 0.08, { freq: 987.77, duracao: 0.16, volume: 0.07 });
  },

  /** O peão pulando de uma casa para a outra. */
  passo(audio, t) {
    tom(audio, t, { freq: 520, ate: 820, forma: "triangle", duracao: 0.08, volume: 0.12 });
  },

  /** Uma faixa atravessando a tela. */
  vento(audio, t) {
    estalo(audio, t, { freq: 300, ate: 2400, q: 0.8, duracao: 0.32, volume: 0.24 });
  },

  /** Sua vez: a faixa passa e uma fanfarrinha toca. */
  vez(audio, t) {
    efeitos.vento(audio, t);
    [523.25, 659.25, 783.99].forEach((freq, i) => tom(audio, t + 0.12 + i * 0.08, { freq, duracao: 0.09, volume: 0.08 }));
    tom(audio, t + 0.36, { freq: 1046.5, duracao: 0.3, volume: 0.08 });
  },

  /** Terreno à venda na sua frente: plim-plim. */
  oferta(audio, t) {
    tom(audio, t, { freq: 1318.5, forma: "sine", duracao: 0.35, volume: 0.13 });
    tom(audio, t + 0.12, { freq: 1760, forma: "sine", duracao: 0.5, volume: 0.13 });
  },

  /** O relógio nos últimos segundos da sua vez. */
  tique(audio, t) {
    tom(audio, t, { freq: 1500, duracao: 0.035, volume: 0.05 });
    estalo(audio, t, { freq: 5000, filtro: "highpass", duracao: 0.012, volume: 0.07 });
  },

  /** Fim de partida. */
  fim(audio, t) {
    const melodia = [[523.25, 0], [659.25, 0.12], [783.99, 0.24], [1046.5, 0.36], [783.99, 0.6], [1046.5, 0.72]];
    for (const [freq, quando] of melodia) {
      tom(audio, t + quando, { freq, duracao: quando === 0.72 ? 0.6 : 0.11, volume: 0.09 });
    }
  },
};

export const som = {
  tocar(tipo = "clique") {
    if (!guardado.som()) return;
    const audio = obterContexto();
    if (!audio) return;
    if (audio.state === "suspended") audio.resume();

    const agora = audio.currentTime;
    if (efeitos[tipo]) {
      efeitos[tipo](audio, agora);
      return;
    }

    const longo = tipo === "sucesso";
    const forma = tipo === "erro" || tipo === "aviso" ? "sawtooth" : "square";
    (notas[tipo] || notas.clique).forEach((freq, indice) => {
      tom(audio, agora + indice * 0.07, { freq, forma, duracao: longo ? 0.13 : 0.09, volume: 0.1 });
    });
  },
};

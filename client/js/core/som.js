import { guardado } from "./api.js";

let contexto;

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

function obterContexto() {
  if (!contexto) {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return null;
    contexto = new AudioContext();
  }
  return contexto;
}

export const som = {
  tocar(tipo = "clique") {
    if (!guardado.som()) return;
    const audio = obterContexto();
    if (!audio) return;
    if (audio.state === "suspended") audio.resume();

    const agora = audio.currentTime;
    (notas[tipo] || notas.clique).forEach((frequencia, indice) => {
      const oscilador = audio.createOscillator();
      const volume = audio.createGain();
      const inicio = agora + indice * 0.07;

      oscilador.type = tipo === "erro" || tipo === "aviso" ? "sawtooth" : "square";
      oscilador.frequency.setValueAtTime(frequencia, inicio);
      volume.gain.setValueAtTime(0.0001, inicio);
      const intensidade = 0.1 * Math.max(0, Math.min(100, guardado.volumeSom())) / 100;
      volume.gain.exponentialRampToValueAtTime(Math.max(0.0001, intensidade), inicio + 0.01);
      volume.gain.exponentialRampToValueAtTime(0.0001, inicio + (tipo === "sucesso" ? 0.13 : 0.09));
      oscilador.connect(volume).connect(audio.destination);
      oscilador.start(inicio);
      oscilador.stop(inicio + (tipo === "sucesso" ? 0.14 : 0.1));
    });
  },
};
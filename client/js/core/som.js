import { guardado } from "./api.js";

let contexto;

const notas = {
  clique: [440],
  confirmar: [523.25, 659.25],
  voltar: [392, 293.66],
  erro: [180, 140],
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
    notas[tipo].forEach((frequencia, indice) => {
      const oscilador = audio.createOscillator();
      const volume = audio.createGain();
      const inicio = agora + indice * 0.07;

      oscilador.type = tipo === "erro" ? "sawtooth" : "square";
      oscilador.frequency.setValueAtTime(frequencia, inicio);
      volume.gain.setValueAtTime(0.0001, inicio);
      const intensidade = 0.1 * Math.max(0, Math.min(100, guardado.volumeSom())) / 100;
      volume.gain.exponentialRampToValueAtTime(Math.max(0.0001, intensidade), inicio + 0.01);
      volume.gain.exponentialRampToValueAtTime(0.0001, inicio + 0.09);
      oscilador.connect(volume).connect(audio.destination);
      oscilador.start(inicio);
      oscilador.stop(inicio + 0.1);
    });
  },
};
/* Casa Coringa: arriscar ou deixar quieto.

   "A tela faz metade do trabalho" (REGRAS, seção 10): o jogador vê os dois
   futuros com os números dele antes de escolher — quanto fica se ganhar,
   quanto fica se perder, e a chance. Sem isso ele aposta no escuro e não
   sente nada. */

import { api } from "../core/api.js";
import { elemento, porcento, reais } from "../ui/comum.js";

const FAIXAS = {
  atras: "Você está atrás na mesa, e a sorte está do seu lado.",
  na_media: "Você está na média da mesa.",
  frente: "Você lidera a mesa, e a Coringa cobra caro de quem está na frente.",
};

function futuro(classe, rotulo, valor, depois) {
  const caixa = elemento("div", `futuro futuro--${classe}`);
  caixa.append(
    elemento("span", "futuro__rotulo", rotulo),
    elemento("strong", "futuro__valor", valor),
    elemento("span", "futuro__depois", depois),
  );
  return caixa;
}

export function decisaoDoCoringa(pendente, codigo) {
  const chance = elemento("div", "chance");
  chance.style.setProperty("--chance", porcento(pendente.chance));
  chance.append(
    elemento("strong", "chance__valor", porcento(pendente.chance)),
    elemento("span", "chance__rotulo", "de chance de ganhar"),
    elemento("span", "chance__barra"),
  );

  const futuros = elemento("div", "futuros");
  futuros.append(
    futuro("ganhar", "Se ganhar", `+${reais(pendente.ganho)}`, `fica com ${reais(pendente.caixa + pendente.ganho)}`),
    futuro("perder", "Se perder", `−${reais(pendente.perda)}`, `fica com ${reais(pendente.caixa - pendente.perda)}`),
  );

  return {
    chave: `coringa:${pendente.casa}:${pendente.caixa}:${pendente.chance}`,
    chamada: "Casa Coringa",
    titulo: "Arrisca ou deixa quieto?",
    corpo: [
      elemento("p", "decisao__texto", `Você tem ${reais(pendente.caixa)} em caixa. ${FAIXAS[pendente.faixa] || ""}`),
      chance,
      futuros,
    ],
    acoes: [
      { rotulo: "Deixar quieto", classe: "compra__recusar", acao: () => api.decidirCoringa(codigo, false) },
      { rotulo: "Arriscar!", classe: "compra__aceitar", acao: () => api.decidirCoringa(codigo, true) },
    ],
  };
}

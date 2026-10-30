/* Bônus do banco: quem está na região sorteada vende uma propriedade ao
   banco acima do valor. Uma vez por evento.

   A janela abre de dois jeitos: sozinha, quando o peão termina o movimento
   na região (aí "Não vender" passa a vez), ou pelo botão embaixo do JOGAR,
   para quem começou a vez lá dentro (aí "Voltar" só fecha e a vez segue). */

import { api } from "../core/api.js";
import { elemento, reais } from "../ui/comum.js";

export function decisaoDoBonus({ estado, tabuleiro, eu, codigo, naDecisao }) {
  const minhas = Object.entries(estado.propriedades || {})
    .filter(([, posse]) => posse.dono === eu?.jogador_id && posse.valor_bonus != null)
    .map(([indice, posse]) => ({ casa: tabuleiro.casas[Number(indice)], posse }))
    .sort((a, b) => b.posse.valor_bonus - a.posse.valor_bonus);

  return {
    chave: `bonus:${naDecisao ? "fim" : "inicio"}:${minhas.map(({ casa }) => casa.i).join(",")}`,
    chamada: "Bônus do banco",
    titulo: "Venda ao banco acima do valor",
    corpo: [
      elemento("p", "decisao__texto", "Você está na região sorteada. Escolha uma propriedade para vender ao banco com bônus — só uma, e só nesta rodada."),
    ],
    opcoes: minhas.map(({ casa, posse }) => ({
      rotulo: casa?.nome || "Propriedade",
      detalhe: `recebe ${reais(posse.valor_bonus)} · vale ${reais(posse.preco_compra)}`,
      acao: () => api.venderNoBonus(codigo, casa.i),
    })),
    acoes: [
      naDecisao
        ? { rotulo: "Não vender", classe: "compra__recusar", acao: () => api.venderNoBonus(codigo, null) }
        : { rotulo: "Voltar", classe: "compra__recusar", acao: async () => null },
    ],
  };
}

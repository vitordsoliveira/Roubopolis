/* Casa da Reconstrução: um nível a mais numa propriedade própria, com
   desconto. A lista vem pronta do motor, com custo e aluguel de cada uma. */

import { api } from "../core/api.js";
import { elemento, porcento, reais } from "../ui/comum.js";

export function decisaoDaReconstrucao(pendente, { tabuleiro, eu, codigo }) {
  const opcoes = pendente.opcoes.map((opcao) => {
    const nome = tabuleiro.casas[opcao.casa]?.nome || "Propriedade";
    const cabe = opcao.custo <= (eu?.caixa || 0);
    return {
      rotulo: `${nome} · nível ${opcao.nivel} → ${opcao.nivel + 1}`,
      detalhe:
        `${reais(opcao.custo)} (era ${reais(opcao.custo_cheio)}) · aluguel ${reais(opcao.aluguel_atual)} → ${reais(opcao.aluguel_novo)}`
        + (cabe ? "" : " · falta caixa"),
      desabilitada: !cabe,
      acao: () => api.decidirReconstrucao(codigo, opcao.casa),
    };
  });

  return {
    chave: `reconstrucao:${pendente.casa}:${pendente.opcoes.map((o) => `${o.casa}-${o.nivel}`).join(",")}`,
    chamada: "Casa da Reconstrução",
    titulo: `Reforma com ${porcento(pendente.desconto)} de desconto`,
    corpo: [
      elemento("p", "decisao__texto", `Escolha uma propriedade sua para subir um nível pagando menos. Seu caixa: ${reais(eu?.caixa)}.`),
    ],
    opcoes,
    acoes: [
      { rotulo: "Não reformar", classe: "compra__recusar", acao: () => api.decidirReconstrucao(codigo, null) },
    ],
  };
}

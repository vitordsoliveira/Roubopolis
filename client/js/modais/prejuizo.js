/* Casa do Prejuízo: quem pisou escolhe qual propriedade média ou barata de
   quem lidera a mesa volta para o banco. Metade do valor vai para o Coletor.

   É a jogada mais "na frente de todo mundo" do jogo: o nome do líder vai no
   título, e o valor de cada casa e o quanto ela põe no Coletor, na lista. */

import { api } from "../core/api.js";
import { elemento, reais } from "../ui/comum.js";

export function decisaoDoPrejuizo(pendente, { estado, tabuleiro, codigo }) {
  const alvo = estado.jogadores.find((jogador) => jogador.jogador_id === pendente.alvo_id);
  const souOAlvo = Boolean(alvo?.sou_eu);
  const texto = souOAlvo
    ? "Quem lidera a mesa toma o golpe, mesmo quando é quem pisa. Escolha qual propriedade média ou barata sua volta para o banco."
    : `${alvo?.nome || "Quem lidera"} tem o maior patrimônio da mesa. Escolha qual propriedade média ou barata volta para o banco.`;

  return {
    chave: `prejuizo:${pendente.casa}:${pendente.alvo_id}:${pendente.opcoes.map((o) => o.casa).join(",")}`,
    chamada: "Casa do Prejuízo",
    titulo: souOAlvo ? "Você lidera: escolha o que perder" : `Golpe em ${alvo?.nome || "quem lidera"}`,
    corpo: [
      elemento("p", "decisao__texto", `${texto} Metade do valor vai para o Coletor de Impostos.`),
      elemento("p", "decisao__texto", "Se o tempo acabar, sai a mais valiosa da lista."),
    ],
    opcoes: pendente.opcoes.map((opcao) => ({
      rotulo: tabuleiro.casas[opcao.casa]?.nome || "Propriedade",
      detalhe: `vale ${reais(opcao.valor)} · ${reais(opcao.ao_coletor)} para o Coletor`,
      acao: () => api.escolherPrejuizo(codigo, opcao.casa),
    })),
    acoes: [],
  };
}

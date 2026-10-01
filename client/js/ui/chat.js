/* Chat da sala — o mesmo no lobby e na partida.

   As mensagens moram no banco e pertencem à SALA, não à tela: por isso a
   conversa do lobby continua dentro da partida. A atualização é por
   consulta a cada poucos segundos, como o resto do jogo; quando existir
   socket (server/sockets/chat.py), só `iniciar` muda.

   Quem usa entrega os elementos da própria tela e decide o que fazer
   quando chega mensagem nova — o lobby não faz nada, a partida acende o
   botão do chat. */

import { api } from "../core/api.js";
import { som } from "../core/som.js";
import { toast } from "./toast.js";

const INTERVALO_MS = 2500;

function elemento(tag, classe, texto) {
  const el = document.createElement(tag);
  if (classe) el.className = classe;
  if (texto !== undefined) el.textContent = texto;
  return el;
}

/**
 * @param {object} opcoes
 * @param {string} opcoes.codigo  código da sala
 * @param {HTMLElement} opcoes.lista  onde as mensagens são desenhadas
 * @param {HTMLFormElement} opcoes.formulario
 * @param {HTMLInputElement} opcoes.campo
 * @param {HTMLElement} opcoes.status  "3 mensagens" ou "Chat indisponível"
 * @param {(jogadorId: number) => (string | null)} [opcoes.corDe]  cor do nome de cada autor
 * @param {(novas: object[]) => void} [opcoes.aoChegar]  mensagens que ainda não estavam na tela
 */
export function montarChat({ codigo, lista, formulario, campo, status, corDe = () => null, aoChegar = () => {} }) {
  let consulta = null;
  /** Maior id já desenhado. `null` até a primeira leitura. */
  let ultimoId = null;

  function pintar(mensagens) {
    // Só arrasta a lista para baixo se a pessoa já estava lendo o fim; quem
    // subiu para reler uma mensagem antiga não perde o lugar.
    const estavaNoFim = lista.scrollTop + lista.clientHeight >= lista.scrollHeight - 24;
    lista.replaceChildren();
    if (!mensagens.length) {
      lista.appendChild(elemento("li", "chat__vazio", "Nenhuma mensagem ainda."));
    } else {
      for (const mensagem of mensagens) {
        const item = elemento("li", "chat__mensagem");
        const nome = elemento("strong", "chat__nome", mensagem.nome);
        const cor = corDe(mensagem.jogador_id);
        if (cor) nome.style.color = cor;
        item.append(nome, elemento("span", "chat__texto", mensagem.texto));
        lista.appendChild(item);
      }
    }
    if (estavaNoFim) lista.scrollTop = lista.scrollHeight;
    status.textContent = `${mensagens.length} ${mensagens.length === 1 ? "mensagem" : "mensagens"}`;

    // Na primeira leitura tudo já é velho: quem acabou de abrir a tela não
    // precisa ser avisado do que foi dito antes de chegar.
    const maior = mensagens.reduce((m, msg) => Math.max(m, msg.id), 0);
    if (ultimoId !== null) {
      const novas = mensagens.filter((msg) => msg.id > ultimoId);
      if (novas.length) aoChegar(novas);
    }
    ultimoId = Math.max(ultimoId ?? 0, maior);
  }

  async function atualizar() {
    try {
      pintar(await api.listarChat(codigo));
    } catch {
      status.textContent = "Chat indisponível";
    }
  }

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const texto = campo.value.trim();
    if (!texto) return;
    campo.disabled = true;
    try {
      await api.enviarChat(codigo, texto);
      campo.value = "";
      await atualizar();
    } catch (erro) {
      som.tocar("erro");
      toast(erro.message, "erro");
    } finally {
      campo.disabled = false;
      campo.focus();
    }
  });

  function parar() {
    if (consulta) clearInterval(consulta);
    consulta = null;
  }

  return {
    atualizar,
    iniciar() {
      parar();
      consulta = setInterval(atualizar, INTERVALO_MS);
    },
    parar,
  };
}

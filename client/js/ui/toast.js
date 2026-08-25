/* Aviso passageiro no rodapé. Some sozinho. */

let pilha = null;

function obterPilha() {
  if (!pilha) {
    pilha = document.createElement("div");
    pilha.className = "toast-pilha";
    pilha.setAttribute("role", "status");
    pilha.setAttribute("aria-live", "polite");
    document.body.appendChild(pilha);
  }
  return pilha;
}

/**
 * @param {string} mensagem
 * @param {"" | "ok" | "erro"} tipo
 * @param {number} duracao em milissegundos
 */
export function toast(mensagem, tipo = "", duracao = 3200) {
  const caixa = document.createElement("div");
  caixa.className = "toast" + (tipo ? ` toast--${tipo}` : "");
  caixa.textContent = mensagem;
  obterPilha().appendChild(caixa);

  setTimeout(() => {
    caixa.classList.add("toast--saindo");
    caixa.addEventListener("animationend", () => caixa.remove(), { once: true });
  }, duracao);
}

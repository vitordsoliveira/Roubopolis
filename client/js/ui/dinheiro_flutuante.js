/* O dinheiro entrando e saindo, contado na tela.

   Quando o caixa de alguém muda, a diferença sobe do cartão dele
   ("+R$ 1.500" em verde, "−R$ 800" em vermelho) e o número do caixa corre
   do valor velho ao novo, como bomba de gasolina. O texto flutuante mora
   no <body>, posicionado pela tela: assim passa por cima de tudo sem
   depender de onde o cartão está. */

const MS_CONTAGEM = 800;
const contagens = new WeakMap();

/** Faz `diferenca` subir de cima do elemento `alvo`. */
export function flutuarDinheiro(alvo, diferenca, formatar) {
  const caixa = alvo.getBoundingClientRect();
  const ganho = diferenca > 0;
  const el = document.createElement("div");
  el.className = `dinheiro-flutuante dinheiro-flutuante--${ganho ? "ganho" : "perda"}`;
  el.setAttribute("aria-hidden", "true");
  el.textContent = `${ganho ? "+" : "−"}${formatar(Math.abs(diferenca))}`;
  el.style.left = `${caixa.left + caixa.width / 2}px`;
  el.style.top = `${caixa.top}px`;
  document.body.appendChild(el);
  el.addEventListener("animationend", () => el.remove(), { once: true });

  // O cartão reage junto: treme quando perde, pula quando ganha.
  const classe = ganho ? "dinheiro--ganhou" : "dinheiro--perdeu";
  alvo.classList.remove("dinheiro--ganhou", "dinheiro--perdeu");
  void alvo.offsetWidth; // reinicia a animação
  alvo.classList.add(classe);
  const limpar = (evento) => {
    if (evento.target !== alvo) return;
    alvo.classList.remove(classe);
    alvo.removeEventListener("animationend", limpar);
  };
  alvo.addEventListener("animationend", limpar);
}

/** Corre o texto de `el` de `de` até `para`, desacelerando no fim. */
export function contarDinheiro(el, de, para, formatar) {
  cancelAnimationFrame(contagens.get(el));
  // Já começa no valor velho: quem chamou pode ter acabado de escrever o
  // novo, e ele não pode piscar antes da contagem.
  el.textContent = formatar(de);
  const inicio = performance.now();

  function quadro(agora) {
    const t = Math.min(1, (agora - inicio) / MS_CONTAGEM);
    const suave = 1 - (1 - t) ** 3;
    el.textContent = formatar(Math.round(de + (para - de) * suave));
    if (t < 1) contagens.set(el, requestAnimationFrame(quadro));
    else contagens.delete(el);
  }
  contagens.set(el, requestAnimationFrame(quadro));
}

/** Enquanto conta, ninguém mais escreve no número — senão ele pula. */
export const contando = (el) => contagens.has(el);

# Backlog de decisões de design

Pontos em aberto do [REGRAS-DO-JOGO.md](REGRAS-DO-JOGO.md), em ordem de
resolução. A ordem não é por importância: é por **dependência**. Os primeiros
travam os outros.

**Status:** 🔴 aberto · 🟡 em discussão · 🟢 decidido

Quando um item for decidido, escreva a decisão aqui **e** atualize o
`REGRAS-DO-JOGO.md`. Este arquivo guarda o *porquê*; lá fica a regra final.

---

## Fundação — trava todo o resto

### 1. 🔴 Preço do upgrade

Nunca foi definido, e sem ele nada de dinheiro fecha: a Casa da Reconstrução
dá "30% de desconto" sobre um valor que não existe, e o patrimônio (condição
de vitória) soma "propriedades e upgrades".

**Bloqueia:** Casa da Reconstrução, cálculo de patrimônio, todo o balanço.

**Ver antes de decidir:** a análise de quantas vezes uma propriedade é pisada
por partida, na seção "A economia do jogo" abaixo. Ela muda a pergunta.

### 2. 🔴 Fórmula do aluguel

Os +15% por nível de upgrade são cumulativos sobre o aluguel base ou
compostos? E em que ordem multiplicam aluguel × upgrade × morro × evento de
fim de ano?

No pior caso o aluguel chega perto de 69% do valor da propriedade — uma
parada pode acabar com um jogador. A ordem dos fatores muda esse teto.

**Bloqueia:** qualquer simulação de balanço.

---

## Experiência — decidem que jogo é

### 3. 🔴 Falência elimina o jogador?

Com aluguel de 20%, alguém pode quebrar aos 6 minutos e passar 9 assistindo.
Em jogo de festa isso esvazia a mesa.

Alternativas: eliminado vira espectador com alguma função; ou falência vira
reset parcial (perde tudo, recomeça com o mínimo) em vez de eliminação.

### 4. 🔴 Fim da partida no meio da rodada

Se o cronômetro zera no turno do jogador 2, os jogadores 3 e 4 jogaram uma
vez a menos — e a vitória é por patrimônio. A ordem de assento decide o jogo.

Solução usual: terminar a rodada em curso.

### 5. 🔴 Coringa pode tomar propriedade?

Percentual do caixa não elimina ninguém (não dá para ficar negativo), então o
"talvez eu me ferre" ainda não existe de verdade. Para a ameaça ser real, a
perda precisaria vender propriedade ao banco a 35% quando o caixa não cobrir
— podendo quebrar o Bônus do Morro ou levar à falência.

**Depende de:** item 3 (se falência elimina, isto fica bem mais pesado).

---

## Correções pontuais — pequenas, mas viram bug se esquecidas

### 6. 🔴 Desafio é sempre EV-positivo para o desafiante

Rende +10% do valor da propriedade nas duas opções, sempre. Não é decisão, é
dinheiro grátis. E como só 1 jogador pode desafiar a cada 5 rodadas, vira
corrida de reflexo — **falta regra de desempate**.

### 7. 🔴 Desafio, opção B ilegível

A segunda variante ("o desafiado vai sortear uma parte do parte e quem chegar
primeiro nessa parte sorteada vence") não dá para implementar. E ela quebra a
simetria de −10%, que só vale se o duelo for 50/50.

Também falta: **quem vence o empate nos dados?**

### 8. 🔴 Leilão sem cooldown

O desafio tem limite de frequência, o leilão não. Como está, o jogador
atrasado pode leiloar todo turno, e o respiro vira interrupção crônica.

### 9. 🔴 Casa do Prejuízo quando quem pisa é o líder

Ele se pune a si mesmo?

### 10. 🔴 Casa Portal pode entrar em laço

Teleporta e continua os passos restantes — pode cair em outro portal, e
outro. Falta um limite.

---

## A economia do jogo — leia antes do item 1

Uma conta que muda a natureza da pergunta sobre upgrades.

O tabuleiro tem **42 casas**. Numa partida de 15 minutos com turnos de até 15
segundos, cada jogador tem entre **15 e 22 turnos**. Com 4 jogadores, os
**adversários** de uma propriedade específica param nela:

```
3 adversários × ~20 paradas ÷ 42 casas ≈ 1,4 vez por partida
```

**Cada propriedade rende aluguel cerca de uma vez e meia na partida inteira.**

Isso tem duas consequências grandes:

1. **Uma propriedade não se paga.** Comprando por V e recebendo 20% de V uma
   vez e meia, ela retorna ~30% do custo antes do jogo acabar.
2. **Comprar é neutro no patrimônio.** A vitória é por caixa + propriedades.
   Trocar R$1.000 de caixa por uma propriedade de R$1.000 não muda nada. O
   mesmo vale para o upgrade, se ele somar ao valor da propriedade.

Ou seja: as únicas fontes reais de patrimônio são **aluguel recebido, eventos,
Coletor de Impostos, Coringa, desafios e leilões** — e não a compra de
terrenos, que é o tema do jogo.

**A pergunta do item 1 deixa de ser "quanto custa o upgrade" e passa a ser
"como fazer propriedade valer a pena num jogo curto".** Caminhos possíveis:

- Aluguel **por rodada** (renda passiva), não só ao pisar
- Tabuleiro menor (as casas brancas "nada a fazer" viram propriedades)
- Partida mais longa
- Upgrade que valha **mais** que o preço pago (aí ele gera patrimônio)

Nada disso está decidido. É o item 1.

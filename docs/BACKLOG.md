# Backlog de decisões de design

Pontos em aberto do [REGRAS-DO-JOGO.md](REGRAS-DO-JOGO.md), em ordem de
resolução. A ordem não é por importância: é por **dependência**. Os primeiros
travam os outros.

**Status:** 🔴 aberto · 🟡 em discussão · 🟢 decidido

Quando um item for decidido, escreva a decisão aqui **e** atualize o
`REGRAS-DO-JOGO.md`. Este arquivo guarda o *porquê*; lá fica a regra final.

---

## Fundação — trava todo o resto

### 1. 🟢 Preço do upgrade

Decisão: cada nível custa **25% do preço de tabela da propriedade**, igual em
todos os níveis, até o limite de três. Os três níveis custam 75% do terreno.
A melhoria é oferecida logo depois de comprar a propriedade e quando o dono
cai nela de novo (um nível por oferta). Só na visita era rara demais: menos de
uma melhoria por partida, mesmo com todos aceitando sempre. O que foi
pago em melhorias conta no patrimônio, entra no preço de compra entre jogadores
e na venda ao banco (valor investido = tabela + melhorias).

**Bloqueia:** Casa da Reconstrução.

### 2. 🟢 Fórmula do aluguel

Decisão atual: acréscimo linear de **50%** do aluguel-base por nível (máximo
de três), sem multiplicadores de Morro ou evento de fim de ano ativos ainda.
Aluguel máximo configurado neste momento: 50% do valor de tabela.

Era 15%. Simulação de 400 partidas (4 jogadores, 10 rodadas, bots que compram
tudo): cada propriedade recebe menos de uma visita por partida, então +15% nunca
pagava a melhoria. Quem melhorava venceu 2/400. Com +50% e a melhoria contando
no patrimônio, venceu ~120/400 quando ninguém comprava de outro jogador.

---

## Experiência — decidem que jogo é

### 3. 🟢 Falência elimina o jogador?

Decisão: quem não consegue pagar aluguel depois de vender propriedades ao banco
é eliminado; os demais continuam. A duração padrão de 15 minutos limita o
tempo de espectador.

### 4. 🟢 Fim da partida no meio da rodada

Decisão: a partida padrão dura 15 minutos. Quando o cronômetro zera, a rodada
em andamento é concluída por todos os jogadores ativos; então vence quem tiver
maior patrimônio (caixa + valor investido nas propriedades, isto é, tabela +
melhorias). Empates compartilham a vitória. Implementado no motor em
`engine/partida.py`.

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

## A economia do jogo — medir antes de rebalancear

A duração padrão agora é **15 minutos**, com turnos limitados a **30 segundos**;
ao zerar o cronômetro, os jogadores concluem a rodada atual e vence o maior
patrimônio. A estimativa anterior de 15–22 turnos por pessoa pressupunha turnos
de 15 segundos e não era uma medição. Como decisões de compra e liquidação têm
seus próprios prazos, ainda não temos uma estimativa confiável de quantas vezes
cada propriedade será visitada por partida.

Também não dá para dizer quantas vezes cada propriedade rende aluguel sem
simulador e dados de partidas. O tabuleiro tem **40 casas**, mas a frequência de
visita depende da distribuição dos dados, número de jogadores, duração efetiva
das decisões e falências. Implementar métricas reproduzíveis de visitas,
aluguéis, caixa, patrimônio e duração é pré-requisito para rebalancear números.

Até lá, qualquer afirmação sobre retorno médio de propriedade ou preço ideal de
upgrade deve ser tratada como hipótese, não como resultado medido.

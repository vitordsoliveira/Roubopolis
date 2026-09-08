# Roubopolis — regras do jogo

Especificação de design. O `engine/` ainda não implementa nada disto — este é
o alvo. Onde um wireframe discordar deste documento, **este documento manda**:
os wireframes foram desenhados antes das regras.

Pontos ainda em aberto estão marcados com **⚠ EM ABERTO**.

---

## 1. Conceito

Uma vila está sendo reconstruída e investidores disputam os terrenos ao redor.
Os jogadores compram terrenos, constroem propriedades e cobram aluguel uns dos
outros.

## 2. Condições de vitória

- **Por tempo (padrão):** quando o cronômetro zera, vence quem tiver o maior
  patrimônio total (dinheiro em caixa + valor de todas as propriedades e
  upgrades).
- **Antecipada:** se todos os outros falirem, a partida acaba na hora.
- **Falência:** quem não consegue pagar uma dívida e não tem patrimônio para
  cobri-la é eliminado. Suas propriedades voltam ao banco e ficam à venda.

**⚠ EM ABERTO:** se o cronômetro zera no meio da rodada, os últimos jogadores
jogam menos vezes que os primeiros. Numa vitória por patrimônio isso é
injusto. Solução usual: terminar a rodada em curso.

## 3. Fluxo do turno

1. O jogador rola os dados e move.
2. A casa onde parou é resolvida (compra, aluguel, evento ou nada).
3. Ações livres, se estiver habilitado: leilão, desafio ou upgrade.
4. O turno passa.

**Limite: 15 segundos por turno.** Estourou, executa a ação padrão — não
comprar, não desafiar.

## 4. Propriedades

Cinco grupos, do mais caro ao mais barato: **Extremamente caro · Muito caro ·
Caro · Médio · Barato**.

- **Aluguel base:** 20% do valor da propriedade.
- **Upgrade:** máximo de 3 níveis; cada nível aumenta o aluguel em 15%.

**⚠ EM ABERTO:** o **preço do upgrade nunca foi definido** — e a Casa da
Reconstrução dá 30% de desconto sobre esse valor inexistente. Também falta
dizer se os +15% são cumulativos sobre o aluguel base ou compostos, e em que
ordem multiplicam aluguel × upgrade × morro × evento de fim de ano. No topo
isso chega a ~69% do valor da propriedade por aluguel.

## 5. Bônus do Morro

Quanto mais morros um jogador controla, maior o aluguel de todos eles:

| Morros | Multiplicador |
|---|---|
| 2 | 1,2× |
| 3 | 1,4× |
| 4 | 1,8× |
| 5 ou mais | 2,0× |

## 6. Leilão

Ferramenta de recuperação para quem está ficando para trás.

**Quem pode:** apenas jogadores com patrimônio **abaixo de 60% da média** dos
jogadores vivos.

O jogador põe uma propriedade sua em leilão; os demais dão lances por **12
segundos**; o maior lance leva. O comprador paga o lance ao vendedor, mais
**2% de imposto calculado sobre o valor de tabela** — não sobre o valor
arrematado. O imposto vai para o Coletor de Impostos.

Se ninguém der lance, o banco compra por **35% do valor de tabela**.

**⚠ EM ABERTO:** o leilão **não tem cooldown** (o desafio tem). Como está, o
jogador atrasado pode leiloar todo turno.

## 7. Desafio

Ferramenta de pressão para quem está atrás. Não transfere propriedade —
transfere dinheiro.

**Quem pode:** patrimônio **abaixo da média** da mesa.
**Frequência:** uma vez a cada 5 rodadas por jogador, e **só 1 desafiante a
cada 5 rodadas** na mesa inteira.

O desafiante escolhe uma propriedade de outro jogador e paga **15% do valor ao
dono** — que fica com esse valor aconteça o que acontecer. O desafiado então
escolhe:

- **Opção A — pagar para encerrar:** paga 25% ao desafiante. Líquido: **−10%**.
- **Opção B — aceitar o duelo:** ambos rolam os dados, maior soma vence.
  Vencendo, fica com os 15% (**+15%**); perdendo, paga 50% (**−35%**).
  Média: **−10%**.

*Nota de design:* as duas opções custam o mesmo na média. A escolha é de
perfil, não de matemática.

**⚠ EM ABERTO — dois problemas:**

1. A Opção B tem uma segunda variante escrita de forma ilegível na
   especificação original (*"o desafiado vai sortear uma parte do parte e quem
   chegar primeiro nessa parte sorteada"*). Do jeito que está não dá para
   implementar — e ela **quebra a simetria**: a média de −10% só vale se o
   duelo for 50/50, o que dado-contra-dado é (falta regra de empate), mas
   "chegar primeiro numa região" não é.
2. **O desafio é sempre EV-positivo para o desafiante** (+10% do valor nas
   duas opções). Não existe decisão: se pode desafiar, desafia, na propriedade
   mais cara. Como só 1 jogador pode a cada 5 rodadas, vira corrida de reflexo
   entre os elegíveis — falta regra de desempate.

## 8. Casas de evento

| Casa | Efeito |
|---|---|
| **Ganho** | "Você roubou." Ganha R$1.000 na hora. |
| **Roubo** | "Você foi roubado." Perde R$500 na hora. |
| **Coletor de Impostos** | Acumula todo imposto recolhido na partida (leilões e Casa do Prejuízo). Quem pisa leva o valor inteiro e o contador zera. |
| **Portal** | Teleporta para uma casa aleatória; ao cair lá, continua os passos restantes, se houver. |
| **Prisão** | Preso por 1 rodada. |
| **Reconstrução** | Upgrade numa propriedade sua com 30% de desconto no valor do upgrade. |
| **Neutra** | Nada acontece. Serve para dar ritmo. |

**Casa do Prejuízo** — o jogador com **maior patrimônio** toma o golpe. Perde
uma propriedade de valor **médio ou inferior**, e **quem pisou escolhe qual**.
A propriedade volta ao banco e fica à venda; **50% do valor vai ao Coletor de
Impostos**. Se ele não tiver nenhuma média ou inferior, perde 15% do caixa,
que vai integralmente ao Coletor.

**⚠ EM ABERTO:** e se quem pisou for o próprio líder? Ele se pune?

**Casa Portal — ⚠ EM ABERTO:** teleporte com passos restantes pode cair em
outro portal. Falta um limite para não entrar em laço.

### Casa Coringa

O jogador escolhe entre não fazer nada ou arriscar. Ver a seção 10 — o desenho
mudou.

## 9. Eventos temáticos

Disparam aleatoriamente e afetam todos ao mesmo tempo.

- **A colheita foi ruim** — todos perdem 10% do caixa.
- **Baile na vila** — todos ganham R$800.
- **Evento de final de ano** — durante a rodada os aluguéis ficam 20% mais
  caros. Quem está preso sai imediatamente; mas se cair na prisão de novo na
  mesma partida, fica **3 rodadas** em vez de 1.
- **O Presidente passou aqui** — o Presidente Cor de Mel confisca todo o
  Coletor de Impostos. O contador zera.
- **Bônus do banco** — sorteia uma região do tabuleiro, marcada por 1 rodada
  depois de todos jogarem. Quem estiver na região pode vender uma propriedade
  ao banco por **35% acima** do valor de tabela.

**⚠ EM ABERTO — divergências com o README:** ele descreve os eventos
disparando "a cada 3 rodadas", a especificação diz "aleatoriamente"; ele fala
em `prefeito.py`, a especificação em "Presidente Cor de Mel"; ele comenta
"venda +25%", a especificação diz 35%; ele diz reconstrução por "metade do
preço", a especificação diz 30% de desconto.

## 10. Casa Coringa — escala com o bolso

**Desenho novo, decidido em 2026-09-08.** Substitui a tabela de valores fixos.

**O objetivo:** *"a pessoa fica no 50/50 nos pensamentos — se eu arriscar ganho
uma bolada, se eu perder talvez eu me ferre."*

### Por que o valor fixo não servia

R$5.000 é fixo num jogo onde a riqueza cresce: aterrorizante no minuto 2,
troco no minuto 14. E "perder R$3.500" é um número — ninguém se apavora com
número. As pessoas se apavoram com "vou perder a Copacabana".

### O desenho

A aposta é **percentual do caixa**, e o jogador **escolhe o tamanho**:

| Aposta | Se ganhar | Se perder |
|---|---|---|
| Trocado | +25% do caixa | −20% do caixa |
| Bolada | +60% do caixa | −45% do caixa |
| Tudo ou nada | +120% do caixa | −85% do caixa |

Com 40% de chance, as três dão **EV ≈ zero**. Não diferem em lucro, só em
**variância** — mesma filosofia do Desafio: a escolha é de perfil, não de
matemática.

A chance é a alavanca de recuperação:

| Faixa (patrimônio ÷ média da mesa) | Chance de ganhar |
|---|---|
| Abaixo de 60% | 55% |
| De 60% a 150% | 40% |
| Acima de 150% | 25% |

### Piso

Percentual puro quebra para quem está quebrado: 45% de R$200 é R$90, e a casa
some justo no caso de recuperação. Precisa de um **piso** (~R$500 como ponto de
partida) como base mínima de cálculo, com a perda sempre limitada ao caixa,
para não haver saldo negativo.

### ⚠ EM ABERTO — o "me ferro"

Percentual do caixa sozinho **não te ferra**: perder 85% dói, mas você
sobrevive. Para a ameaça ser real, a perda precisaria poder **comer
propriedade** — se o caixa não cobrir, vender ao banco a 35% até quitar. Aí
perder pode quebrar o Bônus do Morro ou levar à falência.

Não inventa vocabulário: a Casa do Prejuízo já tira propriedade, e o leilão já
tem o banco comprando a 35%. **Ainda não decidido.**

### A UI faz metade do trabalho

A tela precisa mostrar os dois futuros com os números reais da pessoa, antes
da escolha:

```
Você tem R$ 12.400 em caixa.
  BOLADA — 40% de chance
  ganhar  →  R$ 19.840   (+7.440)
  perder  →  R$  6.820   (−5.580)
```

Sem isso o jogador aposta no escuro e não sente nada.

## 11. Tabuleiro

Grade **11×12**, 42 casas na borda. Bairros reais de São Paulo e Rio; becos e
vielas são o grupo barato. **INICIAL** no canto inferior esquerdo, **PRISÃO**
no inferior direito.

**Linha de cima:** Av. Faria Lima · Jardins · CASA DO PREJUÍZO · Itaim Bibi ·
Av. Augusta · (vazia) · Tatuapé · CASA DO ROUBO · Beco da Ladeira · Viela do
Zé · Rua da Laje

**Coluna esquerda:** Beira Mar Leblon · CASA DO GANHO · Barra da Tijuca ·
(vazia) · Vila Olímpia · CASA DA RECONSTRUÇÃO · Ipanema · (vazia) · Pinheiros ·
Santana

**Coluna direita:** Escadão · (vazia) · (vazia) · CASA CORINGA · Rua do Bailão ·
Beco da Quadra · Viela do Bar · CASA PORTAL · Copacabana · Botafogo

**Linha de baixo:** INICIAL · Madureira · Moema · CASA DO IMPOSTO · Méier ·
(vazia) · Vila Madalena · Beco do Mandelão · (vazia) · Tijuca · PRISÃO

### Easter eggs

Duas casas trazem um evento extra com **5% de chance**. São piadinhas sobre São
Paulo e o texto é intencional — não "melhorar", a graça está na referência.

- Perto da **Av. Augusta**: *"você fica encantado com uma bela pessoa, e perde
  R$450"*
- Perto do **Beco do Mandelão**: *"você fica bêbado e te furtam, perde R$450"*

**⚠ A conferir:** a contagem por grupo bate com o README (2 extremamente
caras, 5 muito caras, 6 caras, 5 médias, 8 becos = 26 propriedades)? O
wireframe parece ter mais casas brancas do que isso sugeria. E confirmar que o
grupo barato (becos, vielas, escadão, rua da laje) é o mesmo do **Bônus do
Morro** — o multiplicador de até 2,0× depende disso.

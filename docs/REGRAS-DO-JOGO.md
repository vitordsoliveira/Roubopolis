# Roubopolis — regras do jogo

Especificação de design. O motor já sorteia quem começa, rola, movimenta,
permite comprar terrenos sem dono, comprar ou pagar aluguel ao cair em
propriedade de outro jogador, melhorar a própria casa, e aplica o bônus do
Morro (seção 5), o leilão (seção 6), as casas de evento (seção 8) e os
eventos temáticos (seção 9). Ainda **não** está no motor: o desafio (seção 7).
Onde um wireframe discordar deste documento, **este documento manda**: os
wireframes foram desenhados antes das regras.

Todo valor citado aqui mora em `data/balanceamento/padrao.json` e pode ser
ajustado lá sem mexer em código. As regras originais usavam valores pequenos
(Ganho de R$ 1.000); na economia de R$ 2 milhões, todo valor fixo foi
multiplicado por 200, o mesmo fator que o Ganho e o Roubo já usavam.

Pontos ainda em aberto estão marcados com **⚠ EM ABERTO**.

---

## 1. Conceito

Uma vila está sendo reconstruída e investidores disputam os terrenos ao redor.
Os jogadores compram terrenos, constroem propriedades e cobram aluguel uns dos
outros.

## 2. Condições de vitória

- **Por tempo (padrão):** a partida dura 25 minutos. Quando o cronômetro zera,
  todos concluem a rodada em andamento; vence quem tiver o maior patrimônio
  (caixa + valor investido nas propriedades: tabela + melhorias). Se houver
  empate, há mais de um vencedor.
- **No fim:** a tela mostra o pódio e o placar de cada um — patrimônio,
  dinheiro arrecadado na partida inteira, casas compradas e ganho com
  aluguéis. Cada jogador recebe créditos para a loja: 100 pela vitória, 20 por
  jogar até o fim (`data/loja/catalogo.json`). Quem abandona não recebe.
- **Antecipada:** se todos os outros falirem, a partida acaba na hora.
- **Falência:** quem não consegue pagar uma dívida e não tem patrimônio para
  cobri-la é eliminado. Suas propriedades voltam ao banco e ficam à venda.

O cronômetro total começa depois do sorteio da ordem. Ao zerar, o jogo marca a
rodada corrente como a última e termina quando todos os jogadores ainda ativos
tiverem concluído seus turnos nela. Os limites de decisão e de liquidação
continuam valendo durante essa rodada final.

## 3. Fluxo do turno

1. O jogador rola os dados e move.
2. A casa onde parou é resolvida (compra, aluguel, melhoria, evento ou nada).
3. Ações livres, se estiver habilitado: leilão ou desafio.
4. O turno passa.

**Limite: 30 segundos por turno.** Estourou, executa a ação padrão — não
comprar, não desafiar.

Quando uma propriedade livre é oferecida para compra, começa um novo prazo
de **30 segundos** para decidir; se acabar, a oferta é recusada.

## 4. Propriedades

Cinco grupos, do mais caro ao mais barato: **Extremamente caro · Muito caro ·
Caro · Médio · Barato**.

- **Aluguel base:** 20% do valor da propriedade.
- **Upgrade:** máximo de 3 níveis. Cada nível custa 25% do preço de tabela
  (o mesmo custo em todos os níveis) e soma **50% do aluguel-base** ao
  aluguel: nível 1 = 30% da tabela, nível 2 = 40%, nível 3 = 50%.
- **Quando melhorar:** só com o peão na casa, um nível por vez, como no
  Business Tour. A oferta aparece logo **depois de comprar** a propriedade
  (do banco ou de outro jogador) e quando o dono **cai de novo nela**. Há o
  mesmo prazo de 30 segundos da compra; se acabar, a melhoria é recusada.
  Sem caixa para o custo, ou já no nível 3, não há oferta.
- **No tabuleiro:** cada nível põe um andar a mais no prédio da casa, com uma
  laje marcando a emenda.
- **Valor investido** de uma propriedade = preço de tabela + o que já foi pago
  em melhorias. É esse valor que conta no patrimônio, que outro jogador paga
  para comprá-la e sobre o qual o banco calcula a venda. Melhoria é
  investimento: não some do placar e não passa de graça para quem compra a
  casa.
- **Escala da economia:** cada jogador começa com R$ 2.000.000 e recebe
  R$ 300.000 ao cruzar o Início.
- Ao parar em um terreno sem dono, o jogador pode comprá-lo pelo preço da
  tabela. Se recusar ou não tiver saldo suficiente, o terreno continua sem
  dono e sem casa.
- Ao cair numa propriedade de outro jogador, o jogador da vez pode comprá-la
  pelo **valor investido**, desde que tenha saldo suficiente. A oferta aparece
  apenas nessa situação; não é possível iniciar compras clicando em outras casas
  nem fora da própria vez. Se confirmar, o valor sai do caixa do comprador e
  entra no caixa do dono anterior, e a propriedade muda de dono com as
  melhorias. Não há cobrança adicional de aluguel nessa jogada. Se recusar ou
  o prazo acabar, paga aluguel ao dono e a vez passa. Quem não tiver saldo para
  comprar também paga o aluguel automaticamente.
- Se o caixa não cobrir o aluguel, o jogador escolhe propriedades próprias para
  vender ao banco, uma por vez, por 35% do valor investido. Cada venda aumenta
  o caixa; quando houver saldo suficiente, o aluguel é pago e a vez passa.
- Se todas as propriedades forem vendidas e ainda faltar dinheiro, o saldo
  restante é entregue ao dono como pagamento parcial, o jogador vai à falência,
  é eliminado e suas propriedades restantes voltam ao banco. Os demais jogadores
  continuam; se sobrar apenas um jogador ativo, a partida termina. Se o prazo de
  liquidação acabar, o jogador vai à falência automaticamente.

**Por que +50% por nível, e não os +15% de antes:** numa simulação de 400
partidas com 4 jogadores, cada propriedade recebeu menos de uma visita por
partida. Com +15%, a melhoria nunca se pagava e quem melhorava casas venceu 2
de 400 partidas (o justo seria ~100). Com +50% e a melhoria contando no
patrimônio, melhorar passa a ser uma aposta boa, mas não obrigatória.

Todos esses percentuais ficam em `data/balanceamento/padrao.json`.

Quem **abandona** a partida sai da roda como na falência: os terrenos voltam
ao banco (antes ficavam no tabuleiro sem cobrar aluguel nem aceitar compra).

## 5. Bônus do Morro

O Morro são as **casas de favela** — o grupo barato: Capão Redondo, Itaquera,
Brasilândia, Parelheiros e Cidade Tiradentes (`morro.grupo` no
balanceamento). Quanto mais delas o mesmo dono tem, maior o aluguel de todas:

| Casas do Morro | Multiplicador |
|---|---|
| 2 | 1,2× |
| 3 | 1,4× |
| 4 | 1,8× |
| 5 | 2,0× |

O multiplicador vale sobre o aluguel já com as melhorias, e soma com o
evento de final de ano. Comprar a casa que liga ou aumenta o bônus avisa a
mesa; o painel de cada casa do Morro mostra quantas o dono tem e o
multiplicador atual. Na legenda, o grupo aparece como "Barata · Morro".

## 6. Leilão

Ferramenta de recuperação para quem está ficando para trás.

**Quem pode:** apenas jogadores com patrimônio **abaixo de 60% da média** dos
jogadores vivos, com alguma propriedade.

**Quando:** no começo da própria vez, antes de rolar (botão "Leiloar
propriedade", embaixo do JOGAR). As regras originais punham as ações livres
depois da jogada; lá, todo turno de todo mundo precisaria de um "passar a
vez" a mais só para dar a chance de leiloar. Depois do leilão, quem vendeu
rola normalmente, com o prazo da vez recomeçado.

**Como:** o jogador escolhe uma propriedade sua e a mesa inteira vê a janela
do leilão (wireframe "Modais do Leilão"). Os demais dão lances por **12
segundos**; o maior lance leva, **com as melhorias**. O comprador paga o lance
ao vendedor, mais **2% de imposto calculado sobre o valor de tabela** — não
sobre o valor arrematado. O imposto vai para o Coletor de Impostos. (O
wireframe mostrava 2% do lance; vale a regra escrita.)

- O primeiro lance precisa passar da oferta do banco; os seguintes sobem de
  5% da tabela em 5%, em número redondo (`passo_do_lance`, `arredondar_para`).
- O lance mais o imposto precisam caber no caixa de quem dá o lance.
- Lance dado com menos de 5 segundos no relógio estica o leilão até 5
  segundos (`segundos_apos_lance`): com a tela consultando o servidor de
  tempos em tempos, sem isso o último a clicar levava sem ninguém ver.
- Quem vende sai da partida: o leilão é cancelado e a casa volta ao banco.
  Quem dá lance sai: os lances dele caem e o maior dos outros volta a valer.

Se ninguém der lance, o banco compra por **35% do valor investido** — a mesma
conta da venda para pagar dívida. Sem melhoria, é exatamente os 35% do valor
de tabela da regra; com melhoria, quem vende recebe também por ela.

**Decidido (2026-10-30): um leilão por rodada por jogador**
(`leilao.rodadas_entre_leiloes`). Ao fechar, todos veem a janela "Leilão
encerrado": quem arrematou, o valor, o lance, quanto economizou (ou recebeu,
para quem vendeu), o imposto e o cofre do Coletor.

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

Valores na escala atual. Perda em casa de evento **nunca passa do caixa**: o
jogador fica com zero, mas não abre liquidação nem vai à falência — só dívida
de aluguel faz isso.

**Na tela:** cada casa de evento abre, para a mesa inteira, uma janela com o
que aconteceu e uma **frase de sátira** (`data/eventos/mensagens_casas.json`,
uma lista por casa; a mesa toda lê a mesma frase). A janela fecha sozinha em
uns 5 segundos, no Continuar, no Esc ou quando quem tem a vez aperta JOGAR:
ela não segura o relógio de ninguém.

| Casa | Efeito |
|---|---|
| **Ganho** | "Você roubou." Ganha R$ 200.000 na hora. |
| **Roubo** | "Você foi roubado." Perde R$ 100.000 na hora (no máximo o que tiver em caixa). |
| **Coletor de Impostos** | Acumula todo imposto recolhido na partida: a Casa do Prejuízo e o imposto do leilão. Quem pisa leva o valor inteiro e o contador zera. O valor fica visível no alto da tela o tempo todo. |
| **Portal** | Teleporta para uma casa sorteada (qualquer uma, menos o próprio portal); de lá o peão anda os passos que faltavam, se houver. Um teleporte por jogada. |
| **Prisão** | Perde a próxima vez (uma rodada). Quem saiu pelo evento de final de ano e volta perde 3. |
| **Reconstrução** | Um nível a mais numa propriedade sua, com 30% de desconto no custo do nível. O nível conta no patrimônio pelo valor cheio. |
| **Neutra** | Nada acontece. Serve para dar ritmo. |

**Casa do Prejuízo** — o jogador com **maior patrimônio** toma o golpe. Perde
uma propriedade de valor **médio ou inferior**, e **quem pisou escolhe qual**.
A propriedade volta ao banco (sem as melhorias) e fica à venda; **50% do valor
investido dela vai ao Coletor de Impostos**. Se ele não tiver nenhuma média ou
inferior, perde 15% do caixa, que vai integralmente ao Coletor. Com uma
propriedade só possível, ela sai sem perguntar; se o tempo acabar, sai a mais
valiosa da lista. Empate no patrimônio: o golpe vai no primeiro da ordem de
jogada.

**Decidido (2026-10-29): o líder que pisa se pune.** A regra fala do maior
patrimônio, não de outro jogador — e é ele quem escolhe o que perde.

**Casa Portal — decidido (2026-10-29):** um teleporte por jogada resolve o
laço. E, por padrão, o portal só vale para **quem para nele**
(`portal.dispara_ao_passar = false`). A regra ao pé da letra (vale para quem
passa, e o peão continua os passos restantes) está pronta no motor e liga
com `true`, mas a simulação mostrou o custo: 200 partidas de 4 jogadores e 15
rodadas tiveram 14 teleportes por partida, o salário do Início caiu de 7,7
para 3,6 por partida e a Casa Coringa — logo depois do portal, no sentido do
peão — quase não foi visitada (0,3 contra 1,3).

### Casa Coringa

O jogador escolhe entre não fazer nada ou arriscar. As chances mudam conforme
a posição dele na partida — ver a seção 10.

### Easter egg

A Av. Augusta tem 5% de chance de "você fica encantado com uma bela pessoa": o
jogador perde R$ 90.000 (no máximo o que tiver em caixa).

## 9. Eventos temáticos

Disparam aleatoriamente e afetam todos ao mesmo tempo. No começo de cada
rodada, a partir da 2ª, há **25%** de chance de um acontecer; o evento vale
para a rodada inteira e aparece no alto da tela. Evento que não mudaria nada
não é sorteado (o Presidente com o Coletor vazio, o Bônus do banco sem
ninguém com propriedade).

- **A colheita foi ruim** — todos perdem 10% do caixa.
- **Baile na vila** — todos ganham R$ 160.000.
- **Evento de final de ano** — durante a rodada os aluguéis ficam 20% mais
  caros. Quem está preso sai imediatamente; mas se cair na prisão de novo na
  mesma partida, fica **3 rodadas** em vez de 1.
- **O Presidente passou aqui** — o Presidente Cor de Mel confisca todo o
  Coletor de Impostos. O contador zera.
- **Bônus do banco** — sorteia uma região de 4 casas seguidas, que fica
  acesa em dourado durante a rodada. Quem estiver nela pode vender uma
  propriedade ao banco por **35% acima** do valor investido (tabela +
  melhorias; sem melhoria, é exatamente 35% acima da tabela). Vale para quem
  começa a vez dentro da região (antes de rolar) e para quem termina o
  movimento nela. Uma venda por jogador por evento.

Quando o evento cai, a mesa inteira vê a janela dele por 8 segundos, com uma
**frase de sátira** (`data/eventos/tematicos.json`) e o efeito em números; o
selo do evento no alto da tela reabre a janela durante a rodada.

A frequência (`eventos.chance_por_rodada`) e o peso de cada evento ficam no
balanceamento. As divergências antigas com o README foram resolvidas a favor
da especificação: os eventos são aleatórios (não "a cada 3 rodadas"), é o
Presidente Cor de Mel, o bônus é de 35% e a reconstrução dá 30% de desconto.

## 10. Casa Coringa

**O que vale (2026-10-29):** a tabela da especificação original, com os
valores na escala atual. O jogador escolhe entre não fazer nada ou arriscar;
a chance de ganhar depende do patrimônio dele dividido pela média dos que
ainda jogam:

| Situação | Chance de ganhar | Ganho | Perda |
|---|---|---|---|
| Abaixo de 60% da média | 60% | R$ 1.000.000 | R$ 700.000 |
| Na média (60% a 150%) | 50% | R$ 1.000.000 | R$ 700.000 |
| Acima de 150% da média | 20% | R$ 1.000.000 | R$ 700.000 |

A perda nunca passa do caixa. A tela mostra os dois futuros com os números
reais do jogador antes da escolha; se o tempo acabar, ele não arrisca. Todos
os números ficam em `coringa` no balanceamento.

O desenho abaixo — aposta em percentual do caixa — foi a alternativa
estudada em setembro. Não está no motor; fica registrado porque o problema que
ele resolve (valor fixo pesa muito no começo e pouco no fim) continua valendo.

### Alternativa estudada: escala com o bolso

**Desenho de 2026-09-08**, não implementado.

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

### O "me ferro"

Perda limitada ao caixa **não te ferra**: dói, mas você sobrevive. Para a
ameaça ser real, a perda precisaria poder **comer propriedade** — se o caixa
não cobrir, vender ao banco a 35% até quitar. Aí perder pode quebrar o Bônus
do Morro ou levar à falência.

**Por enquanto, não (2026-10-29):** a perda para no caixa, na Coringa e em
toda casa de evento. Reabrir quando houver partidas reais para comparar.

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

Grade **11×11**, 40 casas na borda, vistas em isométrico. O desenho é o de
`img/tabuleiro/TELA TABULEIRO_5.jpg.jpeg`, com a cidade (`CIDADE.png`) no
miolo. Bairros de São Paulo. A fonte da verdade das casas é
`data/tabuleiros/vila_original.json`.

Os quatro cantos são maiores e têm cenário: **Praça** (onde os dados caem),
**Prisão**, **Mansão** e **Represa**. A **INICIAL** não fica em canto: fica no
meio da borda de baixo. O peão começa na INICIAL e percorre o tabuleiro no
sentido horário. Os índices e locais físicos das casas permanecem fixos; por
isso, a compra de um terreno continua ligada ao mesmo espaço após esta mudança.

Na ordem em que o peão anda no sentido horário, a partir da INICIAL:

O ponto inicial é a **Praça**, no canto de baixo, junto aos dados. No sentido
horário, o percurso é:

**Até a Represa:** CASA DO IMPOSTO · Itaquera · Capão Redondo · (neutra) ·
Cidade Tiradentes · Parelheiros · Vila Nova Conceição · CASA DO GANHO ·
(neutra) · REPRESA

**Até a Mansão:** (neutra) · CASA DA RECONSTRUÇÃO · Itaim Bibi · Ibirapuera ·
Jardim Paulista · CASA DO PREJUÍZO · Cidade Jardim · Vila Olímpia · (neutra) ·
MANSÃO

**Até a Prisão:** Alto de Pinheiros · Pinheiros · CASA DO ROUBO · Brasilândia ·
Moema · Brooklin · Vila Madalena · (neutra) · Vila Conceição · PRISÃO

**De volta à Praça:** Perdizes · CASA PORTAL · CASA CORINGA · Casa Verde ·
Santana · Av. Augusta · Ipiranga · Mooca · (neutra) · PRAÇA

Por grupo: 5 extremamente caras, 5 muito caras, 3 caras, 5 médias e 5
baratas — 23 propriedades.

A arte tinha erros que o arquivo corrige: Itaim Bibi fora da linha de casas,
Ipiranga e Alto de Pinheiros repetidos, Santana pintada como casa neutra e
"Brasília dia" no lugar de Brasilândia. No lugar da Ipiranga repetida
entrou a Av. Augusta; as outras vagas viraram Vila Olímpia e uma casa
neutra.

**Decidido (2026-10-30):** o Bônus do Morro vale para as casas de favela, que
são o grupo barato (`morro.grupo` no balanceamento). No tabuleiro antigo esse
grupo eram becos e vielas; neste são os bairros da periferia, desenhados como
barracos com caixa d'água.

### Easter eggs

Duas casas trazem um evento extra com **5% de chance**. São piadinhas sobre São
Paulo e o texto é intencional — não "melhorar", a graça está na referência.

- Perto da **Av. Augusta**: *"você fica encantado com uma bela pessoa, e perde
  R$450"* (R$ 90.000 na escala atual)
- Perto do **Beco do Mandelão**: *"você fica bêbado e te furtam, perde R$450"*

A Av. Augusta voltou ao tabuleiro novo, com o easter egg dela — ativo no motor.

**⚠ EM ABERTO:** o Beco do Mandelão não está no tabuleiro novo. Falta decidir
em que casa o easter egg dele passa a morar.

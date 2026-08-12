# Estrutura do Projeto

Princípio geral: **comportamento diferente vira arquivo, valor diferente vira dado.**

O motor (`engine/`) não conhece Flask, não conhece SocketIO, não conhece banco de dados. Ele recebe um estado e uma ação, devolve um estado novo. Isso é o que permite rodar 10.000 simulações sem abrir o navegador.

---

## Árvore completa

```
ROUBODOPOLIS/
│
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── run.py                          # ponto de entrada do servidor
│
├── data/                           # TUDO que é número fica aqui
│   │
│   ├── tabuleiros/
│   │   ├── vila_original.json      # as 42 casas, ordem e tipo
│   │   ├── vila_pequena.json       # variação futura (partida de 10 min)
│   │   └── schema.json             # validação da estrutura
│   │
│   ├── propriedades/
│   │   ├── extremamente_cara.json  # 2 propriedades
│   │   ├── muito_cara.json         # 5 propriedades
│   │   ├── cara.json               # 6 propriedades
│   │   ├── media.json              # 5 propriedades
│   │   └── morro_do_salve.json     # 8 becos
│   │
│   ├── personagens/
│   │   ├── personagens.json        # nome, arte, passiva
│   │   └── passivas.json           # definição das habilidades
│   │
│   ├── eventos/
│   │   ├── tematicos.json          # textos e valores dos eventos
│   │   └── mensagens_casas.json    # textos exibidos ao pisar
│   │
│   ├── balanceamento/
│   │   ├── padrao.json             # 15 min — perfil principal
│   │   ├── rapido.json             # 10 min
│   │   └── longo.json              # 25 min
│   │
│   └── i18n/
│       └── pt_br.json              # todo texto exibido ao jogador
│
├── engine/                         # MOTOR PURO — sem rede, sem banco
│   ├── __init__.py
│   │
│   ├── state/
│   │   ├── __init__.py
│   │   ├── game_state.py           # estado completo da partida
│   │   ├── player.py               # jogador: caixa, propriedades, flags
│   │   ├── property.py             # propriedade: dono, nível de upgrade
│   │   └── enums.py                # FaseDoTurno, TipoCasa, StatusJogador
│   │
│   ├── board/
│   │   ├── __init__.py
│   │   ├── loader.py               # lê os JSON e monta o tabuleiro
│   │   ├── board.py                # consulta: casa por índice, grupo, região
│   │   └── tile.py                 # representação de uma casa
│   │
│   ├── casas/                      # UM ARQUIVO POR CASA
│   │   ├── __init__.py
│   │   ├── base.py                 # interface: resolver(estado, jogador)
│   │   ├── registry.py             # mapeia tipo da casa → classe
│   │   ├── inicial.py
│   │   ├── propriedade.py          # compra e cobrança de aluguel
│   │   ├── neutra.py               # nada acontece
│   │   ├── ganho.py                # +R$1.000
│   │   ├── roubo.py                # -R$500
│   │   ├── coletor_impostos.py     # esvazia o acumulador
│   │   ├── portal.py               # sorteia destino e re-resolve
│   │   ├── prisao.py               # prende 1 ou 3 rodadas
│   │   ├── reconstrucao.py         # upgrade por metade do preço
│   │   ├── prejuizo.py             # golpe no líder
│   │   └── coringa.py              # aposta com chance dinâmica
│   │
│   ├── eventos/                    # UM ARQUIVO POR EVENTO TEMÁTICO
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── scheduler.py            # dispara a cada 3 rodadas
│   │   ├── colheita_ruim.py        # -10% do caixa de todos
│   │   ├── baile_na_vila.py        # +R$800 para todos
│   │   ├── final_de_ano.py         # aluguel +20%, saidinha da cadeia
│   │   ├── prefeito.py             # confisca o coletor de impostos
│   │   └── bonus_do_banco.py       # região marcada, venda +25%
│   │
│   ├── acoes/                      # UM ARQUIVO POR AÇÃO DO JOGADOR
│   │   ├── __init__.py
│   │   ├── base.py                 # interface: validar() + executar()
│   │   ├── rolar_dado.py
│   │   ├── mover.py
│   │   ├── comprar.py
│   │   ├── pagar_aluguel.py
│   │   ├── upgrade.py
│   │   ├── leilao.py               # abrir, dar lance, encerrar
│   │   ├── desafio.py              # iniciar, cancelar, duelar
│   │   ├── vender_ao_banco.py
│   │   └── falencia.py
│   │
│   ├── regras/                     # CÁLCULOS PUROS — sem efeito colateral
│   │   ├── __init__.py
│   │   ├── aluguel.py              # base + upgrade + bônus + modificadores
│   │   ├── patrimonio.py           # caixa + propriedades + upgrades
│   │   ├── morro_bonus.py          # multiplicador 1,2× a 2,0×
│   │   ├── elegibilidade.py        # quem pode leiloar, quem pode desafiar
│   │   ├── posicao_relativa.py     # atrás / na média / na frente
│   │   └── vitoria.py              # condição de fim de partida
│   │
│   ├── turno/
│   │   ├── __init__.py
│   │   ├── maquina_estados.py      # fases do turno
│   │   ├── transicoes.py           # tabela de transições válidas
│   │   └── timers.py               # 15s de turno, 12s de lance
│   │
│   ├── rng/
│   │   └── gerador.py              # random com seed — essencial pra simular
│   │
│   └── log/
│       └── eventos_log.py          # histórico do que aconteceu na partida
│
├── server/                         # CAMADA DE REDE
│   ├── __init__.py
│   ├── app.py                      # cria o Flask + SocketIO
│   ├── config.py
│   │
│   ├── salas/
│   │   ├── sala.py                 # uma partida em memória
│   │   ├── gerenciador.py          # criar, entrar, sair, limpar
│   │   └── convites.py             # código de sala e link de convite
│   │
│   ├── sockets/                    # UM ARQUIVO POR CANAL
│   │   ├── conexao.py              # connect, disconnect, reconexão
│   │   ├── lobby.py                # sala de espera, escolha de personagem
│   │   ├── partida.py              # ações do turno
│   │   ├── leilao.py               # lances em tempo real
│   │   ├── desafio.py              # proposta e resposta
│   │   └── chat.py
│   │
│   ├── rotas/
│   │   ├── auth.py
│   │   ├── perfil.py
│   │   ├── ranking.py
│   │   └── estatisticas.py
│   │
│   ├── db/
│   │   ├── models.py               # usuário, histórico, estatística
│   │   ├── session.py
│   │   └── migrations/
│   │
│   ├── serializers/
│   │   └── estado_publico.py       # o que cada jogador PODE ver
│   │
│   └── seguranca/
│       ├── validador_acao.py       # a ação é válida nesta fase?
│       └── rate_limit.py
│
├── client/
│   ├── index.html                  # menu principal
│   ├── lobby.html
│   ├── partida.html
│   │
│   ├── css/
│   │   ├── base/
│   │   │   ├── reset.css
│   │   │   ├── variaveis.css       # cores dos grupos, espaçamentos
│   │   │   └── tipografia.css
│   │   ├── componentes/
│   │   │   ├── botao.css
│   │   │   ├── modal.css
│   │   │   ├── card-propriedade.css
│   │   │   ├── painel-jogador.css
│   │   │   └── timer.css
│   │   └── telas/
│   │       ├── menu.css
│   │       ├── lobby.css
│   │       └── tabuleiro.css
│   │
│   ├── js/
│   │   ├── core/
│   │   │   ├── socket.js           # conexão e reconexão
│   │   │   ├── estado.js           # espelho local, somente leitura
│   │   │   └── eventos.js          # barramento interno
│   │   │
│   │   ├── tabuleiro/
│   │   │   ├── render.js           # monta a grade 11×12
│   │   │   ├── casa.js             # uma casa no DOM
│   │   │   ├── peao.js             # movimento animado
│   │   │   └── highlight.js        # região do bônus do banco
│   │   │
│   │   ├── modais/                 # UM ARQUIVO POR MODAL
│   │   │   ├── comprar.js
│   │   │   ├── leilao.js
│   │   │   ├── desafio.js
│   │   │   ├── coringa.js
│   │   │   ├── reconstrucao.js
│   │   │   ├── prejuizo.js
│   │   │   └── fim_de_partida.js
│   │   │
│   │   ├── ui/
│   │   │   ├── painel_jogadores.js
│   │   │   ├── log_partida.js
│   │   │   ├── timer.js
│   │   │   ├── dinheiro_flutuante.js   # o "+R$1.000" subindo
│   │   │   └── toast.js
│   │   │
│   │   └── telas/
│   │       ├── menu.js
│   │       ├── lobby.js
│   │       └── partida.js
│   │
│   └── assets/
│       ├── fontes/
│       ├── icones/
│       ├── personagens/
│       └── som/
│
├── sim/                            # SIMULAÇÃO DE BALANCEAMENTO
│   ├── simulador.py                # roda N partidas sem interface
│   ├── bots/
│   │   ├── base.py
│   │   ├── aleatorio.py            # compra tudo que pode
│   │   ├── ganancioso.py           # prioriza propriedade cara
│   │   ├── conservador.py          # guarda caixa
│   │   └── focado_morro.py         # testa o multiplicador do morro
│   ├── metricas/
│   │   ├── duracao.py              # quantas rodadas até o fim
│   │   ├── vitorias.py             # taxa por bot e por ordem de jogada
│   │   ├── impacto_casas.py        # quanto cada casa moveu dinheiro
│   │   └── curva_patrimonio.py     # evolução ao longo da partida
│   └── relatorios/
│       └── gerar_graficos.py
│
└── tests/
    ├── engine/
    │   ├── test_casas/             # um teste por casa
    │   ├── test_eventos/
    │   └── test_acoes/
    ├── regras/
    │   ├── test_aluguel.py
    │   ├── test_morro_bonus.py
    │   └── test_patrimonio.py
    └── integracao/
        └── test_partida_completa.py
```

## Por que `rng/gerador.py` existe

Todo `random` da partida passa por um gerador com seed. Isso permite reproduzir uma partida inteira a partir de um número, o que é o que salva você quando aparecer um bug de "o aluguel veio errado" e você precisar reproduzir o cenário exato.

---

## Ordem de construção

| Fase | O que construir | Resultado |
|---|---|---|
| 1 | `data/` + `engine/` + `sim/` | Balanceamento validado por dado |
| 2 | `client/` estático | Tabuleiro desenhado, sem lógica |
| 3 | Partida local numa aba | Jogo jogável e testável |
| 4 | `server/` completo | Multiplayer |

O multiplayer vem por último de propósito: é a parte mais trabalhosa e a que menos importa se as regras ainda estiverem quebradas.
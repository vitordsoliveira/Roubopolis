# Roubopolis — instruções para o Claude

Jogo de tabuleiro multiplayer: Flask + MySQL no servidor, Electron no cliente.
Este arquivo é lido automaticamente. As regras do jogo estão em
[docs/REGRAS-DO-JOGO.md](docs/REGRAS-DO-JOGO.md).

Código, comentários, nomes de variáveis e mensagens ao jogador **em
português**. É a convenção do projeto inteiro — siga mesmo que pareça
incomum.

---

## O jogo é 100% desktop

O jogador **nunca** abre o jogo pelo navegador. O servidor Flask fica na web
(`https://roubopolis.gteltestes.com`) e a janela do Electron carrega essa URL
— mas a página é só o meio de entrega para o aplicativo instalado, não um
modo de uso.

**Nada no `client/` deve ter caminho alternativo para quando a ponte
`window.roubodopolis` (de `electron/preload.js`) não existir.** Caminho
alternativo ali não é robustez, é máscara: esconde a ponte quebrada e produz
comportamento sutilmente errado. Dois casos reais que já custaram tempo:

- **Sair do jogo** caía em `window.close()`, que o navegador ignora em
  silêncio quando a aba não foi aberta por script. O botão parecia quebrado.
- **Tela cheia** caía em `document.requestFullscreen()`, que no Electron
  *funciona* — mas é o fullscreen do HTML, não o da janela nativa. O seletor
  da configuração e a janela real passavam a discordar sem erro nenhum.

O padrão certo está em `ponteDesktop()` + `avisarSemPonte()` em
`client/js/telas/menu.js`: sem ponte, erro visível ao jogador. **Falha
barulhenta, nunca silenciosa.**

## Nome vs. caminho

O jogo chama-se **Roubopolis** (sem o "do"). Os diretórios continuam
`Roubodopolis` — `/home/gtel/Roubodopolis` no servidor — e **não podem ser
renomeados** sem quebrar a configuração do Passenger. Textos exibidos ao
jogador: Roubopolis. Caminhos: Roubodopolis.

## Arquitetura

- **`engine/`** — motor puro: sem Flask, sem banco, sem rede. Recebe estado +
  ação, devolve estado novo. É o que permite simular 10.000 partidas sem
  abrir o navegador. **Hoje está vazio**; é a próxima fase.
- **`server/`** — Flask, rotas, banco. O `engine/` nunca importa daqui.
- **`client/`** — telas. Caminhos absolutos (`/css`, `/assets`) e scripts
  `type="module"`, servidos pelo Flask.
- **`electron/`** — só a casca. Abre a URL do servidor; não contém o jogo.
  Por isso publicar no servidor atualiza o desktop junto, sem reinstalar.
- **`data/`** — todo número que dá para ajustar sem mexer em código.

Princípio geral: **comportamento diferente vira arquivo, valor diferente vira
dado.**

## Regras técnicas que já quebraram o projeto

**Python 3.10+ é obrigatório.** `server/db/models.py` usa `Mapped[str | None]`,
e o SQLAlchemy avalia essa anotação em tempo de execução — no 3.9 o app morre
na importação, antes do primeiro request. O servidor tem `/usr/bin/python3.13`
(o padrão do sistema é 3.9: ignore).

**`requirements.txt` usa faixas, não `==`.** Os pins exatos originais
apontavam para versões inexistentes (`python-dotenv==1.2.2`) e quebraram o
deploy. A máquina de desenvolvimento e o servidor resolvem versões diferentes.

**O `.env` não vem pelo git** (está no `.gitignore`) e precisa ser criado à
mão no servidor, com `@localhost` — não o IP público — e `DEBUG=0`.

**`create_all` não adiciona coluna em tabela que já existe.** Por isso existe
`garantir_colunas()` em `server/db/criar_banco.py`. Ao acrescentar campo a um
model, rode `python -m server.db.criar_banco` no servidor, ou o erro aparece
como `Unknown column` no primeiro acesso.

**No terminal do VS Code, `ELECTRON_RUN_AS_NODE=1` está no ambiente** e faz o
binário do Electron rodar como Node puro (`require("electron")` devolve o
caminho do .exe em vez da API). Por isso os scripts npm passam por
`electron/iniciar.js`, que remove a variável. Não chame `electron .` direto.

## Publicar

Sempre como o usuário **`gtel`**, nunca root: o Passenger executa o app como
dono da pasta, e arquivo criado por root quebra o app depois — com sintoma
que só aparece horas mais tarde.

```bash
su - gtel -c 'cd ~/Roubodopolis && bash ferramentas/publicar.sh'
```

Mudou só `client/`? O `git pull` basta. Mudou Python? Precisa de
`touch tmp/restart.txt` — o Passenger mantém o código em memória. Mudou
`electron/`? Aí sim precisa de `npm run build` e reinstalar.

**Nunca edite o root de documento pela tela do cPanel.** O campo tem prefixo
fixo `/public_html/` e concatena o que você digita, produzindo lixo como
`/home/gtel/public_html/home/gtel/Roubodopolis`. O Passenger exige
`DocumentRoot = <PassengerAppRoot>/public`, em caminho real (symlink não
serve) e fora do `public_html`. Para mudar: editar
`/var/cpanel/userdata/gtel/<domínio>` e `<domínio>_SSL`, depois
`/scripts/rebuildhttpdconf && /scripts/restartsrv_httpd`.

O app de referência na mesma máquina é o **GTELSuport** — quando algo de
Passenger não funcionar, comparar com ele resolve mais rápido que teorizar.

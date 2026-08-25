/* Casca desktop do Roubodopolis.
 *
 * O Electron NÃO carrega a pasta client/ pelo disco. Duas razões:
 *   1. index.html referencia tudo por caminho absoluto (/css, /assets, /js).
 *      Em file:// isso aponta para a raiz do disco, não para o projeto.
 *   2. Os scripts são type="module", e módulo em file:// é barrado por CORS.
 *
 * Então a janela abre uma URL HTTP e o servidor Flask serve tudo — o mesmo
 * servidor que o navegador usa. Como api.js pede /api/... por caminho
 * relativo, tudo cai na mesma origem e nenhuma linha do código web muda.
 *
 * Consequência boa: quem joga pelo desktop e quem joga pelo navegador estão
 * na MESMA partida, no mesmo banco. O executável é um cliente, não uma cópia.
 */

const electron = require("electron");
const path = require("node:path");

// Em Node puro, `require("electron")` devolve o caminho do .exe em vez da
// API — acontece quando ELECTRON_RUN_AS_NODE=1 está no ambiente (o VS Code
// define isso). Sem este aviso o sintoma é um TypeError sem explicação.
if (typeof electron === "string" || !electron.app) {
  console.error(
    "Este arquivo precisa ser executado PELO Electron, não pelo Node.\n" +
      "Use:  npm run dev        (local)\n" +
      "      npm start         (produção)\n\n" +
      "Se você chamou `electron .` na mão e caiu aqui, a variável\n" +
      "ELECTRON_RUN_AS_NODE=1 está no ambiente (terminal do VS Code).\n" +
      "Os scripts do npm passam por electron/iniciar.js, que a remove."
  );
  process.exit(1);
}

const { app, BrowserWindow, Menu, shell, ipcMain } = electron;

// --------------------------------------------------------------------------
// para onde a janela aponta
// --------------------------------------------------------------------------

const SERVIDOR_PRODUCAO = "https://roubopolis.gteltestes.com";
const SERVIDOR_LOCAL = "http://127.0.0.1:5000";

const argumentos = process.argv.slice(1);
const modoLocal = argumentos.includes("--local");

/** Precedência: variável de ambiente > --local > produção. */
const enderecoServidor = (
  process.env.ROUBODOPOLIS_URL || (modoLocal ? SERVIDOR_LOCAL : SERVIDOR_PRODUCAO)
).replace(/\/+$/, "");

// Só se navega dentro desta origem. Qualquer outra vai para o navegador do
// sistema — sem isso um link no jogo abriria um site arbitrário com as
// permissões da janela do app.
const origemPermitida = new URL(enderecoServidor).origin;

const PAGINA_DE_ERRO = path.join(__dirname, "erro.html");
// Ícone do app. Fica aqui, e não em client/assets/, porque o instalador
// empacota só a pasta electron/ — ver "files" no package.json.
// O mesmo arquivo é usado em três lugares: esta janela, o .exe e o
// instalador (os dois últimos via "build.win.icon" no package.json).
const ICONE = path.join(__dirname, "icone.png");

let janela = null;

// --------------------------------------------------------------------------
// janela
// --------------------------------------------------------------------------

function criarJanela() {
  janela = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: "#12160f", // evita o flash branco antes do CSS carregar
    show: false,
    icon: ICONE,
    title: "Roubopolis",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  // Sem barra de menu: é um jogo, não um editor de texto. Os atalhos que
  // importam continuam ligados em `atalhos()`.
  Menu.setApplicationMenu(null);

  janela.once("ready-to-show", () => janela.show());

  atalhos(janela);
  travarNavegacao(janela);

  carregar();
}

function carregar() {
  janela.loadURL(enderecoServidor).catch((erro) => mostrarErro(erro.message));
}

function mostrarErro(mensagem) {
  const parametros = new URLSearchParams({
    servidor: enderecoServidor,
    mensagem: mensagem || "Não consegui alcançar o servidor.",
    local: modoLocal ? "1" : "0",
  });
  janela.loadFile(PAGINA_DE_ERRO, { search: parametros.toString() });
}

// --------------------------------------------------------------------------
// segurança de navegação
// --------------------------------------------------------------------------

function travarNavegacao(alvo) {
  // Link para fora (ex.: redes sociais) abre no navegador padrão.
  alvo.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http:") || url.startsWith("https:")) shell.openExternal(url);
    return { action: "deny" };
  });

  alvo.webContents.on("will-navigate", (evento, url) => {
    // file:// é a própria página de erro; deixa passar.
    if (url.startsWith("file://")) return;
    if (new URL(url).origin !== origemPermitida) {
      evento.preventDefault();
      shell.openExternal(url);
    }
  });

  // Servidor fora do ar, DNS errado, HTTPS quebrado: cai aqui.
  alvo.webContents.on("did-fail-load", (_e, codigo, descricao, urlQueFalhou, principal) => {
    // -3 é ABORTED: acontece em redirecionamento normal, não é falha real.
    if (!principal || codigo === -3) return;
    if (urlQueFalhou.startsWith("file://")) return;
    mostrarErro(`${descricao} (${codigo})`);
  });
}

// --------------------------------------------------------------------------
// atalhos
// --------------------------------------------------------------------------

function atalhos(alvo) {
  alvo.webContents.on("before-input-event", (evento, entrada) => {
    if (entrada.type !== "keyDown") return;

    if (entrada.key === "F11") {
      alvo.setFullScreen(!alvo.isFullScreen());
      evento.preventDefault();
      return;
    }
    if (entrada.key === "F5" || (entrada.control && entrada.key.toLowerCase() === "r")) {
      carregar();
      evento.preventDefault();
      return;
    }
    if (entrada.key === "F12") {
      alvo.webContents.toggleDevTools();
      evento.preventDefault();
    }
  });
}

// --------------------------------------------------------------------------
// ciclo de vida
// --------------------------------------------------------------------------

// Segunda instância só traz a primeira para a frente: duas janelas com o
// mesmo jogador logado dariam confusão no lobby.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!janela) return;
    if (janela.isMinimized()) janela.restore();
    janela.focus();
  });

  app.whenReady().then(() => {
    ipcMain.on("tentar-de-novo", () => carregar());

    criarJanela();

    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) criarJanela();
    });
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });
}

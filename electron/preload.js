/* Ponte entre a página e o Electron.
 *
 * A janela do jogo roda com contextIsolation e sem Node. Este arquivo é o
 * ÚNICO caminho de comunicação, e ele expõe de propósito quase nada: só o
 * que a tela de erro precisa. A página do jogo (que vem do servidor) não
 * ganha nenhum poder novo por rodar dentro do app.
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("roubodopolis", {
  /** Só a tela de erro usa: manda o processo principal recarregar a URL. */
  tentarDeNovo: () => ipcRenderer.send("tentar-de-novo"),
  sairDoJogo: () => ipcRenderer.send("sair-do-jogo"),

  /** Alterna o modo de exibição da janela a partir das configurações. */
  alternarTelaCheia: () => ipcRenderer.invoke("alternar-tela-cheia"),
  telaCheia: () => ipcRenderer.sendSync("estado-tela-cheia"),
  aoMudarTelaCheia: (callback) => ipcRenderer.on("tela-cheia-alterada", callback),

  /** Permite ao client/ detectar que está no desktop, se um dia precisar. */
  desktop: true,
  versaoApp: process.env.npm_package_version || null,
  plataforma: process.platform,
});

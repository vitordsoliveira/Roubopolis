/* Lançador do app desktop. Roda em Node puro, não no Electron.
 *
 * Existe por um motivo específico: o VS Code exporta ELECTRON_RUN_AS_NODE=1
 * para o seu próprio extension host. Qualquer terminal aberto dentro do
 * editor herda essa variável, e com ela o binário do Electron se comporta
 * como um Node comum — `require("electron")` devolve o caminho do .exe em
 * vez da API, e o main.js morre em "Cannot read properties of undefined".
 *
 * Então limpamos a variável e só então chamamos o Electron de verdade.
 * Assim `npm run dev` funciona igual no terminal do VS Code, no PowerShell
 * e no CMD.
 */

const { spawn } = require("node:child_process");

// Em Node puro este require devolve o caminho do executável do Electron.
const executavel = require("electron");

const ambiente = { ...process.env };
delete ambiente.ELECTRON_RUN_AS_NODE;

const argumentos = [".", ...process.argv.slice(2)];

const filho = spawn(executavel, argumentos, {
  stdio: "inherit",
  env: ambiente,
  windowsHide: false,
});

filho.on("close", (codigo) => process.exit(codigo ?? 0));
filho.on("error", (erro) => {
  console.error("Não consegui iniciar o Electron:", erro.message);
  console.error("Rodou `npm install`?");
  process.exit(1);
});

/* Conversa com o servidor e guarda a identidade no navegador.
   Sem senha: o token devolvido no cadastro é a credencial. Perdeu o
   localStorage, virou outro jogador. */

const CHAVE_TOKEN = "roubopolis.token";
const CHAVE_NOME = "roubopolis.nome";
/* A foto fica guardada junto do nome para o menu conseguir se desenhar
   inteiro antes de falar com o servidor — sem isso o avatar aparecia
   depois, com um salto. */
const CHAVE_FOTO = "roubopolis.foto";
const CHAVE_SOM = "roubopolis.som";
const CHAVE_VOLUME_SOM = "roubopolis.volume-som";
const CHAVE_ABA = "roubopolis.aba-propria";

/* Abas do mesmo navegador dividem o localStorage — duas abas seriam sempre o
   MESMO jogador, o que impede testar uma sala sozinho. Abrir /?novo=1 marca a
   aba para guardar a identidade no sessionStorage, que é por aba. */
function cofre() {
  try {
    if (sessionStorage.getItem(CHAVE_ABA) === "1") return sessionStorage;
  } catch {
    /* sem sessionStorage: segue no localStorage */
  }
  return localStorage;
}

function ler(chave, padrao = "") {
  // Aba anônima e navegador com dados bloqueados fazem isto lançar.
  try {
    return cofre().getItem(chave) ?? padrao;
  } catch {
    return padrao;
  }
}

function gravar(chave, valor) {
  try {
    cofre().setItem(chave, valor);
  } catch {
    /* sem armazenamento: o jogo funciona, só não lembra da pessoa */
  }
}

function apagar(chave) {
  try {
    cofre().removeItem(chave);
  } catch {
    /* idem */
  }
}

export const guardado = {
  token: () => ler(CHAVE_TOKEN),
  nome: () => ler(CHAVE_NOME),
  foto: () => ler(CHAVE_FOTO) || null,
  som: () => ler(CHAVE_SOM, "1") === "1",
  volumeSom: () => Number(ler(CHAVE_VOLUME_SOM, "100")),
  salvarToken: (valor) => gravar(CHAVE_TOKEN, valor),
  salvarNome: (valor) => gravar(CHAVE_NOME, valor),
  salvarFoto: (valor) => gravar(CHAVE_FOTO, valor || ""),
  salvarSom: (ligado) => gravar(CHAVE_SOM, ligado ? "1" : "0"),
  salvarVolumeSom: (valor) => gravar(CHAVE_VOLUME_SOM, String(valor)),

  /** Guarda tudo que o menu precisa para se desenhar sem consultar a rede. */
  salvarSessao(jogador) {
    gravar(CHAVE_TOKEN, jogador.token ?? ler(CHAVE_TOKEN));
    gravar(CHAVE_NOME, jogador.nome ?? "");
    gravar(CHAVE_FOTO, jogador.foto || "");
  },

  esquecer: () => {
    apagar(CHAVE_TOKEN);
    apagar(CHAVE_NOME);
    apagar(CHAVE_FOTO);
  },

  /** Só para testar: dá a esta aba um jogador independente das outras. */
  usarAbaPropria: () => {
    try {
      sessionStorage.setItem(CHAVE_ABA, "1");
      sessionStorage.removeItem(CHAVE_TOKEN);
      sessionStorage.removeItem(CHAVE_NOME);
      return true;
    } catch {
      return false;
    }
  },
  abaPropria: () => {
    try {
      return sessionStorage.getItem(CHAVE_ABA) === "1";
    } catch {
      return false;
    }
  },
};

export class ErroDaApi extends Error {
  constructor(mensagem, status = 0) {
    super(mensagem);
    this.status = status;
  }
}

async function pedir(caminho, { metodo = "GET", corpo } = {}) {
  const cabecalhos = { "Content-Type": "application/json" };
  const token = guardado.token();
  if (token) cabecalhos["X-Jogador-Token"] = token;

  let resposta;
  try {
    resposta = await fetch(caminho, {
      method: metodo,
      headers: cabecalhos,
      body: corpo === undefined ? undefined : JSON.stringify(corpo),
    });
  } catch {
    throw new ErroDaApi("Não alcancei o servidor. Ele está rodando?", 0);
  }

  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) {
    throw new ErroDaApi(dados.erro || `Deu erro ${resposta.status}.`, resposta.status);
  }
  return dados;
}

export const api = {
  quemSouEu: () => pedir("/api/jogador"),
  perfil: () => pedir("/api/perfil"),
  /** Campo ausente não é alterado; `remover_foto: true` apaga o avatar. */
  salvarPerfil: (dados) => pedir("/api/perfil", { metodo: "POST", corpo: dados }),
  async entrar(login, senha) {
    const jogador = await pedir("/api/auth/entrar", { metodo: "POST", corpo: { login, senha } });
    guardado.salvarSessao(jogador);
    return jogador;
  },
  async cadastrar(login, senha, nome) {
    const jogador = await pedir("/api/auth/cadastrar", {
      metodo: "POST",
      corpo: { login, senha, nome },
    });
    guardado.salvarSessao(jogador);
    return jogador;
  },
  /** Menu: manda o nome, recebe e guarda o token. */
  async identificar(nome) {
    const jogador = await pedir("/api/jogador", { metodo: "POST", corpo: { nome } });
    guardado.salvarSessao(jogador);
    return jogador;
  },
  criarSala: () => pedir("/api/salas", { metodo: "POST", corpo: {} }),
  entrarNaSala: (codigo) => pedir(`/api/salas/${codigo}/entrar`, { metodo: "POST", corpo: {} }),
  verSala: (codigo) => pedir(`/api/salas/${codigo}`),
  escolherPersonagem: (codigo, personagem) =>
    pedir(`/api/salas/${codigo}/personagem`, { metodo: "POST", corpo: { personagem } }),
  marcarPronto: (codigo, pronto) =>
    pedir(`/api/salas/${codigo}/pronto`, { metodo: "POST", corpo: { pronto } }),
  sairDaSala: (codigo) => pedir(`/api/salas/${codigo}/sair`, { metodo: "POST", corpo: {} }),
};

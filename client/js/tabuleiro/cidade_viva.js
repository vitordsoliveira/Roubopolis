/* A cidade do miolo, viva: a pelada na quadra, o policial no muro e os
   carros nas duas ruas.

   A pintura (CIDADE.png) é parada; o que se mexe é desenhado aqui, por cima,
   numa camada que usa o sistema de coordenadas da própria pintura — uma
   unidade é um pixel da CIDADE.png original. As figuras que ganharam vida
   foram APAGADAS da pintura em ferramentas/limpar_cidade.py: se esta camada
   não rodar, a cidade fica sem elas, e não com elas em dobro.

   Todas as posições abaixo foram medidas na CIDADE.png. Se a arte mudar,
   remeça aqui e em limpar_cidade.py. */

import figurantes from "/assets/tabuleiro/figurantes.json" with { type: "json" };
import { BRACO, COR_ESTRELA, ESTRELA, FARDA, MENINO, NOIA, OMBRO, POLICIAL, TIMES, TRAPO } from "./figurantes.js";
import { grupoDoMapa } from "./pixel.js";

const SVG = "http://www.w3.org/2000/svg";

/** Tamanho de um pixel dos desenhos, em pixels da pintura. Os meninos da
    pintura tinham uns 45 px de altura; os adultos, uns 48. */
const PX_MENINO = 2.3;
const PX_ADULTO = 2.1;

const sorteio = (a, b) => a + Math.random() * (b - a);
const escolher = (lista) => lista[Math.floor(Math.random() * lista.length)];
const limitar = (x, a, b) => Math.max(a, Math.min(b, x));

function no(tag, atributos = {}, pai = null) {
  const el = document.createElementNS(SVG, tag);
  for (const [nome, valor] of Object.entries(atributos)) el.setAttribute(nome, String(valor));
  if (pai) pai.appendChild(el);
  return el;
}

/** Desenho de pixel apoiado pelos pés: o meio da base fica na origem. */
function desenho(linhas, paleta, px) {
  const g = grupoDoMapa(linhas, paleta);
  g.setAttribute("transform", `scale(${px}) translate(${-linhas[0].length / 2} ${-linhas.length})`);
  return g;
}

function sombra(pai, rx, ry) {
  return no("ellipse", { rx, ry, fill: "rgba(0, 0, 0, 0.32)" }, pai);
}

/* Os gritos ("GOL!", "PÁ!") estouram, sobem um pouco e somem. */
function criarGrito(pai, classe) {
  const el = no("text", { class: `cidade-viva__grito ${classe}`, "text-anchor": "middle", visibility: "hidden" }, pai);
  return { el, x: 0, y: 0, vida: 0, dur: 0 };
}

function gritar(grito, texto, x, y, dur) {
  Object.assign(grito, { x, y, vida: 0, dur });
  grito.el.textContent = texto;
  grito.el.setAttribute("visibility", "visible");
}

function animarGrito(grito, dt) {
  if (grito.dur <= 0) return;
  grito.vida += dt;
  const t = grito.vida;
  if (t >= grito.dur) {
    grito.dur = 0;
    grito.el.setAttribute("visibility", "hidden");
    return;
  }
  const escala = t < 0.12 ? 0.4 + (t / 0.12) * 0.9 : t < 0.24 ? 1.3 - ((t - 0.12) / 0.12) * 0.3 : 1;
  grito.el.setAttribute("transform", `translate(${grito.x.toFixed(1)} ${(grito.y - t * 6).toFixed(1)}) scale(${escala.toFixed(2)})`);
  grito.el.setAttribute("opacity", Math.min(1, (grito.dur - t) / 0.3).toFixed(2));
}

/** Põe os filhos do grupo na ordem de profundidade: quem está mais embaixo
    na tela está mais perto, e passa na frente. Só mexe no DOM se a ordem
    mudou. */
function ordenarPorAltura(grupo, itens) {
  const ordem = [...itens].sort((a, b) => a.y - b.y);
  const atual = [...grupo.children];
  const els = ordem.map((i) => i.raiz);
  if (els.every((el, k) => atual[k] === el)) return;
  for (const el of els) grupo.appendChild(el);
}

// ==========================================================================
// a pelada
// ==========================================================================

/* A quadra é um paralelogramo na pintura. Os meninos vivem em coordenadas
   dela: `u` anda do canto esquerdo para o de cima (ao longo do alambrado do
   fundo), `v` do canto esquerdo para o de baixo. O gol fica na borda u = 1. */
const QUADRA = { origem: [528, 438], u: [92, -58], v: [84, 50] };

function naQuadra(u, v) {
  return [
    QUADRA.origem[0] + u * QUADRA.u[0] + v * QUADRA.v[0],
    QUADRA.origem[1] + u * QUADRA.u[1] + v * QUADRA.v[1],
  ];
}

/** A boca do gol, entre as traves, na linha u = 1. */
const GOL = { u: 1, v0: 0.38, v1: 0.74 };
const MEIO_DO_GOL = (GOL.v0 + GOL.v1) / 2;

/* Onde se pode pisar. Longe da borda de baixo (v perto de 1): lá o
   alambrado é pintado NA FRENTE da quadra, e um menino ali ficaria por cima
   dele em vez de atrás. */
const CAMPO = { u0: 0.12, u1: 0.96, v0: 0.12, v1: 0.7 };

/** Em larguras de quadra por segundo. */
const VELOCIDADE = { correndo: 0.42, conduzindo: 0.3, goleiro: 0.45, zagueiro: 0.3 };

const SAIDA = { a1: [0.36, 0.46], a2: [0.48, 0.24], z: [0.7, 0.5], g: [0.94, MEIO_DO_GOL] };
const CENTRO = [0.4, 0.47];

function criarMenino(pai, paleta, [u, v]) {
  const raiz = no("g", {}, pai);
  sombra(raiz, 7.5, 2.6);
  const corpo = no("g", {}, raiz);
  const quadros = {};
  for (const [nome, linhas] of Object.entries(MENINO)) {
    const g = desenho(linhas, paleta, PX_MENINO);
    g.setAttribute("visibility", "hidden");
    corpo.appendChild(g);
    quadros[nome] = g;
  }
  return {
    raiz, corpo, quadros, quadro: null,
    u, v, alvo: [u, v], velocidade: VELOCIDADE.correndo,
    virado: 1, relogio: Math.random(), andando: false,
    pose: null, poseAte: 0, pulo: 0, giro: 0, y: 0,
  };
}

function moverMenino(m, dt) {
  const du = m.alvo[0] - m.u;
  const dv = m.alvo[1] - m.v;
  const d = Math.hypot(du, dv);
  m.andando = d > 0.008;
  if (m.andando) {
    const passo = Math.min(d, m.velocidade * dt);
    m.u += (du / d) * passo;
    m.v += (dv / d) * passo;
    const dx = du * QUADRA.u[0] + dv * QUADRA.v[0];
    if (Math.abs(dx) > 0.3) m.virado = dx > 0 ? 1 : -1;
  }
  m.relogio += dt;
}

function pintarMenino(m, agora) {
  let quadro = "parado";
  if (m.pose && agora < m.poseAte) quadro = m.pose;
  else if (m.andando) quadro = Math.floor(m.relogio / 0.13) % 2 ? "corre1" : "corre2";
  if (quadro !== m.quadro) {
    if (m.quadro) m.quadros[m.quadro].setAttribute("visibility", "hidden");
    m.quadros[quadro].setAttribute("visibility", "visible");
    m.quadro = quadro;
  }
  const [x, y] = naQuadra(m.u, m.v);
  m.y = y;
  m.raiz.setAttribute("transform", `translate(${x.toFixed(1)} ${y.toFixed(1)})`);
  m.corpo.setAttribute(
    "transform",
    `translate(0 ${(-m.pulo).toFixed(1)}) rotate(${m.giro.toFixed(1)}) scale(${m.virado} 1)`,
  );
}

function criarBola(pai) {
  const raiz = no("g", {}, pai);
  sombra(raiz, 3.4, 1.3);
  const corpo = no("g", {}, raiz);
  no("circle", { r: 3.2, fill: "#fbfbf6", stroke: "#1a1020", "stroke-width": 0.9 }, corpo);
  no("circle", { cx: 0.8, cy: -0.6, r: 1.1, fill: "#1a1020" }, corpo);
  return { raiz, corpo, u: CENTRO[0], v: CENTRO[1], h: 0, giro: 0, y: 0 };
}

function pintarBola(b) {
  const [x, y] = naQuadra(b.u, b.v);
  // Meio pixel à frente: na mesma casa do menino, a bola fica no pé dele,
  // não atrás da perna.
  b.y = y + 0.5;
  b.raiz.setAttribute("transform", `translate(${x.toFixed(1)} ${y.toFixed(1)})`);
  b.corpo.setAttribute("transform", `translate(0 ${(-3.2 - b.h).toFixed(1)}) rotate(${b.giro.toFixed(0)})`);
}

const distancia = (a, b) => Math.hypot(a.u - b.u, a.v - b.v);

function criarPelada(pai) {
  const grupo = no("g", { class: "cidade-viva__pelada" }, pai);
  const a1 = criarMenino(grupo, TIMES.atacante1, SAIDA.a1);
  const a2 = criarMenino(grupo, TIMES.atacante2, SAIDA.a2);
  const z = criarMenino(grupo, TIMES.zagueiro, SAIDA.z);
  const g = criarMenino(grupo, TIMES.goleiro, SAIDA.g);
  const bola = criarBola(grupo);
  const grito = criarGrito(pai, "cidade-viva__grito--gol");
  const atacantes = [a1, a2];
  const todos = [a1, a2, z, g];

  let agora = 0;
  const jogo = {
    fase: "reinicio", ate: 1.2, dono: null, voo: null,
    quemSai: a1, buscando: null, mergulho: null, chutador: null,
  };

  const pontoDeAtaque = () => [sorteio(0.3, 0.8), sorteio(CAMPO.v0 + 0.05, CAMPO.v1 - 0.05)];
  const companheiro = (m) => (m === a1 ? a2 : a1);

  function chuteNaPose(m) {
    m.pose = "chute";
    m.poseAte = agora + 0.28;
  }

  /** A bola sai voando de onde está até `para`; ao chegar, `depois`. */
  function lancar(para, dur, altura, depois) {
    jogo.voo = { de: [bola.u, bola.v], para, t: 0, dur, altura, depois };
    jogo.dono = null;
  }

  function conduzir(m) {
    Object.assign(jogo, { fase: "conducao", dono: m, ate: agora + sorteio(0.9, 1.8), buscando: null });
    m.alvo = pontoDeAtaque();
    m.velocidade = VELOCIDADE.conduzindo;
  }

  function passar(de, para) {
    chuteNaPose(de);
    const destino = [
      limitar(para.u + sorteio(-0.05, 0.08), CAMPO.u0, CAMPO.u1),
      limitar(para.v + sorteio(-0.06, 0.06), CAMPO.v0, CAMPO.v1),
    ];
    para.alvo = destino;
    para.velocidade = VELOCIDADE.correndo;
    const dist = Math.hypot(destino[0] - bola.u, destino[1] - bola.v);
    jogo.fase = "passe";
    lancar(destino, 0.25 + dist / 1.1, 3 + dist * 6, () => conduzir(para));
  }

  function chutar(m) {
    chuteNaPose(m);
    const r = Math.random();
    const resultado = r < 0.55 ? "gol" : r < 0.88 ? "defesa" : "fora";
    let v;
    if (resultado === "gol") {
      // No canto longe do goleiro.
      v = g.v > MEIO_DO_GOL ? sorteio(GOL.v0 + 0.02, MEIO_DO_GOL - 0.06) : sorteio(MEIO_DO_GOL + 0.06, GOL.v1 - 0.02);
    } else if (resultado === "defesa") {
      v = limitar(g.v + sorteio(-0.12, 0.12), GOL.v0 + 0.03, GOL.v1 - 0.03);
    } else {
      v = Math.random() < 0.5 ? GOL.v0 - sorteio(0.05, 0.1) : GOL.v1 + sorteio(0.05, 0.1);
    }
    const dist = Math.hypot(GOL.u - bola.u, v - bola.v);
    const dur = 0.2 + dist / 1.7;
    // O goleiro pula na hora quando defende, e atrasado quando toma.
    g.alvo = [0.95, resultado === "gol" ? limitar(v + (v > g.v ? -0.12 : 0.12), GOL.v0, GOL.v1) : v];
    g.velocidade = resultado === "defesa" ? 1.2 : 0.5;
    Object.assign(jogo, { fase: "chute", chutador: m });
    jogo.mergulho = { lado: v > g.v ? 1 : -1, de: agora + dur * 0.3, ate: agora + dur + 0.45 };
    lancar([GOL.u - 0.02, v], dur, 6 + dist * 8, () => depoisDoChute(resultado));
  }

  function depoisDoChute(resultado) {
    if (resultado === "gol") {
      Object.assign(jogo, { fase: "gol", ate: agora + 2.6 });
      const [x, y] = naQuadra(GOL.u, MEIO_DO_GOL);
      gritar(grito, "GOL!", x - 6, y - 58, 2.2);
      jogo.chutador.pose = "comemora";
      jogo.chutador.poseAte = agora + 2.4;
      return;
    }
    // Defesa ou para fora: a bola volta para o campo e alguém vai buscar.
    jogo.fase = "rebote";
    const volta = [sorteio(0.52, 0.72), sorteio(CAMPO.v0 + 0.05, CAMPO.v1 - 0.05)];
    lancar(volta, 0.7, resultado === "defesa" ? 9 : 4, bolaSolta);
  }

  function bolaSolta() {
    const perto = atacantes.reduce((a, b) => (distancia(a, bola) < distancia(b, bola) ? a : b));
    Object.assign(jogo, { fase: "solta", buscando: perto });
    perto.velocidade = VELOCIDADE.correndo;
  }

  function reiniciar() {
    const sai = jogo.quemSai;
    jogo.quemSai = companheiro(sai);
    Object.assign(jogo, { fase: "reinicio", ate: agora + 1.6 });
    sai.alvo = [...SAIDA.a1];
    companheiro(sai).alvo = [...SAIDA.a2];
    z.alvo = [...SAIDA.z];
    for (const m of todos) m.velocidade = VELOCIDADE.correndo;
    // O goleiro busca no fundo da rede e devolve para o meio.
    lancar([...CENTRO], 1.1, 16, () => {});
  }

  function atualizar(dt) {
    agora += dt;

    // Quem não tem papel no lance se posiciona em volta da bola.
    if (jogo.fase !== "reinicio") {
      z.alvo = [
        limitar(bola.u + (GOL.u - bola.u) * 0.4, 0.3, 0.85),
        limitar(bola.v + (MEIO_DO_GOL - bola.v) * 0.4, CAMPO.v0, CAMPO.v1),
      ];
      z.velocidade = VELOCIDADE.zagueiro;
    }
    if (jogo.fase !== "chute") {
      g.alvo = [0.95, limitar(bola.v, GOL.v0 + 0.05, GOL.v1 - 0.05)];
      g.velocidade = VELOCIDADE.goleiro;
    }

    switch (jogo.fase) {
      case "conducao": {
        const dono = jogo.dono;
        if (!dono.andando) dono.alvo = pontoDeAtaque();
        const outro = companheiro(dono);
        if (!outro.andando && Math.random() < dt * 0.8) {
          outro.alvo = pontoDeAtaque();
          outro.velocidade = VELOCIDADE.correndo;
        }
        // A bola vai no pé, um pouco à frente, quicando de leve.
        bola.u = dono.u + 0.03 * dono.virado * 0.7;
        bola.v = dono.v + 0.015;
        bola.h = Math.abs(Math.sin(agora * 11)) * 1.6;
        bola.giro += dt * 360 * dono.virado;
        if (agora > jogo.ate) {
          if (distancia(z, dono) < 0.16 && Math.random() < 0.3) {
            // Desarme: o zagueiro dá um chutão para trás.
            chuteNaPose(z);
            jogo.fase = "rebote";
            lancar([sorteio(0.15, 0.35), sorteio(CAMPO.v0, CAMPO.v1)], 0.9, 16, bolaSolta);
          } else if (dono.u > 0.58 && Math.random() < 0.55) {
            chutar(dono);
          } else {
            passar(dono, outro);
          }
        }
        break;
      }
      case "solta": {
        const m = jogo.buscando;
        m.alvo = [bola.u, bola.v];
        if (distancia(m, bola) < 0.035) conduzir(m);
        break;
      }
      case "gol": {
        const c = jogo.chutador;
        c.pulo = Math.abs(Math.sin(agora * 10)) * 7;
        const outro = companheiro(c);
        outro.alvo = [limitar(c.u - 0.06, CAMPO.u0, CAMPO.u1), limitar(c.v + 0.05, CAMPO.v0, CAMPO.v1)];
        if (agora > jogo.ate) {
          c.pulo = 0;
          reiniciar();
        }
        break;
      }
      case "reinicio":
        if (agora > jogo.ate && !jogo.voo) conduzir(jogo.quemSai === a1 ? a2 : a1);
        break;
      default:
        break;
    }

    const voo = jogo.voo;
    if (voo) {
      voo.t += dt;
      const p = Math.min(1, voo.t / voo.dur);
      bola.u = voo.de[0] + (voo.para[0] - voo.de[0]) * p;
      bola.v = voo.de[1] + (voo.para[1] - voo.de[1]) * p;
      bola.h = 4 * voo.altura * p * (1 - p);
      bola.giro += dt * 720;
      if (p >= 1) {
        jogo.voo = null;
        bola.h = 0;
        voo.depois();
      }
    }

    // O mergulho do goleiro: cai de lado na direção da bola e levanta.
    const mg = jogo.mergulho;
    const caindo = mg && agora > mg.de && agora < mg.ate;
    const alvoGiro = caindo ? mg.lado * 62 : 0;
    g.giro += (alvoGiro - g.giro) * Math.min(1, dt * 14);
    g.pulo = caindo ? 3 : 0;
    if (mg && agora >= mg.ate) jogo.mergulho = null;

    for (const m of todos) {
      moverMenino(m, dt);
      // Parado, olha para a bola.
      if (!m.andando) {
        const dx = (bola.u - m.u) * QUADRA.u[0] + (bola.v - m.v) * QUADRA.v[0];
        if (Math.abs(dx) > 2) m.virado = dx > 0 ? 1 : -1;
      }
    }
    animarGrito(grito, dt);
    pintar();
  }

  function pintar() {
    for (const m of todos) pintarMenino(m, agora);
    pintarBola(bola);
    ordenarPorAltura(grupo, [...todos, bola]);
  }

  return { atualizar, pintar };
}

// ==========================================================================
// o muro
// ==========================================================================

/* Na calçada do muro "AQUI TAMBÉM SE CONSTRÓI O FUTURO", onde a pintura
   tinha um rapaz parado. Posições dos pés. O policial fica à direita,
   virado para a esquerda. */
const NOIA_EM = [1210, 699];
const POLICIAL_EM = [1238, 686];

/* O roteiro da surra, em segundos. `braco` é o ângulo do braço do
   cassetete (0 = pendurado; 140 = erguido para trás da cabeça; 305 = a
   pancada, na frente). O ângulo sempre cresce durante a pancada: o braço
   passa POR CIMA da cabeça, e não por baixo. */
const ROTEIRO = [
  { dur: 1.1, braco: [0, 0] },
  { dur: 0.35, braco: [0, 140] },
  { dur: 0.12, braco: [140, 305], pancada: "PÁ!" },
  { dur: 0.32, braco: [305, 305] },
  { dur: 0.3, braco: [305, 140] },
  { dur: 0.12, braco: [140, 305], pancada: "PÁ!" },
  { dur: 0.32, braco: [305, 305] },
  { dur: 0.3, braco: [305, 140] },
  { dur: 0.12, braco: [140, 305], pancada: "POW!", derruba: true },
  { dur: 0.45, braco: [305, 360] },
  { dur: 2.0, braco: [360, 360] },
  { dur: 0.55, braco: [360, 360], levanta: true },
];

/* A surra precisa ser VISTA: um carro passando na frente do muro bem na
   hora da paulada tapava a cena inteira. Então o policial só começa com o
   trecho da rua em frente ao muro livre pelos próximos segundos, e enquanto
   bate nenhum carro novo entra naquela rua. `x` é o trecho em que um carro
   daquela faixa cobre a cena (o carro ocupa uns 80 px para trás da âncora
   e 45 para a frente); `segundos` é a surra toda, da primeira erguida do
   cassetete até o noia ir ao chão, com folga. */
const PALCO = { faixa: "taxi", x: [1120, 1340], segundos: 2.8 };

/** `palco` diz se a rua está livre e avisa o trânsito que a surra começou. */
function criarMuro(pai, palco) {
  const grupo = no("g", { class: "cidade-viva__muro" }, pai);

  const noia = no("g", { transform: `translate(${NOIA_EM[0]} ${NOIA_EM[1]})` }, grupo);
  sombra(noia, 9, 2.8);
  const noiaCorpo = no("g", {}, noia);
  noiaCorpo.appendChild(desenho(NOIA, TRAPO, PX_ADULTO));
  const tontura = no("g", { visibility: "hidden" }, noia);
  const estrelas = [0, 1, 2].map(() => {
    const e = no("g", {}, tontura);
    e.appendChild(desenho(ESTRELA, COR_ESTRELA, 1.3));
    return e;
  });

  const policial = no("g", { transform: `translate(${POLICIAL_EM[0]} ${POLICIAL_EM[1]})` }, grupo);
  sombra(policial, 10, 3);
  // O desenho olha para a direita; espelhado, olha para o noia.
  const policialCorpo = no("g", { transform: "scale(-1 1)" }, policial);
  policialCorpo.appendChild(desenho(POLICIAL, FARDA, PX_ADULTO));
  const ombroX = (OMBRO[0] - POLICIAL[0].length / 2) * PX_ADULTO;
  const ombroY = (OMBRO[1] - POLICIAL.length) * PX_ADULTO;
  const braco = no("g", {}, policialCorpo);
  const bracoDesenho = grupoDoMapa(BRACO, FARDA);
  bracoDesenho.setAttribute("transform", `scale(${PX_ADULTO}) translate(-1.5 0)`);
  braco.appendChild(bracoDesenho);

  const grito = criarGrito(pai, "cidade-viva__grito--pancada");

  let agora = 0;
  let passo = 0;
  let inicioDoPasso = 0;
  const estado = { caido: false, apanhou: -9, levantando: -9, angulo: 0 };

  function atualizar(dt) {
    agora += dt;
    let atual = ROTEIRO[passo];
    while (agora - inicioDoPasso >= atual.dur) {
      if (passo === 0) {
        if (!palco.podeComecar()) {
          // Carro vindo: o policial espera ele passar.
          inicioDoPasso = agora - atual.dur;
          break;
        }
        palco.comecou();
      }
      inicioDoPasso += atual.dur;
      if (atual.pancada) {
        gritar(grito, atual.pancada, NOIA_EM[0] - 2, NOIA_EM[1] - 50, 0.6);
        estado.apanhou = inicioDoPasso;
        if (atual.derruba) estado.caido = true;
      }
      passo = (passo + 1) % ROTEIRO.length;
      atual = ROTEIRO[passo];
      if (atual.levanta) estado.levantando = inicioDoPasso;
      if (passo === 0) estado.caido = false;
    }
    const p = Math.min(1, (agora - inicioDoPasso) / atual.dur);
    const [a0, a1] = atual.braco;
    braco.setAttribute("transform", `translate(${ombroX} ${ombroY}) rotate(${(a0 + (a1 - a0) * p).toFixed(1)})`);

    // O noia: se encolhe a cada pancada, cai na última, levanta no fim.
    let angulo;
    if (atual.levanta) {
      angulo = -90 * (1 - p);
    } else if (estado.caido) {
      angulo = Math.max(-90, -90 * ((agora - estado.apanhou) / 0.18));
    } else {
      const desde = agora - estado.apanhou;
      angulo = desde < 0.35 ? -16 * (1 - desde / 0.35) : Math.sin(agora * 2.2) * 2;
    }
    const recuo = angulo < -2 ? Math.min(4, -angulo / 20) : 0;
    noiaCorpo.setAttribute("transform", `translate(${(-recuo).toFixed(1)} 0) rotate(${angulo.toFixed(1)})`);

    const tonto = estado.caido && !atual.levanta && agora - estado.apanhou > 0.2;
    tontura.setAttribute("visibility", tonto ? "visible" : "hidden");
    if (tonto) {
      estrelas.forEach((e, k) => {
        const a = agora * 4 + k * 2.1;
        e.setAttribute("transform", `translate(${(-40 + Math.cos(a) * 9).toFixed(1)} ${(-14 + Math.sin(a) * 3).toFixed(1)})`);
      });
    }
    animarGrito(grito, dt);
  }

  return { atualizar, pintar: () => atualizar(0) };
}

// ==========================================================================
// o trânsito
// ==========================================================================

/* Uma faixa por rua, cada uma num sentido, os dois descendo para a esquina
   da frente. A faixa passa onde a pintura tinha o carro (`pintado`),
   `desvio` pixels mais para o meio da rua — o carro pintado estava
   estacionado colado no meio-fio. A inclinação da rua vem do manifesto,
   medida junto com o recorte.

   `de` e `ate` são onde o carro surge e some (x na pintura). A da esquerda
   começa depois das motos paradas no começo da rua; a da direita, depois
   da moto parada perto do quiosque. A `frota` diz que carros passam em
   cada uma, e se vão espelhados: o vermelho foi pintado descendo para a
   direita e o táxi descendo para a esquerda — espelhado, um vira o outro. */
const FAIXAS = [
  {
    pintado: "carro-vermelho",
    desvio: -8,
    de: 150,
    ate: 665,
    frota: [["carro-vermelho", false], ["carro-azul", false], ["carro-verde", false], ["carro-roxo", false], ["taxi", true]],
  },
  {
    pintado: "taxi",
    desvio: -8,
    de: 1340,
    ate: 890,
    frota: [["taxi", false], ["carro-vermelho", true], ["carro-azul", true], ["carro-verde", true], ["carro-roxo", true]],
  },
];

/** Em pixels da pintura, medidos na horizontal. */
const VELOCIDADE_DO_CARRO = [40, 58];
const DISTANCIA_ENTRE_CARROS = 150;
const ESPERA_ENTRE_CARROS = [2.5, 8];
/** Quantos pixels o carro leva para aparecer e sumir nas pontas da faixa. */
const ESMAECER = 45;

function criarTransito(pai) {
  const grupo = no("g", { class: "cidade-viva__transito" }, pai);
  const carros = [];
  let relogio = 0;

  const faixas = FAIXAS.map((f) => {
    const ref = figurantes.carros[f.pintado];
    return {
      ...f,
      inclinacao: ref.rua,
      x0: ref.pintado_em[0],
      y0: ref.pintado_em[1] + f.desvio,
      sentido: Math.sign(f.ate - f.de),
      espera: sorteio(1, 3),
      ultimo: null,
      seguraAte: 0,
    };
  });
  const faixaDo = (pintado) => faixas.find((f) => f.pintado === pintado);

  const yNa = (faixa, x) => faixa.y0 + faixa.inclinacao * (x - faixa.x0);

  function novoCarro(faixa, x, [nome, espelhado] = escolher(faixa.frota.filter(([n]) => n !== faixa.ultimo))) {
    faixa.ultimo = nome;
    const dados = figurantes.carros[nome];
    const raiz = no("g", {}, grupo);
    no("image", { href: dados.sprite, width: dados.largura, height: dados.altura }, raiz);
    const carro = { raiz, dados, espelhado, faixa, x, y: 0, velocidade: sorteio(...VELOCIDADE_DO_CARRO) };
    carros.push(carro);
    pintarCarro(carro);
    return carro;
  }

  function pintarCarro(c) {
    const f = c.faixa;
    c.y = yNa(f, c.x);
    const [ax, ay] = c.dados.ancora;
    c.raiz.setAttribute(
      "transform",
      `translate(${c.x.toFixed(1)} ${c.y.toFixed(1)}) scale(${c.espelhado ? -1 : 1} 1) translate(${-ax} ${-ay})`,
    );
    const borda = Math.min(Math.abs(c.x - f.de), Math.abs(f.ate - c.x));
    c.raiz.setAttribute("opacity", Math.min(1, borda / ESMAECER).toFixed(2));
  }

  // Os dois carros da pintura começam onde estavam: a cidade abre igual à
  // arte, e só então o trânsito anda.
  for (const f of faixas) novoCarro(f, f.x0, [f.pintado, false]);

  /** Nenhum carro da faixa passa entre `xMin` e `xMax` nos próximos
      `segundos`? Conta com a velocidade de cada um; se ele frear atrás de
      outro, chega ainda mais tarde, então a resposta continua valendo. */
  function livre(pintado, [xMin, xMax], segundos) {
    const f = faixaDo(pintado);
    return !carros.some((c) => {
      if (c.faixa !== f) return false;
      const depois = c.x + c.velocidade * f.sentido * segundos;
      return Math.max(c.x, depois) >= xMin && Math.min(c.x, depois) <= xMax;
    });
  }

  /** Nenhum carro novo entra na faixa pelos próximos `segundos`. */
  function segurar(pintado, segundos) {
    faixaDo(pintado).seguraAte = relogio + segundos;
  }

  function atualizar(dt) {
    relogio += dt;
    for (const f of faixas) {
      const daFaixa = carros.filter((c) => c.faixa === f).sort((a, b) => (b.x - a.x) * f.sentido);
      let frente = null;
      for (const c of daFaixa) {
        let v = c.velocidade;
        // Ninguém ultrapassa: chegou perto do da frente, anda no passo dele.
        if (frente && Math.abs(frente.x - c.x) < DISTANCIA_ENTRE_CARROS) v = Math.min(v, frente.velocidade * 0.8);
        c.x += v * f.sentido * dt;
        frente = c;
      }
      for (const c of daFaixa) {
        if ((c.x - f.ate) * f.sentido >= 0) {
          c.raiz.remove();
          carros.splice(carros.indexOf(c), 1);
        }
      }
      f.espera -= dt;
      const ultimo = daFaixa[daFaixa.length - 1];
      const temEspaco = !ultimo || Math.abs(ultimo.x - f.de) > DISTANCIA_ENTRE_CARROS + 20;
      if (f.espera <= 0 && temEspaco && relogio >= f.seguraAte) {
        novoCarro(f, f.de);
        f.espera = sorteio(...ESPERA_ENTRE_CARROS);
      }
    }
    for (const c of carros) pintarCarro(c);
    ordenarPorAltura(grupo, carros);
  }

  return { atualizar, livre, segurar };
}

// ==========================================================================

/**
 * Enche `camada` — um grupo SVG já posicionado e escalado para que uma
 * unidade seja um pixel da CIDADE.png — com o que se mexe na cidade.
 */
export function animarCidade(camada) {
  const atores = no("g", { class: "cidade-viva" }, camada);

  const pelada = criarPelada(atores);
  // O muro nasce antes do trânsito para os carros serem desenhados na frente
  // da cena; por isso o palco consulta o trânsito só quando já existe.
  let transito = null;
  const muro = criarMuro(atores, {
    podeComecar: () => transito.livre(PALCO.faixa, PALCO.x, PALCO.segundos),
    comecou: () => transito.segurar(PALCO.faixa, PALCO.segundos),
  });
  transito = criarTransito(atores);

  // Os postes da calçada da frente, por cima de tudo: o carro passa atrás.
  no("image", {
    href: figurantes.frente,
    width: figurantes.cidade.largura,
    height: figurantes.cidade.altura,
    class: "cidade-viva__frente",
  }, camada);

  pelada.pintar();
  muro.pintar();

  let antes = null;
  function quadro(agora) {
    // Aba escondida pausa o requestAnimationFrame; na volta, o salto de
    // tempo é cortado para ninguém atravessar a cidade num quadro.
    const dt = antes === null ? 0 : Math.min(0.05, (agora - antes) / 1000);
    antes = agora;
    pelada.atualizar(dt);
    muro.atualizar(dt);
    transito.atualizar(dt);
    requestAnimationFrame(quadro);
  }
  requestAnimationFrame(quadro);
}

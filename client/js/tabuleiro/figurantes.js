/* Os figurantes da cidade: os meninos da pelada, o policial e o noia.

   Desenhados em texto, como os ícones de pixel.js — cada caractere é um
   pixel e a paleta diz a cor. O mesmo menino serve aos quatro jogadores: só
   a paleta muda (pele, cabelo, camisa do time).

   Os desenhos olham para a DIREITA; quem anima espelha quando o boneco anda
   para a esquerda. O ponto de apoio de todos é o meio da base: os pés. */

const CONTORNO = "#1a1020";

// --- menino -------------------------------------------------------------

const TRONCO = [
  "...KKK...",
  "..KHHHK..",
  ".KHHHHHK.",
  ".KHSSSHK.",
  ".KSESESK.",
  ".KSSSSSK.",
  "..KKSKK..",
  ".KTTTTTK.",
  "KSTTTTTSK",
  "KSTTTTTSK",
  ".KTTTTTK.",
  ".KPPPPPK.",
];

export const MENINO = {
  parado: [...TRONCO, ".KPPKPPK.", ".KSK.KSK.", ".KSK.KSK.", ".KXK.KXK."],
  corre1: [...TRONCO, ".KPPKPPK.", "KSK...KSK", "KSK...KSK", "KXK...KXK"],
  corre2: [...TRONCO, ".KPPPPPK.", "..KSSK...", "..KSSK...", "..KXXK..."],
  chute: [...TRONCO, ".KPPKPPK.", ".KSK.KSSK", ".KSK..KXK", ".KXK....."],
  // Braços para cima: a comemoração do gol, e o goleiro se esticando.
  comemora: [
    "K...KKK...K",
    "SK.KHHHK.KS",
    "SKKHHHHHKKS",
    "KSKHSSSHKSK",
    ".KKSESESKK.",
    "..KSSSSSK..",
    "..KKKSKKK..",
    "..KTTTTTK..",
    "..KTTTTTK..",
    "..KTTTTTK..",
    "..KTTTTTK..",
    "..KPPPPPK..",
    "..KPPKPPK..",
    "..KSK.KSK..",
    "..KSK.KSK..",
    "..KXK.KXK..",
  ],
};

/** A pelada: laranja ataca, azul defende, verde no gol. */
export const TIMES = {
  atacante1: { K: CONTORNO, E: CONTORNO, H: "#1d1a1f", S: "#8d5a3b", T: "#ff7a1a", P: "#1c2340", X: "#f4f4f4" },
  atacante2: { K: CONTORNO, E: CONTORNO, H: "#6b3b1f", S: "#f1c7a0", T: "#ff7a1a", P: "#1c2340", X: "#e02b2b" },
  zagueiro: { K: CONTORNO, E: CONTORNO, H: "#1d1a1f", S: "#c68a5e", T: "#2f7bff", P: "#f4f4f4", X: "#1d1a1f" },
  goleiro: { K: CONTORNO, E: CONTORNO, H: "#e0b040", S: "#c68a5e", T: "#2fd05a", P: "#1c2340", X: "#1d1a1f" },
};

// --- o policial ---------------------------------------------------------

/* O braço direito, o do cassetete, NÃO está no corpo: é um desenho à parte
   que gira no ombro. Assim a pancada é uma rotação contínua, em vez de três
   poses trocando no susto. */
export const POLICIAL = [
  "....KKKKK....",
  "...KCCYCCK...",
  "..KCCCCCCCK..",
  "...KccccccccK",
  "....KSSSSK...",
  "....KSSESK...",
  "....KMMMSK...",
  ".....KSSK....",
  "...KKUUUUKK..",
  "..KUUUUUYUUK.",
  "..KUUUUUUUUK.",
  "..KSKUUUUUK..",
  "..KSKUUUUUK..",
  "..KSKuuuuuK..",
  "...K.BBBBBK..",
  "....KBBBBBK..",
  "....KPPPPPK..",
  "....KPPKPPK..",
  "....KPK.KPK..",
  "....KPK.KPK..",
  "....KXK.KXK..",
  "...KXXK.KXXK.",
];

/** Onde o braço gira, em pixels do desenho do corpo. */
export const OMBRO = [10.5, 9];

/** O braço pendurado, apontando para baixo a partir do ombro (0,0). O
    cassetete continua a linha do braço, depois da mão. */
export const BRACO = [
  "KUK",
  "KUK",
  "KUK",
  "KSK",
  "KSK",
  ".T.",
  ".T.",
  ".T.",
  ".T.",
  ".T.",
  ".T.",
  ".T.",
  ".T.",
];

export const FARDA = {
  K: CONTORNO,
  E: CONTORNO,
  C: "#1b2d57",
  c: "#0f1a36",
  Y: "#ffd23d",
  S: "#b77b52",
  M: "#2a1a12",
  U: "#2c4a9a",
  u: "#1f3570",
  B: "#141414",
  P: "#1b2d57",
  X: "#0c0c0c",
  T: "#262626",
};

// --- o noia -------------------------------------------------------------

export const NOIA = [
  "..K.KKK.K..",
  "..KHHHHK...",
  ".KHHHHHHK..",
  ".KHSSSSHK..",
  "..KSSESSK..",
  "..KSSSSSK..",
  "..KSsssSK..",
  "...KSSSK...",
  "..KWWWWWK..",
  ".KSKWWWKSK.",
  ".KSKWWWKSK.",
  ".KSKWwWKSK.",
  ".KSKWWWKSK.",
  "..KKPPPKK..",
  "...KPPPK...",
  "...KPKPK...",
  "...KSKSK...",
  "...KSKSK...",
  "...KSKSK...",
  "..KFFKFFK..",
  "..KKKKKKK..",
];

export const TRAPO = {
  K: CONTORNO,
  E: CONTORNO,
  H: "#2b211c",
  S: "#9c6541",
  s: "#6e4630",
  W: "#d8d2c0",
  w: "#9b8f72",
  P: "#6f6f78",
  F: "#2f7bff",
};

// --- efeitos ------------------------------------------------------------

/** Estrelinha de quem apanhou e ficou tonto. */
export const ESTRELA = ["..Y..", ".YYY.", "YYYYY", ".YYY.", "..Y.."];
export const COR_ESTRELA = { Y: "#ffd23d" };

#!/usr/bin/env bash
# Atualiza o Roubodopolis na hospedagem. Rode DENTRO da VPS, por SSH:
#
#     cd /home/gtel/Roubodopolis && bash ferramentas/publicar.sh
#
# Não faz deploy a partir da sua máquina — o `git push` continua sendo seu.
# Este script é o outro lado: puxa, instala o que mudou e reinicia.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

BRANCH="${1:-vitinho}"

echo "== Roubodopolis: publicando ($BRANCH) =="

# --- 0. quem está rodando isto -------------------------------------------
# O Passenger executa o app como o DONO da pasta. Se o deploy rodar como
# root, os arquivos baixados nascem de root e o app perde acesso a eles —
# e o erro só aparece depois, como 500 sem causa aparente.
#
# É por isso que NÃO usamos o `git config --global --add safe.directory` que
# o git sugere quando reclama de "dubious ownership": aquilo silencia o
# aviso e deixa o estrago acontecer. O aviso está certo; o usuário é que
# está errado.
DONO="$(stat -c '%U' "$RAIZ")"
EU="$(id -un)"

if [ "$EU" != "$DONO" ]; then
  echo "ERRO: rodando como '$EU', mas $RAIZ pertence a '$DONO'."
  echo
  echo "Rode assim:"
  echo "    su - $DONO -c 'cd $RAIZ && bash ferramentas/publicar.sh $BRANCH'"
  echo
  echo "Se a conta estiver com shell bloqueado:"
  echo "    su -s /bin/bash - $DONO -c 'cd $RAIZ && bash ferramentas/publicar.sh $BRANCH'"
  exit 1
fi

# Restos de uma execução anterior feita como root.
INTRUSO="$(find "$RAIZ" -not -user "$DONO" -print -quit 2>/dev/null || true)"
if [ -n "$INTRUSO" ]; then
  echo "ERRO: há arquivo que não pertence a '$DONO' (ex.: $INTRUSO)."
  echo "Provavelmente sobrou de um deploy feito como root. Como root, rode:"
  echo "    chown -R $DONO:$DONO $RAIZ"
  exit 1
fi

# --- 1. o .env precisa existir antes de qualquer coisa --------------------
if [ ! -f .env ]; then
  echo "ERRO: não existe .env em $RAIZ"
  echo "Ele não vem pelo git (está no .gitignore). Veja o passo 3 do DEPLOY.md."
  exit 1
fi

# --- 2. código -----------------------------------------------------------
echo "-- git pull"
git pull origin "$BRANCH"

# --- 3. dependências, só se requirements.txt mudou -----------------------
# HEAD@{1} é o commit anterior ao pull. Na primeira execução ele não existe,
# e aí instalamos de qualquer jeito.
if ! git diff --quiet 'HEAD@{1}' HEAD -- requirements.txt 2>/dev/null; then
  echo "-- requirements.txt mudou: instalando"
  pip install -r requirements.txt
else
  echo "-- requirements.txt sem mudança: pulando pip"
fi

# --- 4. banco ------------------------------------------------------------
# create_all só cria o que falta; repetir é seguro e não apaga dado.
echo "-- conferindo o banco"
python -m server.db.criar_banco

# --- 5. reinício ---------------------------------------------------------
# O Passenger recarrega o código quando este arquivo muda de data.
mkdir -p tmp
touch tmp/restart.txt

echo
echo "Pronto. https://roubopolis.gteltestes.com"

#!/usr/bin/env sh
set -eu

REPOSITORY_URL=${DNS_SWITCHER_REPOSITORY_URL:-https://github.com/AngoloInformatico/DNS-SwitcherPro.git}
ARCHIVE_URL=${DNS_SWITCHER_ARCHIVE_URL:-https://github.com/AngoloInformatico/DNS-SwitcherPro/archive/refs/heads/main.tar.gz}
BRANCH=${DNS_SWITCHER_BRANCH:-main}
INSTALL_DIR=${DNS_SWITCHER_SOURCE_DIR:-/DATA/AppData/dns-switcher-pro-source}

if ! command -v docker >/dev/null 2>&1; then
  echo "Errore: Docker non è disponibile su ZimaOS." >&2
  exit 1
fi

mkdir -p "$(dirname "$INSTALL_DIR")"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Aggiornamento del progetto da GitHub..."
  git -C "$INSTALL_DIR" pull --ff-only
elif [ -e "$INSTALL_DIR" ]; then
  echo "Errore: $INSTALL_DIR esiste già ma non è un repository Git." >&2
  echo "Rinominarla o rimuoverla, quindi ripetere l'installazione." >&2
  exit 1
elif command -v git >/dev/null 2>&1; then
  echo "Download del progetto da GitHub..."
  git clone --depth 1 --branch "$BRANCH" "$REPOSITORY_URL" "$INSTALL_DIR"
else
  echo "Git non disponibile: download dell'archivio GitHub..."
  TEMP_DIR=$(mktemp -d)
  ARCHIVE_FILE="$TEMP_DIR/project.tar.gz"
  if command -v curl >/dev/null 2>&1; then
    curl -fL "$ARCHIVE_URL" -o "$ARCHIVE_FILE"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$ARCHIVE_FILE" "$ARCHIVE_URL"
  else
    echo "Errore: sono necessari git, curl oppure wget." >&2
    exit 1
  fi
  mkdir -p "$INSTALL_DIR"
  tar -xzf "$ARCHIVE_FILE" -C "$INSTALL_DIR" --strip-components=1
fi

if [ ! -f "$INSTALL_DIR/Docker/install-zimaos.sh" ]; then
  echo "Errore: install-zimaos.sh non trovato nel repository scaricato." >&2
  exit 1
fi

chmod +x "$INSTALL_DIR/Docker/install-zimaos.sh"
exec "$INSTALL_DIR/Docker/install-zimaos.sh"

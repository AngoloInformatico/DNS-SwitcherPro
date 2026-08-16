#!/usr/bin/env sh
set -eu

CONTAINER_NAME=dns-switcher-pro
DEFAULT_IMAGE=dns-switcher-pro:1.1.4-zimaos
INSTALL_DIR=${DNS_SWITCHER_SOURCE_DIR:-/DATA/AppData/dns-switcher-pro-source}
DATA_DIR=${DNS_SWITCHER_DATA_PATH:-}
PURGE=0

if [ "${1:-}" = "--purge" ]; then
  PURGE=1
elif [ "$#" -gt 0 ]; then
  echo "Uso: sh uninstall-zimaos.sh [--purge]" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Errore: Docker non è disponibile su questo sistema." >&2
  exit 1
fi

USE_SUDO=0
if ! docker info >/dev/null 2>&1; then
  if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && sudo docker info >/dev/null 2>&1; then
    USE_SUDO=1
  else
    echo "Errore: impossibile accedere al daemon Docker." >&2
    exit 1
  fi
fi

run_docker() {
  if [ "$USE_SUDO" -eq 1 ]; then
    sudo docker "$@"
  else
    docker "$@"
  fi
}

# Recupera l'eventuale percorso dati personalizzato prima di rimuovere i file.
ENV_FILE="$INSTALL_DIR/Docker/.env"
if [ -z "$DATA_DIR" ] && [ -f "$ENV_FILE" ]; then
  DATA_DIR=$(sed -n 's/^DNS_SWITCHER_DATA_PATH=//p' "$ENV_FILE" | tail -n 1)
fi
DATA_DIR=${DATA_DIR:-/DATA/AppData/dns-switcher-pro}

IMAGE_REF=$DEFAULT_IMAGE
if run_docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
  IMAGE_REF=$(run_docker inspect --format '{{.Config.Image}}' "$CONTAINER_NAME")
  echo "Rimozione del container $CONTAINER_NAME..."
  run_docker rm -f "$CONTAINER_NAME" >/dev/null
else
  echo "Container $CONTAINER_NAME non presente."
fi

if run_docker image inspect "$IMAGE_REF" >/dev/null 2>&1; then
  echo "Rimozione dell'immagine $IMAGE_REF..."
  run_docker image rm "$IMAGE_REF" >/dev/null
else
  echo "Immagine $IMAGE_REF non presente."
fi

# Compose crea normalmente questa rete; se è ancora usata, Docker la conserva.
run_docker network rm dns-switcher-pro_default >/dev/null 2>&1 || true

safe_remove_dir() {
  target=$1
  case "$target" in
    ""|/|/DATA|/DATA/AppData)
      echo "Percorso non sicuro, rimozione annullata: $target" >&2
      exit 1
      ;;
    /*) ;;
    *)
      echo "Il percorso da eliminare deve essere assoluto: $target" >&2
      exit 1
      ;;
  esac
  if [ -e "$target" ]; then
    if [ "$(id -u)" -eq 0 ]; then
      rm -rf -- "$target"
    elif command -v sudo >/dev/null 2>&1; then
      sudo rm -rf -- "$target"
    else
      echo "Privilegi insufficienti per eliminare $target" >&2
      exit 1
    fi
  fi
}

if [ "$PURGE" -eq 1 ]; then
  echo "Eliminazione completa di dati e sorgenti..."
  safe_remove_dir "$DATA_DIR"
  safe_remove_dir "$INSTALL_DIR"
  echo "DNS Switcher Pro, configurazione, password, log e sorgenti sono stati eliminati."
else
  echo
  echo "DNS Switcher Pro è stato disinstallato."
  echo "Dati conservati in: $DATA_DIR"
  echo "Sorgenti conservati in: $INSTALL_DIR"
  echo "Per eliminare anche dati e sorgenti, ripetere il comando con --purge."
fi

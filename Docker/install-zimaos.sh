#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
ENV_FILE="$SCRIPT_DIR/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "Errore: Docker non è disponibile su questo sistema." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  if ! command -v openssl >/dev/null 2>&1; then
    echo "Errore: openssl è necessario per generare il token iniziale." >&2
    exit 1
  fi
  TOKEN=$(openssl rand -hex 32)
  sed "s/CAMBIA-QUESTO-TOKEN-CON-ALMENO-32-CARATTERI/$TOKEN/" \
    "$SCRIPT_DIR/.env.example" > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Creato $ENV_FILE con un token casuale."
fi

cd "$PROJECT_DIR"
docker compose --env-file "$ENV_FILE" -f "$SCRIPT_DIR/docker-compose.yml" up -d --build

PORT=$(sed -n 's/^DNS_SWITCHER_PORT=//p' "$ENV_FILE" | tail -n 1)
TOKEN=$(sed -n 's/^DNS_SWITCHER_SESSION_TOKEN=//p' "$ENV_FILE" | tail -n 1)
PORT=${PORT:-8765}

echo
echo "DNS Switcher Pro è stato avviato."
echo "Aprire: http://IP-DELLO-ZIMAOS:${PORT}/?token=${TOKEN}"

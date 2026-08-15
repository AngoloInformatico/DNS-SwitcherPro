#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENV_FILE="$SCRIPT_DIR/.env"

if ! command -v docker >/dev/null 2>&1; then
  echo "Errore: Docker non è disponibile su questo sistema." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  if [ -r /proc/sys/kernel/random/uuid ]; then
    TOKEN="$(tr -d '-' < /proc/sys/kernel/random/uuid)$(tr -d '-' < /proc/sys/kernel/random/uuid)"
  elif [ -r /dev/urandom ] && command -v od >/dev/null 2>&1; then
    TOKEN=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
  elif command -v openssl >/dev/null 2>&1; then
    TOKEN=$(openssl rand -hex 32)
  else
    echo "Errore: impossibile generare in modo sicuro il token iniziale." >&2
    exit 1
  fi
  sed "s/CAMBIA-QUESTO-TOKEN-CON-ALMENO-32-CARATTERI/$TOKEN/" \
    "$SCRIPT_DIR/.env.example" > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Creato $ENV_FILE con un token casuale."
fi

cd "$SCRIPT_DIR"

# ZimaOS può fornire Docker Compose come plugin moderno (`docker compose`) o
# come comando standalone (`docker-compose`). Entrando in questa cartella
# Compose carica automaticamente il file .env, anche nelle versioni che non
# supportano l'opzione globale --env-file.
if docker compose version >/dev/null 2>&1; then
  docker compose -f docker-compose.yml up -d --build
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_FILE=docker-compose.yml
  if ! docker-compose -f "$COMPOSE_FILE" config >/dev/null 2>&1; then
    # Le release Compose v1 meno recenti non riconoscono il campo top-level
    # `name`; x-casaos e il resto del manifest rimangono invariati.
    COMPOSE_FILE=.docker-compose.compat.yml
    sed '/^name:[[:space:]]/d' docker-compose.yml > "$COMPOSE_FILE"
  fi
  docker-compose -f "$COMPOSE_FILE" up -d --build
else
  echo "Errore: Docker Compose non è disponibile (né 'docker compose' né 'docker-compose')." >&2
  exit 1
fi

PORT=$(sed -n 's/^DNS_SWITCHER_PORT=//p' "$ENV_FILE" | tail -n 1)
TOKEN=$(sed -n 's/^DNS_SWITCHER_SESSION_TOKEN=//p' "$ENV_FILE" | tail -n 1)
PORT=${PORT:-8765}

echo
echo "DNS Switcher Pro è stato avviato."
echo "Aprire: http://IP-DELLO-ZIMAOS:${PORT}/?token=${TOKEN}"

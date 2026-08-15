#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname "$SCRIPT_DIR")
ENV_FILE="$SCRIPT_DIR/.env"
IMAGE_NAME=dns-switcher-pro:1.1.3-zimaos
CONTAINER_NAME=dns-switcher-pro

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

# Su ZimaOS l'utente SSH può vedere il comando Docker senza avere accesso al
# socket del daemon. In quel caso eleviamo soltanto la fase di installazione.
if DOCKER_INFO_OUTPUT=$(docker info 2>&1); then
  :
else
  case "$DOCKER_INFO_OUTPUT" in
    *"permission denied"*)
      if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
        echo "Docker richiede privilegi amministrativi su questo ZimaOS."
        echo "Rilancio tramite sudo; inserire la password dell'utente se richiesta."
        exec sudo sh "$0"
      fi
      ;;
  esac

  echo "Errore: impossibile accedere al daemon Docker." >&2
  echo "$DOCKER_INFO_OUTPUT" >&2
  if [ "$(id -u)" -ne 0 ]; then
    echo "Eseguire prima 'sudo -i' e ripetere l'installazione." >&2
  fi
  exit 1
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
  echo "Docker Compose non è disponibile: avvio tramite Docker standard."

  # Alcune installazioni ZimaOS espongono in HOME un config.json di sistema
  # non leggibile dall'utente del terminale. Per immagini pubbliche non serve:
  # usiamo una configurazione locale vuota ed evitiamo il relativo warning.
  if [ -z "${DOCKER_CONFIG:-}" ]; then
    DOCKER_CONFIG="$SCRIPT_DIR/.docker-cli"
    export DOCKER_CONFIG
    mkdir -p "$DOCKER_CONFIG"
    chmod 700 "$DOCKER_CONFIG"
  fi

  PORT=$(sed -n 's/^DNS_SWITCHER_PORT=//p' "$ENV_FILE" | tail -n 1)
  TOKEN=$(sed -n 's/^DNS_SWITCHER_SESSION_TOKEN=//p' "$ENV_FILE" | tail -n 1)
  DATA_PATH=$(sed -n 's/^DNS_SWITCHER_DATA_PATH=//p' "$ENV_FILE" | tail -n 1)
  TIMEZONE=$(sed -n 's/^TZ=//p' "$ENV_FILE" | tail -n 1)
  PORT=${PORT:-8765}
  DATA_PATH=${DATA_PATH:-/DATA/AppData/dns-switcher-pro}
  TIMEZONE=${TIMEZONE:-Europe/Rome}

  case "$PORT" in
    ''|*[!0-9]*)
      echo "Errore: DNS_SWITCHER_PORT deve essere un numero valido." >&2
      exit 1
      ;;
  esac
  if [ -z "$TOKEN" ]; then
    echo "Errore: DNS_SWITCHER_SESSION_TOKEN non è configurato in $ENV_FILE." >&2
    exit 1
  fi
  case "$DATA_PATH" in
    /*) ;;
    *)
      echo "Errore: DNS_SWITCHER_DATA_PATH deve essere un percorso assoluto." >&2
      exit 1
      ;;
  esac

  mkdir -p "$DATA_PATH"

  echo "Client rilevato: $(docker --version 2>/dev/null || echo 'versione non disponibile')"

  if docker buildx version >/dev/null 2>&1; then
    BUILD_VARIANT=buildx
  elif docker build --help 2>&1 | \
       grep -E -e 'Usage:[[:space:]]+docker build([[:space:]]|$)' >/dev/null; then
    BUILD_VARIANT=classic
  else
    # Docker 28 può essere installato senza il plugin Buildx. L'immagine CLI
    # ufficiale include il plugin e usa il daemon ZimaOS tramite il suo socket.
    BUILD_VARIANT=helper
    BUILD_HELPER_IMAGE=docker:28-cli
  fi

  run_docker_build() {
    case "$BUILD_VARIANT" in
      buildx) (cd "$PROJECT_DIR" && docker buildx build --load "$@") ;;
      classic) (cd "$PROJECT_DIR" && docker build "$@") ;;
      helper)
        docker run --rm \
          -v /var/run/docker.sock:/var/run/docker.sock \
          -v "$PROJECT_DIR:/workspace:ro" \
          -w /workspace \
          "$BUILD_HELPER_IMAGE" \
          buildx build --load "$@"
        ;;
    esac
  }
  echo "Metodo di build: $BUILD_VARIANT"

  run_docker_build -f Docker/Dockerfile -t "$IMAGE_NAME" .

  if docker inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    echo "Sostituzione del container esistente..."
    docker rm -f "$CONTAINER_NAME" >/dev/null
  fi

  docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --init \
    --ipc host \
    --publish "${PORT}:8765" \
    --env DNS_SWITCHER_CONTAINER=1 \
    --env DNS_SWITCHER_WORK_DIR=/data \
    --env DNS_SWITCHER_ALLOWED_HOSTS='*' \
    --env "DNS_SWITCHER_SESSION_TOKEN=$TOKEN" \
    --env "TZ=$TIMEZONE" \
    --volume "${DATA_PATH}:/data" \
    --security-opt no-new-privileges:true \
    --label it.alexlignola.dnsswitcherpro.managed=true \
    "$IMAGE_NAME" >/dev/null
fi

PORT=$(sed -n 's/^DNS_SWITCHER_PORT=//p' "$ENV_FILE" | tail -n 1)
TOKEN=$(sed -n 's/^DNS_SWITCHER_SESSION_TOKEN=//p' "$ENV_FILE" | tail -n 1)
PORT=${PORT:-8765}

echo
echo "DNS Switcher Pro è stato avviato."
echo "Aprire: http://IP-DELLO-ZIMAOS:${PORT}/?token=${TOKEN}"

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
  if [ -z "${DOCKER_CONFIG:-}" ] && [ -n "${HOME:-}" ] && \
     [ -e "$HOME/.docker/config.json" ] && [ ! -r "$HOME/.docker/config.json" ]; then
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
  elif docker builder build --help >/dev/null 2>&1; then
    BUILD_VARIANT=builder
  else
    BUILD_VARIANT=classic
  fi

  run_docker_build() {
    case "$BUILD_VARIANT" in
      buildx) docker buildx build --load "$@" ;;
      builder) docker builder build "$@" ;;
      *) docker build "$@" ;;
    esac
  }
  echo "Metodo di build: $BUILD_VARIANT"

  # Le forme brevi -f e -t funzionano con i client Docker legacy. Se il client
  # ZimaOS non espone neppure -f, viene usato temporaneamente il nome Dockerfile
  # predefinito nella radice del contesto, senza lasciare file nel repository.
  if run_docker_build --help 2>&1 | \
     grep -E -e '(^|[[:space:]])-f([,[:space:]]|$)|--file' >/dev/null; then
    run_docker_build -f "$SCRIPT_DIR/Dockerfile" -t "$IMAGE_NAME" "$PROJECT_DIR"
  else
    TEMP_DOCKERFILE="$PROJECT_DIR/Dockerfile"
    if [ -e "$TEMP_DOCKERFILE" ]; then
      echo "Errore: esiste già $TEMP_DOCKERFILE; impossibile preparare il fallback di build." >&2
      exit 1
    fi

    echo "Il client non accetta -f: secondo tentativo con il Dockerfile predefinito..."
    cp "$SCRIPT_DIR/Dockerfile" "$TEMP_DOCKERFILE"
    cleanup_temp_dockerfile() {
      rm -f "$TEMP_DOCKERFILE"
    }
    trap cleanup_temp_dockerfile 0 1 2 15

    if run_docker_build -t "$IMAGE_NAME" "$PROJECT_DIR"; then
      BUILD_RESULT=0
    else
      BUILD_RESULT=$?
    fi

    cleanup_temp_dockerfile
    trap - 0 1 2 15
    if [ "$BUILD_RESULT" -ne 0 ]; then
      exit "$BUILD_RESULT"
    fi
  fi

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

#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT_DIR/.env"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT=""
WEB_PORT=""
API_BASE_URL=""
WEB_URL=""
BACKEND_PID=""
WEB_PID=""

log() {
  printf '\n==> %s\n' "$1"
}

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

require_browser_opener() {
  if command -v open >/dev/null 2>&1 ||
    command -v xdg-open >/dev/null 2>&1 ||
    command -v sensible-browser >/dev/null 2>&1; then
    return
  fi

  fail "No browser opener found. Install one or open $WEB_URL manually."
}

is_port_open() {
  local port="$1"

  python3 - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sys.exit(1)
PY
}

find_open_port() {
  local preferred_port="$1"
  local max_port="${2:-65535}"
  local port="$preferred_port"

  while [ "$port" -le "$max_port" ]; do
    if is_port_open "$port"; then
      printf '%s\n' "$port"
      return 0
    fi
    port=$((port + 1))
  done

  fail "No open port found at or above $preferred_port"
}

cleanup() {
  trap - INT TERM EXIT
  if [ -n "$WEB_PID" ] && kill -0 "$WEB_PID" >/dev/null 2>&1; then
    kill "$WEB_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "$WEB_PID" ]; then
    wait "$WEB_PID" >/dev/null 2>&1 || true
  fi
  if [ -n "$BACKEND_PID" ]; then
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}

url_ready() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS "$1" >/dev/null 2>&1
    return $?
  fi

  python3 - "$1" >/dev/null 2>&1 <<'PY'
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        sys.exit(0 if response.status < 500 else 1)
except Exception:
    sys.exit(1)
PY
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local attempts="${3:-60}"

  printf 'Waiting for %s at %s' "$name" "$url"
  for _ in $(seq 1 "$attempts"); do
    if url_ready "$url"; then
      printf '\n'
      return 0
    fi
    printf '.'
    sleep 1
  done
  printf '\n'
  fail "$name did not become ready at $url"
}

open_browser() {
  local url="$1"

  if command -v open >/dev/null 2>&1; then
    open "$url"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
  elif command -v sensible-browser >/dev/null 2>&1; then
    sensible-browser "$url" >/dev/null 2>&1 &
  else
    fail "No browser opener found. Open $url manually."
  fi
}

load_env_api_key() {
  if [ -n "${OPENAI_API_KEY:-}" ] || [ ! -f "$ENV_FILE" ]; then
    return
  fi

  local line
  line="$(grep -E '^[[:space:]]*(export[[:space:]]+)?OPENAI_API_KEY=' "$ENV_FILE" | tail -n 1 || true)"
  if [ -z "$line" ]; then
    return
  fi

  local value="${line#*=}"
  value="${value%$'\r'}"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  export OPENAI_API_KEY="$value"
}

write_env_api_key() {
  local key="$1"
  local tmp_file

  tmp_file="$(mktemp)"
  if [ -f "$ENV_FILE" ]; then
    grep -v -E '^[[:space:]]*(export[[:space:]]+)?OPENAI_API_KEY=' "$ENV_FILE" >"$tmp_file" || true
  fi
  printf 'OPENAI_API_KEY=%s\n' "$key" >>"$tmp_file"
  mv "$tmp_file" "$ENV_FILE"
}

prompt_for_api_key() {
  if [ -n "${OPENAI_API_KEY:-}" ]; then
    return
  fi

  read -r -s -p 'Enter your OpenAI API key: ' OPENAI_API_KEY
  printf '\n'

  if [ -z "$OPENAI_API_KEY" ]; then
    fail "OPENAI_API_KEY cannot be empty"
  fi

  export OPENAI_API_KEY
  write_env_api_key "$OPENAI_API_KEY"
  log "Saved OPENAI_API_KEY to .env"
}

main() {
  cd "$ROOT_DIR"

  require_command uv
  require_command npm
  require_command python3

  BACKEND_PORT="$(find_open_port 8000)"
  WEB_PORT="$(find_open_port 3000)"
  API_BASE_URL="http://$BACKEND_HOST:$BACKEND_PORT"
  WEB_URL="http://localhost:$WEB_PORT"

  require_browser_opener

  load_env_api_key
  prompt_for_api_key

  log "Installing Python dependencies"
  uv sync

  if [ ! -d "$ROOT_DIR/web/node_modules" ]; then
    log "Installing web dependencies"
    npm --prefix web install
  fi

  trap cleanup INT TERM EXIT

  log "Starting backend on $API_BASE_URL"
  AIRLINE_SUPPORT_CORS_ORIGINS="$WEB_URL,http://127.0.0.1:$WEB_PORT" \
    uv run uvicorn airline_support.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
  BACKEND_PID="$!"

  wait_for_url "backend" "$API_BASE_URL/api/health" 60

  log "Starting web app on $WEB_URL"
  NEXT_PUBLIC_API_BASE_URL="$API_BASE_URL" npm --prefix web run dev -- --port "$WEB_PORT" &
  WEB_PID="$!"

  wait_for_url "web app" "$WEB_URL" 90

  log "Opening $WEB_URL"
  open_browser "$WEB_URL"

  printf '\nBackend and web app are running. Press Ctrl-C to stop both.\n'
  wait "$BACKEND_PID" "$WEB_PID"
}

main "$@"

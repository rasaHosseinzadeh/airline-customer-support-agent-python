#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT_DIR/.env"

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

commit_dependency_changes() {
  local paths=(
    "pyproject.toml"
    "uv.lock"
  )

  if ! command -v git >/dev/null 2>&1; then
    log "Skipping dependency commit: git is not available"
    return
  fi

  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log "Skipping dependency commit: not inside a git repository"
    return
  fi

  if [ -z "$(git status --porcelain -- "${paths[@]}")" ]; then
    return
  fi

  log "Committing dependency changes"
  if ! git add -- "${paths[@]}"; then
    log "Dependency commit failed while staging files; continuing without committing"
    return
  fi
  if ! git commit -m "Update Python dependency lock files" -- "${paths[@]}"; then
    log "Dependency commit failed; continuing without committing"
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

  load_env_api_key
  prompt_for_api_key

  log "Installing Python dependencies"
  uv sync
  commit_dependency_changes

  log "Starting terminal chat"
  uv run airline-support
}

main "$@"

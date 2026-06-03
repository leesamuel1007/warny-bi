#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QDRANT_URL="${WARNY_QDRANT_URL:-http://127.0.0.1:16333}"
OLLAMA_URL="${WARNY_OLLAMA_URL:-http://127.0.0.1:11434}"
SQL_CONTAINER="${WARNY_SQL_CONTAINER:-mssql2025}"
QDRANT_CONTAINER="${WARNY_QDRANT_CONTAINER:-warny-qdrant}"
INGEST=0
RECREATE=0

usage() {
  printf '%s\n' "Usage: scripts/bash/run_local_foss_api.sh [--ingest] [--recreate]"
  printf '%s\n' ""
  printf '%s\n' "Starts local Docker services if their containers exist, optionally refreshes Qdrant,"
  printf '%s\n' "then runs the WARNY-BI FastAPI service for Power BI."
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ingest)
      INGEST=1
      shift
      ;;
    --recreate)
      INGEST=1
      RECREATE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

cd "$PROJECT_ROOT"

if [[ ! -f config/.env ]]; then
  printf '%s\n' "Missing config/.env. Create it from config/.env.example and fill in local secrets."
  exit 1
fi

start_container_if_exists() {
  local name="$1"
  if ! command -v docker >/dev/null 2>&1; then
    return 0
  fi
  if docker ps -a --format '{{.Names}}' | grep -qx "$name"; then
    if ! docker ps --format '{{.Names}}' | grep -qx "$name"; then
      docker start "$name" >/dev/null
      printf '%s\n' "Started Docker container: $name"
    fi
  fi
}

wait_http() {
  local label="$1"
  local url="$2"
  local attempts="${3:-30}"
  local index
  for index in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      printf '%s\n' "$label is reachable."
      return 0
    fi
    sleep 1
  done
  printf '%s\n' "$label is not reachable at $url"
  return 1
}

start_container_if_exists "$SQL_CONTAINER"
start_container_if_exists "$QDRANT_CONTAINER"

wait_http "Qdrant" "$QDRANT_URL/collections" 30
wait_http "Ollama" "$OLLAMA_URL/api/tags" 30

if [[ "$INGEST" -eq 1 ]]; then
  if [[ "$RECREATE" -eq 1 ]]; then
    UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run python scripts/python/load_to_qdrant.py --recreate
  else
    UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run python scripts/python/load_to_qdrant.py
  fi
fi

UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run python scripts/python/run_rag_api.py

#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OPENSEARCH_URL="${OPENSEARCH_URL:-http://127.0.0.1:9200}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
SQL_CONTAINER="${SQL_CONTAINER:-mssql2025}"
OPENSEARCH_CONTAINER="${OPENSEARCH_CONTAINER:-warny-opensearch}"
INGEST=0
RECREATE=0
LOAD_DB=0

usage() {
  printf '%s\n' "Usage: scripts/bash/run_local_foss_api.sh [--load-db] [--ingest] [--recreate]"
  printf '%s\n' ""
  printf '%s\n' "Starts local Docker services if their containers exist, optionally loads processed"
  printf '%s\n' "CSVs into SQL Server, optionally refreshes OpenSearch, then runs the WARNY-BI"
  printf '%s\n' "FastAPI service for Power BI."
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
    --load-db)
      LOAD_DB=1
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
start_container_if_exists "$OPENSEARCH_CONTAINER"

wait_http "OpenSearch" "$OPENSEARCH_URL/_cat/health" 30
wait_http "Ollama" "$OLLAMA_URL/api/tags" 30

if [[ "$LOAD_DB" -eq 1 ]]; then
  UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run python scripts/python/load_to_db.py
  UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run python scripts/python/build_canonical_vocab.py
fi

if [[ "$INGEST" -eq 1 ]]; then
  if [[ "$RECREATE" -eq 1 ]]; then
    UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run python scripts/python/load_to_opensearch.py --recreate
  else
    UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run python scripts/python/load_to_opensearch.py
  fi
fi

UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}" uv run python scripts/python/run_rag_api.py

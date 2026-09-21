#!/usr/bin/env bash
#
# Starts and stops the six application services on the host.
#
#   ./scripts/services.sh start    start all six
#   ./scripts/services.sh stop     stop all six
#   ./scripts/services.sh status   health of each
#   ./scripts/services.sh logs 8001
#
# The datastores must already be running:  ./scripts/dev.sh up
#
# The services run on the host rather than in containers so you can edit a file
# and restart one service in a second. `docker compose up` runs the same six in
# containers when you want the full deployment shape.

set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"
LOGS="$ROOT/.logs"
mkdir -p "$LOGS"

if   [ -x ".venv/Scripts/python.exe" ]; then PY="$ROOT/.venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ];        then PY="$ROOT/.venv/bin/python"
else                                        PY="python"
fi

SERVICES=(
  "ingestion-api:8001"
  "retrieval-api:8002"
  "context-composer:8003"
  "deletion-orchestrator:8004"
  "memory-mcp-server:8005"
  "memory-processor:8006"
)

export_env() {
  # Point every service at the datastores `./scripts/dev.sh up` started.
  # Postgres is on 5433 because a natively installed PostgreSQL commonly owns
  # 5432; Redpanda's external listener is on 19092.
  export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
  export NEO4J_USER="${NEO4J_USER:-neo4j}"
  export NEO4J_PASSWORD="${NEO4J_PASSWORD:-neo4j_password_secure}"
  export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
  export POSTGRES_PORT="${POSTGRES_PORT:-5433}"
  export REDIS_HOST="${REDIS_HOST:-localhost}"
  export REDIS_PORT="${REDIS_PORT:-6379}"
  export KAFKA_BOOTSTRAP_SERVERS="${KAFKA_BOOTSTRAP_SERVERS:-localhost:19092}"
  export INGESTION_SERVICE_TOKEN="${INGESTION_SERVICE_TOKEN:-dev-ingestion-token}"
  export EMBEDDING_BACKEND="${EMBEDDING_BACKEND:-local_hash}"
}

start() {
  export_env
  for entry in "${SERVICES[@]}"; do
    name="${entry%%:*}"; port="${entry##*:}"
    ( cd "$ROOT/services/$name" \
      && nohup "$PY" -m uvicorn main:app --host 127.0.0.1 --port "$port" \
         > "$LOGS/$port.log" 2>&1 & )
    echo "  starting $name on $port"
  done
  echo
  echo "  waiting for them to come up..."
  for _ in $(seq 1 30); do
    up=0
    for entry in "${SERVICES[@]}"; do
      port="${entry##*:}"
      curl -s -m 2 -o /dev/null "http://localhost:$port/health" && up=$((up+1))
    done
    [ "$up" -eq 6 ] && break
    sleep 2
  done
  status
}

stop() {
  # Services are started with nohup and are not tracked by a pid file, so they
  # are found by the port they hold.
  for entry in "${SERVICES[@]}"; do
    port="${entry##*:}"
    if command -v powershell.exe >/dev/null 2>&1; then
      powershell.exe -NoProfile -Command "
        Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id \$_.OwningProcess -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1
    else
      pid=$(lsof -ti tcp:"$port" 2>/dev/null)
      [ -n "$pid" ] && kill -9 $pid 2>/dev/null
    fi
    echo "  stopped $port"
  done
}

status() {
  echo
  for entry in "${SERVICES[@]}"; do
    name="${entry%%:*}"; port="${entry##*:}"
    code=$(curl -s -m 3 -o /tmp/svc_status.json -w "%{http_code}" "http://localhost:$port/health")
    case "$code" in
      200) echo "  up        $name ($port)" ;;
      503) echo "  DEGRADED  $name ($port) — $(head -c 160 /tmp/svc_status.json)" ;;
      *)   echo "  DOWN      $name ($port) — see .logs/$port.log" ;;
    esac
  done
}

case "${1:-status}" in
  start)  start ;;
  stop)   stop ;;
  restart) stop; sleep 2; start ;;
  status) status ;;
  logs)   tail -f "$LOGS/${2:-8001}.log" ;;
  *) sed -n '3,12p' "$0" >&2; exit 2 ;;
esac

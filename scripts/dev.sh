#!/usr/bin/env bash
#
# Development task runner.
#
# The build plan called for a Makefile, but `make` is not installed on the
# Windows machine this project is developed on. This script gives the same
# verbs and runs anywhere Git Bash or a POSIX shell does — including inside CI.
#
# Usage:
#   ./scripts/dev.sh install     install dev + service dependencies
#   ./scripts/dev.sh lint        ruff
#   ./scripts/dev.sh typecheck   mypy
#   ./scripts/dev.sh test        pytest
#   ./scripts/dev.sh check       lint + typecheck + test (what CI runs)
#   ./scripts/dev.sh up          start the datastores and run migrations
#   ./scripts/dev.sh down        stop them (data is kept)
#   ./scripts/dev.sh destroy     stop them and delete the data
#   ./scripts/dev.sh migrate     re-run migrations only
#   ./scripts/dev.sh ps          what is running
#   ./scripts/dev.sh logs [svc]  follow logs
#
set -euo pipefail
cd "$(dirname "$0")/.."

# The virtualenv lives in .venv/Scripts on Windows and .venv/bin elsewhere.
# Fall back to whatever `python` is on PATH, which is the case inside CI.
if   [ -x ".venv/Scripts/python.exe" ]; then PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ];        then PY=".venv/bin/python"
else                                        PY="python"
fi

LINT_PATHS="packages services tests data"

case "${1:-check}" in
  install)
    "$PY" -m pip install --upgrade pip
    "$PY" -m pip install -r requirements-dev.txt
    "$PY" -m pip install -e packages/contracts
    ;;
  lint)      "$PY" -m ruff check $LINT_PATHS ;;
  format)    "$PY" -m ruff check --fix $LINT_PATHS ;;
  typecheck) "$PY" -m mypy ;;
  test)      "$PY" -m pytest ;;
  check)
    echo "── lint ──────────────────────────────────────────────"
    "$PY" -m ruff check $LINT_PATHS
    echo "── typecheck ─────────────────────────────────────────"
    "$PY" -m mypy
    echo "── test ──────────────────────────────────────────────"
    "$PY" -m pytest
    ;;
  up)
    # Starts the datastores and applies the migrations. The migrator is a
    # one-shot container that must exit 0; every application service waits on
    # it, so nothing can run against an unmigrated database (§6.4 step 4).
    docker compose up -d --wait postgres neo4j redis redpanda
    docker compose run --rm migrator
    echo
    echo "datastores ready:"
    echo "  neo4j      bolt://localhost:7687   browser http://localhost:7474"
    echo "  postgres   localhost:5433"
    echo "  redis      localhost:6379"
    echo "  redpanda   localhost:19092"
    ;;
  down)    docker compose down ;;
  destroy)
    # Also removes the volumes. Everything stored locally is lost.
    docker compose down -v
    ;;
  migrate) docker compose run --rm migrator ;;
  ps)      docker compose ps ;;
  logs)    docker compose logs -f "${2:-}" ;;
  *)
    echo "unknown task: $1" >&2
    sed -n '8,22p' "$0" >&2
    exit 2
    ;;
esac

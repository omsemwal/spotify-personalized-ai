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
#   ./scripts/dev.sh up          start the datastores via docker compose
#   ./scripts/dev.sh down        stop them
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
  up)   docker compose up -d postgres neo4j redis redpanda ;;
  down) docker compose down ;;
  *)
    echo "unknown task: $1" >&2
    sed -n '8,17p' "$0" >&2
    exit 2
    ;;
esac

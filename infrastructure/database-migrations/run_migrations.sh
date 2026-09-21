#!/usr/bin/env bash
#
# Applies every schema migration, then exits.
#
# §6.4 step 4: "Apply schema constraints and migrations before traffic." This
# runs as the one-shot `migrator` service in docker-compose.yml, and every
# application service waits for it to exit successfully — so a service can never
# start against an unmigrated database.
#
# Re-running is safe. Both migrations are idempotent: the Cypher uses
# CREATE ... IF NOT EXISTS and the SQL uses CREATE TABLE IF NOT EXISTS.
#
# It runs inside the neo4j image because that image already carries
# cypher-shell; psql is installed on first run. Failing here fails the whole
# stack, which is the point — a partially migrated database is worse than one
# that never started.

set -euo pipefail

MIGRATIONS_DIR="$(dirname "$0")"

echo "── applying Neo4j constraints ──────────────────────────────"
cypher-shell \
  -a "bolt://${NEO4J_HOST:-neo4j}:7687" \
  -u "${NEO4J_USER:-neo4j}" \
  -p "${NEO4J_PASSWORD:?NEO4J_PASSWORD must be set}" \
  --fail-at-end \
  -f "${MIGRATIONS_DIR}/001_neo4j_constraints.cypher"
echo "   neo4j constraints applied"

echo "── applying PostgreSQL schema ──────────────────────────────"
if ! command -v psql >/dev/null 2>&1; then
  echo "   installing postgresql-client"
  apt-get update -qq >/dev/null
  apt-get install -y -qq postgresql-client >/dev/null
fi

# ON_ERROR_STOP makes psql exit non-zero on the first failed statement.
# Without it psql reports success after running a broken migration.
psql -v ON_ERROR_STOP=1 \
  --host "${PGHOST:-postgres}" \
  --username "${PGUSER:-postgres}" \
  --dbname "${PGDATABASE:-memory_system}" \
  --file "${MIGRATIONS_DIR}/001_postgres_operational_store.sql"
echo "   postgres schema applied"

echo "── migrations complete ─────────────────────────────────────"

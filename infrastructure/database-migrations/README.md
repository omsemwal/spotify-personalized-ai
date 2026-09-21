# infrastructure/database-migrations

**What this is:** Versioned, numbered migrations for both persistent stores,
each with a rollback statement inline (§5.5 Maintainability: "Migrations
require compatibility checks and rollback plans").

## Files
- `001_neo4j_constraints.cypher` — the graph uniqueness constraints and
  indexes (mirrors `packages/graph-schema/constraints.py`, kept here as the
  canonical, ordered migration artifact).
- `001_postgres_operational_store.sql` — the operational store tables
  (§6.2 PostgreSQL): `consent_state`, `ingestion_status`, `tool_audit`,
  `experiments`, `feedback`, `deletion_jobs`.

## Apply
```bash
# Neo4j
cat 001_neo4j_constraints.cypher | cypher-shell -u neo4j -p "$NEO4J_PASSWORD"

# Postgres
psql "$DATABASE_URL" -f 001_postgres_operational_store.sql
```

## Numbering convention
`NNN_description.ext` — increment `NNN` for every future migration, never edit
a shipped migration in place. This is what makes rollback and compatibility
checks (§7.8 step 3) possible during a canary release.

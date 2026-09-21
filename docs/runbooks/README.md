# docs/runbooks

**What this is:** Operator runbooks for the incidents the Operations Lead and
Site Reliability Lead named in the leadership transcript (§4). Spec ref: §5.5
Deployment readiness — "health checks... rollback, and runbooks."

## Files
- `ingestion_lag.md` — events accepted but not yet reflected as memories.
- `graph_or_vector_outage.md` — the graph or vector store is down; documents
  the expected fail-open behavior and how to confirm it's engaging correctly.
- `deletion_backlog.md` — deletion jobs piling up; per-store retry guidance.

Each runbook ties directly to an alert in `infrastructure/monitoring/alerts.yml`.

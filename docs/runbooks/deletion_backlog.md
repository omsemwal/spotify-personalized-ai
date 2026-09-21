# Runbook: Deletion Backlog Growing

**Alert:** `DeletionBacklogGrowing` (`infrastructure/monitoring/alerts.yml`).

## Diagnosis
1. `GET /v1/deletions/{job_id}` for a sample of recent jobs — check which
   store's status is stuck at `pending`/`failed` rather than `completed`.
2. If `graph` is stuck: check Neo4j connectivity/load.
3. If `operational_store` is stuck: check PostgreSQL connectivity.

## Mitigation
- Deletion jobs in `services/deletion-orchestrator/main.py` are per-store —
  retry just the failed store's step rather than re-running the whole job
  (avoids redundant work on stores that already completed).
- `backup_policy` legitimately stays at `scheduled` until the backup system's
  own retention cycle runs — this is expected, not a stuck job, and should
  not itself count toward the backlog alert.

## Escalation
If deletion cannot complete within the SLA in `packages/policy-engine`'s
retention policy for a given memory type, escalate to Data Governance per
§5.4 — an incomplete deletion is a release-blocking issue per §7.7.

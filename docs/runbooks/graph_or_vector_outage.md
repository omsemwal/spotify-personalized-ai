# Runbook: Graph or Vector Store Outage

**Alert:** `GraphWriteFailureSpike` (`infrastructure/monitoring/alerts.yml`).

## Expected behavior during outage (§5.5 Reliability — this is BY DESIGN)
- `context-composer` must fail open: `POST /v1/context/compose` returns
  `fallback_used=true` immediately rather than hanging (see its `httpx` call
  timeout of 0.25s and except-block fallback in `main.py`).
- `ingestion-api` continues accepting events into the queue — it does not
  depend on the graph being reachable (§6.1 step 1).
- `memory-processor` should stop consuming or move failing events to a
  dead-letter path rather than dropping them.

## Diagnosis
1. `curl :8002/health`, `curl :8006/health` — confirm which service is affected.
2. Check Neo4j / Qdrant container health directly: `docker-compose ps`.
3. Check `RetrievalLatencyP95Breach` and `HighFallbackRate` alerts together —
   a spike in both confirms the composer's fail-open path is engaging correctly.

## Recovery
1. Restore the underlying store (restart container / scale up / restore from
   backup per its own runbook).
2. Run `packages/graph-schema/constraints.py` again if the store was rebuilt
   from scratch (`CREATE CONSTRAINT ... IF NOT EXISTS` is idempotent).
3. Replay any dead-lettered events via `memory-processor`'s replay path.
4. Confirm `HighFallbackRate` returns to baseline.

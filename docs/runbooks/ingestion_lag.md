# Runbook: Ingestion Lag

**Alert:** none dedicated yet — watch `ingestion_status` table growth rate
(see `infrastructure/database-migrations/001_postgres_operational_store.sql`).

## Symptoms
Events accepted (`202`) by `ingestion-api` but not yet reflected as memories
in `retrieval-api` search results after several minutes.

## Diagnosis
1. Check `services/memory-processor` health: `curl :8006/health`.
2. Check the queue: in local mode, `QueueAdapter.drain_local_queue_for_tests()`
   shows backlog size; in production, check Kafka/Redpanda consumer lag for
   the `interaction-events` topic and consumer group.
3. Check for `graph_write_failures_total` spikes (`infrastructure/monitoring/alerts.yml`
   → `GraphWriteFailureSpike`).

## Mitigation
- If `memory-processor` is down: restart it; the queue is durable (Kafka/Redpanda)
  so no events are lost, only delayed.
- If Neo4j is unreachable: `memory-processor` should fail its writes loudly
  (not silently drop) — check for a dead-letter queue backlog and replay once
  Neo4j recovers, using idempotency keys to avoid duplicate writes.

## Replay
Use the idempotent write path (`MERGE` semantics in `graph.py`) — replaying
the same event is always safe, never creates a duplicate memory.

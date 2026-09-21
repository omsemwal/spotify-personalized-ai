# Architecture Overview

Mirrors §6.1's architecture narrative exactly, mapped to the services that
implement each step.

| # | Step (§6.1) | Implemented by |
|---|---|---|
| 1 | Capture and authorize | `services/ingestion-api` — `POST /v1/events` |
| 2 | Extract and normalize | `services/memory-processor` — `classifier.py`, `entity_resolution.py` |
| 3 | Write temporal graph | `packages/graph-schema` (`graph.py` / `memory_store.py`) via `memory-processor` |
| 4 | Create embeddings | `services/retrieval-api/embeddings.py` + `vector_store.py`, same `memory_id` as the graph |
| 5 | Retrieve candidates | `services/retrieval-api` — hybrid graph + vector candidate generation |
| 6 | Rerank and govern | `services/retrieval-api/reranker.py` + `packages/policy-engine` |
| 7 | Compose context | `services/context-composer` — `POST /v1/context/compose` |
| 8 | Generate and observe | LLM orchestrator (outside this repo's scope) consumes the `ContextPackage`; `packages/observability` records the trace |

## Technology choices (§6.2)
See the root `docker-compose.yml` for the exact stack: PostgreSQL (operational
store), Neo4j (temporal graph + vector index option), Redis (cache/idempotency),
Redpanda (Kafka-compatible event transport), Qdrant (optional dedicated vector
store). Every service's `requirements.txt` lists its production dependencies;
local-mode fallbacks (see each service's README "Local-mode fallback" section)
let the pipeline run without the full stack for development and testing.

## Why services are separate processes, not one monolith
§4 (CTO): "We need one shared capability, not a separate memory implementation
inside every AI surface." Splitting into `ingestion-api` / `memory-processor` /
`retrieval-api` / `context-composer` / `memory-mcp-server` /
`deletion-orchestrator` lets each scale and fail independently — a slow
`retrieval-api` degrades to a fallback in `context-composer` rather than
blocking `ingestion-api`'s accept path (§5.5 Reliability).

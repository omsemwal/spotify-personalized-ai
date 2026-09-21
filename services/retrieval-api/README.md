# services/retrieval-api

**What this is:** Hybrid candidate generation (graph + vector), reranking, and
the authorized trace endpoint. Owns 2 of the 10 required APIs.

## APIs owned (§7.3)
| Endpoint | Behavior |
|---|---|
| `POST /v1/memories/search` | Subject-scoped hybrid retrieval → rerank → policy filter → ranked results. Returns `fallback_used=true` with an empty result set when nothing survives policy filtering — never a partial/cross-subject result (§5.5 Reliability: fail open). |
| `GET /v1/traces/{trace_id}` | Returns the redacted `Trace` recorded during that search — every stage's duration, outcome, and which `memory_id`s were used. |

## Pipeline (§6.1 steps 5-6)
1. **Candidate generation** — graph candidates (`graph_store.get_all_for_subject`,
   subject-scoped) + vector similarity (`embeddings.py` + `vector_store.py`,
   same `memory_id` as the graph).
2. **Rerank** (`reranker.py`) — weighted score across vector similarity,
   explicitness, confidence, recency, and graph-match bonus; applies an
   entity-cluster diversity cap so one preference can't dominate the pack.
3. **Policy filter** — every reranked item re-runs `PolicyEngine.evaluate_retrieval()`
   (see `packages/policy-engine`) — a memory eligible at write time can still be
   excluded here (expired, surface-ineligible, low-confidence).

## Embeddings backend
`embeddings.py` defaults to a deterministic local hashing embedder
(`EMBEDDING_BACKEND=local_hash`) so the service runs without downloading model
weights. Set `EMBEDDING_BACKEND=sentence_transformers` to use the real
`all-MiniLM-L6-v2` model in an environment with network access (§6.2).

## Trace storage (pilot)
Traces are kept in an in-process dict for the pilot. Production should persist
them to the operational PostgreSQL store (§6.2) so `GET /v1/traces/{trace_id}`
survives a restart.

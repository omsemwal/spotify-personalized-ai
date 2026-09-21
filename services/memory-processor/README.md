# services/memory-processor

**What this is:** Converts approved interaction events into typed candidate
memories, resolves entities, applies the policy gate, and writes accepted
facts into the temporal graph. Owns 3 of the 10 required APIs.

## APIs owned (§7.3)
| Endpoint | Behavior |
|---|---|
| `POST /v1/memories/extract` | Runs `classifier.classify()` on one `InteractionEvent`, returns `ExtractionResult` with typed `ExtractionCandidate`s. Does **not** write to the graph — deterministic validation only. |
| `POST /v1/memories` | The only path allowed to create a new durable memory. Runs `PolicyEngine.evaluate_write()` first; on denial returns `403 policy_denial` with rejection codes. |
| `PATCH /v1/memories/{id}` | `action=correct` supersedes (closes old `valid_to`, links `SUPERSEDES`, never deletes history); `action=expire` marks `status=expired`. Uses optimistic concurrency via `expected_version`. |

## Files
- `classifier.py` — deterministic-rules extraction (§7.5: "deterministic rules
  plus structured model output" — an LLM extractor can be swapped in behind the
  same `ExtractionCandidate` contract without changing callers).
- `entity_resolution.py` — canonical alias table standing in for the real
  catalog service (§7.2 step 4).
- `store_factory.py` — dependency injection: real Neo4j (`graph.py`) in
  production, `InMemoryGraphStore` (`memory_store.py`) for local/dev/test.

## Memory safety (§7.5)
> "Never write a new durable fact solely because the model generated it in a
> response. Only eligible user or product evidence can create memory."

`POST /v1/memories` is only ever called from a validated `ExtractionCandidate`
with `decision == "accept"`, or from an explicit user statement/MCP tool call —
never directly from LLM output.

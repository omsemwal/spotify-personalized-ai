# Threat Model (§4 Security Lead, §5.5 Security)

| Threat | Mitigation | Where |
|---|---|---|
| Cross-user leakage | Every graph read is scoped by `subject_id`; no traversal method exists without it | `packages/graph-schema` — see `tests/security/test_subject_isolation.py` |
| Prompt injection through stored text | Stored `fact_text` is only ever emitted in the structured `fact` field of `ContextItem`, never merged into instruction fields | `services/context-composer/composer.py` — see `tests/security/test_prompt_injection_stored_content.py` |
| Unauthorized tool calls | Every MCP tool call is subject-bound, rate-limited, and audited | `services/memory-mcp-server/{rate_limiter,audit}.py` |
| Replay of stale tokens | Idempotency keys with TTL; service tokens checked per-request (pilot: static registry — replace with real workload-identity/mTLS before production) | `services/ingestion-api/{idempotency_adapter,auth}.py` |
| Malicious/malformed events | Schema validation rejects before graph processing; consent-denied events rejected outright | `services/ingestion-api/main.py` |
| Sensitive inference leakage (mood/mental-health) | Blocked at the policy-engine write gate, never even reaches the graph | `packages/policy-engine/registry.py::BLOCKED_INFERRED_CATEGORIES` |
| Silent partial deletion | Deletion reports per-store status, not one boolean | `services/deletion-orchestrator/main.py` |

## Known gaps for a production release (explicitly out of pilot scope)
- `auth.py`'s static service-token registry must be replaced with real
  workload identity (mTLS + signed JWT) before any non-synthetic data is used.
- Rate limiting is per-process (in-memory token bucket) — needs a shared
  Redis-backed limiter for a multi-instance deployment.
- The trace store in `retrieval-api` is in-memory — needs to persist to
  PostgreSQL so traces survive a restart (see `infrastructure/database-migrations`).

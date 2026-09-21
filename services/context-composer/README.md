# services/context-composer

**What this is:** The only service allowed to hand memory content to an LLM.
It calls `retrieval-api`, applies the token budget, and returns either a
populated `ContextPackage` or a deterministic no-memory fallback. Owns 2 of
the 10 required APIs.

## APIs owned (§7.3)
| Endpoint | Behavior |
|---|---|
| `POST /v1/context/compose` | Calls retrieval-api with a 250ms timeout (§5.5 P95 budget). On timeout/error, **fails open** — returns `fallback_used=true`, never a partial or stale result. |
| `POST /v1/feedback` | Records relevance/correction/rejection signal. Never used to auto-validate or reinforce a model-generated claim (§5.4). |

## Prompt-injection boundary (§5.4)
> "Treat stored free text as untrusted data and isolate it from system
> instructions to reduce prompt-injection risk."

`composer.py` only ever emits structured `ContextItem` fields (`fact`,
`memory_type`, `confidence`, ...). It is the caller's (the LLM orchestrator's)
responsibility to render these as **quoted data** in the prompt template —
never string-concatenate `fact` into a system/instruction message. See
`tests/security/` for the adversarial-stored-content test that checks this.

## Fail-open behavior (§5.5 Reliability)
> "Memory retrieval must fail open to a non-personalized response. No partial
> or cross-subject context may be injected after a timeout or authorization
> failure."

If `retrieval-api` is slow or down, `/v1/context/compose` returns immediately
with an empty, explicit no-memory package rather than hanging or retrying
indefinitely.

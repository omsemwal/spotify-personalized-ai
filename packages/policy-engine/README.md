# packages/policy-engine

**What this is:** The eligibility and retention rule engine. Every candidate
memory passes `evaluate_write()` before it can be written to the graph; every
stored memory passes `evaluate_retrieval()` again at query time before it can
enter a context package. Spec ref: §5.4 "User Control, Privacy, and Safety",
§6.1 step 6 "Rerank and govern."

## Why evaluation happens twice
A memory that was eligible when written can become ineligible later — it can
expire, get superseded, or the requesting surface can change. §5.4 requires
"Exclude memories that are expired, contradicted, disallowed, low-confidence,
or outside the active surface policy" **at composition time**, not just at
write time. That is why `PolicyEngine` has two entry points instead of one.

## Files
- `registry.py` — the policy registry (§5.4 Data Governance Lead requirement):
  one entry per memory type with sensitivity, allowed purposes, and retention
  days. Also lists `BLOCKED_INFERRED_CATEGORIES` — emotional/mental-health/medical
  inference is never durable by default (Privacy Lead's explicit instruction).
- `engine.py` — `PolicyEngine` with `evaluate_write()` and `evaluate_retrieval()`,
  each returning `(allowed: bool, rejection_codes: list[str])` for full
  provenance in `PolicyDecision` (see `packages/contracts/policy.py`).

## Changing the registry
Adding a new memory type or sensitive category is a **governed change** — per
§7.5, it requires policy/data-governance sign-off, not a code review alone.

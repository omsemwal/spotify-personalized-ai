# Policy Registry (human-readable mirror of `packages/policy-engine/registry.py`)

| Memory type | Sensitivity | Allowed purposes | Retention (days) | Requires explicit confirmation |
|---|---|---|---|---|
| episode | normal | continuity, personalization | 30 | no |
| explicit_preference | normal | continuity, personalization, correction | 365 | no |
| candidate_preference | normal | personalization | 90 | **yes** |
| exclusion | normal | personalization, safety | 365 | no |
| correction | normal | continuity, correction | 365 | no |

## Blocked inferred categories (never durable by default)
`emotional_state`, `mood_inference`, `mental_health_inference`,
`medical_inference`, `political_affiliation_inference` — per §5.4 Privacy
Lead: "We should not store inferred emotional state as a durable profile by
default."

## Changing this registry
This is a **governed change** — requires policy/data-governance sign-off
(§7.5), not a standalone code review. Update both `packages/policy-engine/registry.py`
and this document in the same change.

# Policy Registry

**Human-readable mirror of `packages/policy-engine/policy_registry.yaml`.**

The YAML file is the one the code reads. This document explains it. A test
(`tests/unit/test_policy_engine.py::test_registry_defines_exactly_the_taxonomy_types`)
fails if the registry, this document and
`docs/architecture/memory_taxonomy.md` stop agreeing on the same five types.

The rules live in YAML rather than in Python because §7.5 requires policy or
data-governance approval for changes to memory types, sensitive categories and
scoring rules. Reviewing a policy change should not require reading code.

---

## Memory types

| Memory type | Sensitivity | Allowed purposes | Retention | Needs confirmation | Min. confidence | Partial consent | Minors |
|---|---|---|---|---|---|---|---|
| `explicit_preference` | normal | continuity, personalization, correction | 365 d | no | 0.30 | allowed | allowed |
| `exclusion` | normal | personalization, safety | 365 d | no | 0.30 | allowed | allowed |
| `correction` | normal | continuity, correction | 365 d | no | **0.00** | allowed | allowed |
| `candidate_preference` | normal | personalization | 90 d | **yes** | 0.30 | refused | refused |
| `episode` | normal | continuity, personalization | 30 d | no | 0.30 | refused | refused |

Three things in that table are worth explaining:

- **`correction` has a minimum confidence of zero.** Every other type can be
  filtered out for being uncertain. A correction cannot, because suppressing it
  would mean carrying on using the very thing the user just told us was wrong.
- **The last two columns split the taxonomy in half.** `explicit_preference`,
  `exclusion` and `correction` are things the user *said*. `candidate_preference`
  and `episode` are things we *inferred*. Partial consent and age protection
  both draw the line in exactly that place: keep what they told us, drop what we
  worked out about them.
- **Retention is shortest for episodes.** Their value is almost entirely
  recency, and they are by far the highest-volume type.

## Prohibited inferences

Never stored, in any type, under any configuration:

`emotional_state`, `mood_inference`, `mental_health_inference`,
`medical_inference`, `political_affiliation_inference`

§4, Privacy Lead: *"We should not store inferred emotional state as a durable
profile by default."* There is no setting that enables these — the check does
not consult the per-type rules at all.

## Consent states

| State | Effect |
|---|---|
| `granted` | Everything the taxonomy permits. |
| `partial` | Only types the user stated outright. Enforced at **write and at retrieval**, so narrowing consent later takes effect on memories that already exist. |
| `denied` | Nothing is written, nothing is retrieved. |

## Subject controls

| Control | Blocks retrieval | Blocks capture |
|---|---|---|
| **Paused** | yes | no |
| **Opted out** | yes | yes |

Pause stops memory being *used*, not being *recorded*. That is what §5.3
specifies — *"Revokes retrieval eligibility"* — and it is what makes pause
reversible: unpausing restores a continuous history instead of leaving a gap.
Opt-out is the control that stops capture.

## Regional retention caps

> ⚠ **Placeholder values.** The mechanism works and is tested. The numbers are
> not a legal position and need a data-governance decision before this system
> handles non-synthetic data.

| Region | Maximum retention |
|---|---|
| `GLOBAL` | no additional cap |
| `EU` | 180 days |
| `US` | no additional cap |
| `IN` | no additional cap |

A region may only **shorten** retention, never extend it — the effective value
is the smaller of the per-type retention and the regional cap. A request from a
region that is not in this table is **refused** with `unknown_region` rather
than defaulted to `GLOBAL`, because defaulting would apply the most permissive
retention to a region nobody has assessed.

## Reason codes

Every refusal returns at least one of these. §7.3 requires stable error codes:
the operations console groups on them and both web apps map them to the text a
user sees. **Adding a code is safe; renaming one is a breaking change.**

| Code | Meaning |
|---|---|
| `consent_denied` | The subject has not consented to memory |
| `consent_partial_type_not_allowed` | Partial consent, and this type was inferred rather than stated |
| `subject_opted_out` | The subject has opted out entirely |
| `memory_paused` | The subject has paused memory use |
| `blocked_sensitive_inference` | A prohibited inference category |
| `unknown_memory_type` | Not in the registry — including a type a model invented |
| `memory_type_blocked` | The type exists but its sensitivity is `blocked` |
| `region_restricted` | This type is not permitted in the subject's region |
| `minor_restricted` | Age protection: inference about a minor |
| `retention_expired` | Past retention, or its valid-time has been closed |
| `low_confidence` | Below the type's minimum confidence |
| `surface_ineligible` | The calling surface has no purpose this type allows |
| `unknown_region` | The subject's region has not been assessed |
| `status_superseded` / `status_expired` / `status_deleted` | The memory is no longer the current version |

## Changing the registry

A **governed change** (§7.5), not an ordinary code review. In order:

1. Update `docs/architecture/memory_taxonomy.md` first, including counter-examples.
2. Update `packages/policy-engine/policy_registry.yaml`.
3. Update this document.
4. Add test rows to `tests/unit/test_policy_engine.py` — including cases that
   must be **refused**.
5. For a new memory type, show the golden-set evidence. §4: *"Do not widen the
   stored-memory taxonomy until the evaluation data supports it."*

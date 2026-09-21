# data/golden-sets

**What this is:** The golden evaluation set required by §5.4 Quality
Engineering Lead and gated by §7.7's release gate. Each case specifies the
expected top memories, any memory that must NOT appear (`prohibited_memory_ids`),
and the context budget — scored by `packages/evaluation/scorer.py`.

## Coverage (matches §5.4 and §7.2 step 7 exactly)
| Case | Covers |
|---|---|
| `gc_001_stable_preference` | Stable, explicit preference |
| `gc_002_contradiction_correction_wins` | Contradiction/correction handling — superseded fact must not leak |
| `gc_003_playlist_exclusion` | Durable exclusion |
| `gc_004_multilingual_statement` | Multilingual phrasing (es-ES) |
| `gc_005_sparse_history_no_memory_fallback` | Sparse history → deterministic no-memory fallback |
| `gc_006_adversarial_stored_content` | Adversarial stored content / prompt-injection resistance |

## Release-gate significance (§7.7)
Any case where `prohibited_memory_ids` leaks into the actual output —
especially `gc_006`'s cross-subject check — is **release-blocking** regardless
of aggregate score, per §7.7: "No launch if cross-subject leakage is observed..."

## Running the golden set
```python
from packages.evaluation import load_golden_set, score_golden_case
cases = load_golden_set("data/golden-sets/pilot_golden_set.json")
# for each case: call context-composer with case["subject_id"]/["surface"]/["intent"],
# then score_golden_case(case, actual_context_items=response["items"])
```
See `tests/end-to-end/test_golden_set_run.py` for the full harness.

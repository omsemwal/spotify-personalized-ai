# packages/evaluation

**What this is:** Offline quality scoring against the golden set in
`data/golden-sets/`. Spec ref: §5.4 "Experimentation and Quality Review",
§7.7 "Release gate."

## Files
- `loader.py` — reads golden case JSON files.
- `scorer.py` — `score_golden_case()` compares a pipeline's actual
  `ContextPackage.items` against a case's expectations: precision@k, whether a
  prohibited memory leaked, and whether the context-budget was respected.

## Release gate (§7.7)
> "No launch if cross-subject leakage is observed, deletion propagation is
> incomplete, provenance falls below threshold, or personalized output
> materially underperforms the memory-disabled baseline."

`GoldenCaseResult.prohibited_memory_leaked = True` on **any** case is treated
as release-blocking, not just a lower score — see `notes` field.

## Usage
```python
from packages.evaluation import load_golden_set, score_golden_case
cases = load_golden_set("data/golden-sets/pilot_golden_set.json")
for case in cases:
    result = score_golden_case(case, actual_context_items=pipeline_output)
```

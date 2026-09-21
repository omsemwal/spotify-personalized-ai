# tests/end-to-end

Full-lifecycle tests: capture → extraction → graph write → retrieval →
context injection → (fallback) → feedback. Corresponds to §11's submission
checklist item: "Core workflow works end to end."

| File | Covers |
|---|---|
| `test_full_lifecycle.py` | Full pipeline via in-memory adapters + explicit no-memory fallback case |
| `test_golden_set_run.py` | Loads and scores all 6 golden-set cases via `packages/evaluation` |

`test_golden_set_run.py` ships with a stub `run_case_stub()` that returns no
memories — replace it with real HTTP calls to `context-composer` once the
docker-compose stack is running, so the golden set is scored against the
actual pipeline rather than the stub.

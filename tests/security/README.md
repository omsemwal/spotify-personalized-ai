# tests/security

Release-gating security tests (§7.7 release gate: "No launch if cross-subject
leakage is observed... or provenance falls below threshold").

| File | Covers |
|---|---|
| `test_subject_isolation.py` | Graph traversal never crosses `subject_id` boundaries |
| `test_prompt_injection_stored_content.py` | Malicious stored fact text stays confined to the `fact` field — never promoted into an instruction-bearing field |

## Note on scope
These tests check the boundaries this codebase controls (data confinement,
subject scoping). The actual prompt template used by whatever LLM orchestrator
consumes `ContextPackage` must independently render `.fact` as quoted data —
see `services/context-composer/README.md`'s "Prompt-injection boundary" section.

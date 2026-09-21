# tests/unit

Unit tests for pure logic with no external services: contract validation,
policy-engine decisions, and graph supersession semantics.

| File | Covers |
|---|---|
| `test_contracts_validation.py` | Pydantic contracts reject malformed input |
| `test_policy_engine.py` | Consent denial, blocked inferred categories, low-confidence exclusion |
| `test_graph_supersession.py` | Correction supersedes without deleting history (§6.1 step 3) |

Run: `pytest tests/unit -v` (requires `pip install -r services/*/requirements.txt` for pydantic/etc.)

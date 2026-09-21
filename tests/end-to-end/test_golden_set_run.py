"""End-to-end: runs every case in data/golden-sets/pilot_golden_set.json
against a simplified in-memory pipeline and scores it with
packages/evaluation/scorer.py. This is a structural harness — wire real
retrieval-api HTTP calls in place of the stubbed `run_case()` once the full
stack is deployed."""
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from packages.evaluation import load_golden_set, score_golden_case


def run_case_stub(case: dict) -> list:
    """Placeholder pipeline call — replace with a real POST to context-composer
    once running against the live docker-compose stack. Returns [] (no memory)
    by default, which is intentionally conservative for a stub."""
    return []


def test_golden_set_loads_and_scores():
    cases = load_golden_set(str(repo_root / "data" / "golden-sets" / "pilot_golden_set.json"))
    assert len(cases) == 6
    for case in cases:
        result = score_golden_case(case, actual_context_items=run_case_stub(case))
        assert result.case_id == case["case_id"]
        # This stub should never itself leak a prohibited memory, since it returns [].
        assert result.prohibited_memory_leaked is False

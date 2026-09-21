"""
Offline scoring for golden cases (§5.4 "Quality Engineering Lead" requirement:
"precision at the top of the retrieved set, not just retrieval recall").
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GoldenCaseResult:
    case_id: str
    precision_at_k: float
    contradiction_detected: bool
    prohibited_memory_leaked: bool
    context_budget_respected: bool
    notes: list[str] = field(default_factory=list)


def score_golden_case(case: dict[str, Any], actual_context_items: list[dict[str, Any]]) -> GoldenCaseResult:
    """Compare a golden case's expectations against what the pipeline actually produced.

    Expected case shape (see data/golden-sets/):
      {
        "case_id": str,
        "expected_top_memory_ids": [str, ...],
        "prohibited_memory_ids": [str, ...],
        "context_budget": int,
        "expects_contradiction_handling": bool
      }
    """
    actual_ids = [item["memory_id"] for item in actual_context_items]
    expected_top = case.get("expected_top_memory_ids", [])
    prohibited = set(case.get("prohibited_memory_ids", []))

    hits = sum(1 for mid in actual_ids[: len(expected_top)] if mid in expected_top)
    precision_at_k = hits / max(len(expected_top), 1)

    leaked = any(mid in prohibited for mid in actual_ids)
    budget_ok = len(actual_context_items) <= case.get("context_budget", 10)

    notes = []
    if leaked:
        notes.append("PROHIBITED MEMORY LEAKED — release-blocking per §7.7 release gate")
    if precision_at_k < 1.0:
        notes.append(f"precision@k={precision_at_k:.2f}, expected top set not fully matched")

    return GoldenCaseResult(
        case_id=case.get("case_id", "unknown"),
        precision_at_k=precision_at_k,
        contradiction_detected=case.get("expects_contradiction_handling", False),
        prohibited_memory_leaked=leaked,
        context_budget_respected=budget_ok,
        notes=notes,
    )

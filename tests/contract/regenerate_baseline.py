"""
Regenerates `contract_baseline.json`, the frozen snapshot that
test_schema_backward_compatibility.py compares the live contracts against.

Run this ONLY when you have deliberately made a breaking contract change and
have bumped SCHEMA_VERSION in packages/contracts/events.py in the same pull
request. Running it to make a red test go green defeats the entire point of
the test.

    python tests/contract/regenerate_baseline.py
"""

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from packages import contracts

# Every model a service or a web app depends on. A model absent from this list
# is not covered by the compatibility tests, so add new shared contracts here.
TRACKED_MODELS = [
    "InteractionEvent",
    "Memory",
    "MemoryCreateRequest",
    "MemoryCorrectionRequest",
    "ExtractionCandidate",
    "ExtractionResult",
    "PolicyDecision",
    "RetrievalCandidate",
    "RetrievalCandidateSet",
    "VectorRecord",
    "ContextItem",
    "ContextPackage",
    "FeedbackEvent",
    "Trace",
    "TraceStage",
    "SearchMemoryInput",
    "SearchMemoryOutput",
    "SearchMemoryResult",
    "AddExplicitPreferenceInput",
    "AddExplicitPreferenceOutput",
    "CorrectMemoryInput",
    "CorrectMemoryOutput",
    "DeleteMemoryInput",
    "DeleteMemoryOutput",
    "ExplainMemoryUseInput",
    "ExplainMemoryUseOutput",
]


def build_baseline() -> dict:
    baseline: dict = {"schema_version": contracts.SCHEMA_VERSION, "models": {}}
    for name in TRACKED_MODELS:
        model = getattr(contracts, name)
        fields = {
            fname: {"required": finfo.is_required()} for fname, finfo in model.model_fields.items()
        }
        baseline["models"][name] = {"fields": dict(sorted(fields.items()))}
    return baseline


if __name__ == "__main__":
    out = Path(__file__).parent / "contract_baseline.json"
    out.write_text(json.dumps(build_baseline(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out} covering {len(TRACKED_MODELS)} contracts")
    print("Confirm SCHEMA_VERSION was bumped in the same pull request.")

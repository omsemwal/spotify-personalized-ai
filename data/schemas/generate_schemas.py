"""
Regenerates every JSON Schema file in this folder from the live Pydantic
contracts in packages/contracts. Run this after any contract change so the
exported schemas never drift from the actual models (§5.5 Maintainability).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from packages.contracts import (
    ContextPackage,
    ExtractionResult,
    FeedbackEvent,
    InteractionEvent,
    Memory,
    PolicyDecision,
    RetrievalCandidateSet,
    Trace,
    VectorRecord,
)

MODELS = {
    "interaction_event.schema.json": InteractionEvent,
    "memory.schema.json": Memory,
    "extraction_result.schema.json": ExtractionResult,
    "context_package.schema.json": ContextPackage,
    "policy_decision.schema.json": PolicyDecision,
    "feedback_event.schema.json": FeedbackEvent,
    "trace.schema.json": Trace,
    "retrieval_candidate_set.schema.json": RetrievalCandidateSet,
    "vector_record.schema.json": VectorRecord,
}

if __name__ == "__main__":
    out_dir = Path(__file__).parent
    for filename, model in MODELS.items():
        schema = model.model_json_schema()
        (out_dir / filename).write_text(json.dumps(schema, indent=2))
        print(f"wrote {filename}")

# data/schemas

**What this is:** JSON Schema exports of the shared Pydantic contracts, for
non-Python consumers (frontend TypeScript codegen, external API documentation
tooling, contract testing). Spec ref: §6.3 Data Assets Required.

## Regenerating
```bash
pip install -e ../../packages/contracts
python generate_schemas.py
```
This writes one `.schema.json` file per contract, always derived live from
`packages/contracts/*.py` via `Model.model_json_schema()` — **never hand-edit
a `.schema.json` file**; edit the Pydantic model and regenerate instead, so
the exported schema can never drift from the actual runtime contract.

## Files produced
| File | Contract | Covers |
|---|---|---|
| `interaction_event.schema.json` | `InteractionEvent` | what an AI surface sends to `POST /v1/events` |
| `memory.schema.json` | `Memory` | one versioned fact as stored in the graph |
| `extraction_result.schema.json` | `ExtractionResult` | the structured output extraction must return |
| `retrieval_candidate_set.schema.json` | `RetrievalCandidateSet` | bounded candidates before ranking |
| `vector_record.schema.json` | `VectorRecord` | embedding metadata that makes erasure deterministic |
| `context_package.schema.json` | `ContextPackage` | the bounded package the LLM receives |
| `policy_decision.schema.json` | `PolicyDecision` | an allow/deny outcome with its reason codes |
| `feedback_event.schema.json` | `FeedbackEvent` | user or reviewer signal |
| `trace.schema.json` | `Trace` | the redacted decision trail for one request |

## Keeping these honest
`tests/contract/test_schema_backward_compatibility.py` regenerates each schema
in memory and compares it to the committed file. If you change a Pydantic model
and forget to regenerate, the test fails and names the file. That is also what
stops anyone hand-editing a `.schema.json`.

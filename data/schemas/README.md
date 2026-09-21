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
`interaction_event.schema.json`, `memory.schema.json`,
`extraction_result.schema.json`, `context_package.schema.json`,
`policy_decision.schema.json`, `feedback_event.schema.json`, `trace.schema.json`

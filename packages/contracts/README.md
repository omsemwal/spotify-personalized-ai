# packages/contracts

**What this is:** The single shared set of typed Pydantic schemas for every event,
memory fact, extraction output, context package, policy decision, feedback record,
trace, and MCP tool input/output in the system.

**Why it exists:** The CTO's requirement from the leadership transcript (§4):
> "Define the event contract, graph schema, retrieval contract, and policy
> boundary now. Product teams should integrate through APIs or MCP tools, not
> direct database queries."

Every other service (`services/*`) imports models from this package. **No service
may define its own duplicate copy of a shared shape** — that recreates exactly the
per-surface schema fragmentation the leadership meeting identified as the core risk
of *not* building this shared layer.

## Files
| File | Contract | Spec ref |
|---|---|---|
| `events.py` | `InteractionEvent` — the versioned event entering via Ingestion API | §5.4 Interaction Capture |
| `memory.py` | `Memory` — a versioned temporal graph fact | §5.4 Temporal Graph Memory Layer |
| `extraction.py` | `ExtractionCandidate` / `ExtractionResult` — structured extractor output | §7.5 |
| `context.py` | `ContextPackage` — the bounded package handed to the LLM | §5.4 Context Composition |
| `policy.py` | `PolicyDecision` — eligibility/retention verdict on one memory | §5.4 User Control, Privacy, Safety |
| `feedback.py` | `FeedbackEvent` — POST /v1/feedback body | §5.4 Experimentation and Quality Review |
| `tracing.py` | `Trace` / `TraceStage` — GET /v1/traces/{trace_id} body | §5.4 Observability and Operations |
| `mcp_tools.py` | Typed input/output for all 5 MCP tools | §5.4 MCP and Tool Interface |

## Versioning
`events.py` carries `SCHEMA_VERSION`. Any breaking change to a contract requires
bumping this and updating `tests/contract/`, per §5.5 Maintainability.

## Install (local dev, editable)
```bash
cd packages/contracts && pip install -e .
```

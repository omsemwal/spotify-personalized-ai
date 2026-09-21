# packages/observability

**What this is:** Shared tracing and redaction utilities used by every service
so a single request can be reconstructed end to end at `GET /v1/traces/{trace_id}`.
Spec ref: §5.4 "Observability and Operations."

## Files
- `tracing.py` — `TraceRecorder`: a context-manager-based stage recorder.
  Each pipeline stage (`intake`, `extraction`, `graph_write`, `embedding_write`,
  `retrieval`, `reranking`, `policy_filter`, `context_injection`, `fallback`)
  wraps its work in `with recorder.stage("name", detail={...}):`.
- `redaction.py` — strips free-text fields (`fact_text`, `payload`, `comment`,
  etc.) from anything written to a trace or log, replacing them with a length
  marker. Identifiers, timestamps, types, and scores are preserved — this is
  what §5.4 means by "preserving identifiers needed for investigation" while
  never logging raw private content.

## Usage
```python
from packages.observability import TraceRecorder
rec = TraceRecorder(subject_id="u_123", surface="music_chat")
with rec.stage("retrieval", detail={"candidate_count": 12}):
    ...
trace_dict = rec.to_trace_dict()  # servable via GET /v1/traces/{trace_id}
```

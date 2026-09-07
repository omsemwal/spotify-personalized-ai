# 👁️ Observability Package

**Folder**: `packages/observability/`  
**Purpose**: Shared Python library providing standardized logging, Prometheus metric counters, and OpenTelemetry trace helpers across all backend microservices.

---

## 📋 What We Do Inside
1. **Structured JSON Logger**:
   - Standardized logger emitting JSON formatted logs with `subject_id`, `trace_id`, and `service_name`.
2. **Prometheus Metrics Helper**:
   - Exposes standardized metric helpers (`counter`, `histogram`) for HTTP latency, Kafka processing lag, and memory operation counts.
3. **OpenTelemetry Tracer Wrapper**:
   - Wraps FastAPI routes and database queries to propagate distributed trace contexts across service boundaries.

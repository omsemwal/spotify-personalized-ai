# API Reference

All 10 required endpoints (§7.3), grouped by owning service. Every request/response
body is validated against `packages/contracts/`.

## Ingestion API (`:8001`)
### `POST /v1/events`
Auth: `Authorization: Bearer <service-token>`
```json
{
  "event_id": "e001", "subject_id": "u_001", "surface": "music_chat",
  "event_type": "statement", "payload": {"text": "I like jazz", "entities": ["jazz"], "explicit": true},
  "locale": "en-US", "timestamp": "2026-06-01T09:00:00Z",
  "consent_state": "granted", "idempotency_key": "idem_001"
}
```
→ `202 Accepted` `{"status":"accepted","event_id":"e001","accepted_by":"...","accepted_at":"..."}`
Errors: `400 malformed`, `400 unsupported_schema_version`, `400 consent_denied`, `409 duplicate_event`, `401 unauthenticated`.

## Memory Processor (`:8006`)
### `POST /v1/memories/extract`
Body: an `InteractionEvent`. → `ExtractionResult` with typed candidates.

### `POST /v1/memories`
Body: `MemoryCreateRequest`. → `201 {"memory_id","status","graph_version"}`. `403 policy_denial` on rejection.

### `PATCH /v1/memories/{memory_id}`
Body: `MemoryCorrectionRequest` (`action: correct|expire|reactivate`). → `200` with old/new memory ids on correction. `409 conflict` on stale `expected_version`.

## Retrieval API (`:8002`)
### `POST /v1/memories/search`
```json
{"subject_id":"u_001","surface":"music_chat","intent":"play something for focus","max_results":5}
```
→ `SearchMemoryOutput` — `results[]` + `fallback_used`.

### `GET /v1/traces/{trace_id}`
→ redacted `Trace` object — stages, durations, `memory_ids_used`, `fallback_used`.

## Context Composer (`:8003`)
### `POST /v1/context/compose`
```json
{"subject_id":"u_001","surface":"music_chat","intent":"play something for focus","token_budget":400}
```
→ `ContextPackage` — bounded `items[]`, or `fallback_used=true` with a reason.

### `POST /v1/feedback`
Body: `FeedbackEvent`. → `202 {"status":"recorded","trace_id":"..."}`.

## Deletion Orchestrator (`:8004`)
### `DELETE /v1/memories/{memory_id}`
→ `202 {"job_id":"del_...","status":"in_progress"}`.

### `GET /v1/deletions/{job_id}`
→ per-store status: `{"job_id","memory_id","status","stores":{"graph":"completed","vector":"completed","cache":"completed","operational_store":"completed","backup_policy":"scheduled"},"started_at","completed_at"}`.

## Error code conventions (§7.3)
Stable codes across all services: `malformed`, `unauthenticated`, `policy_denial`,
`conflict`, `dependency_timeout`, `retryable_service_failure`, `not_found`,
`unsupported_schema_version`, `consent_denied`, `duplicate_event`.

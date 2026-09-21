# services/ingestion-api

**What this is:** The single entry point for every eligible interaction event
(`POST /v1/events`, §7.3 endpoint #1). It is the only place events are
authenticated, validated, and idempotency-checked before entering the async
processing pipeline.

## Request flow (§7.3 shared rules)
1. **Service auth** (`auth.py`) — validates a bearer service token; rejects
   `unauthenticated` before touching the body.
2. **Schema validation** — parses the body as `packages.contracts.InteractionEvent`,
   the one shared contract (never a locally-redefined model).
3. **Schema-version check** — rejects `unsupported_schema_version` if the caller
   is on an old contract version.
4. **Consent check** — `consent_state == "denied"` is rejected immediately.
5. **Idempotency check** (`idempotency_adapter.py`) — duplicate `idempotency_key`
   → `409 duplicate_event`, never a silent double-write.
6. **Publish** (`queue_adapter.py`) — pushes to Kafka/Redpanda; the HTTP response
   returns `202 Accepted` immediately. Graph/vector writes happen later in
   `services/memory-processor` and never block this request (§6.1 step 1).

## Dependencies are required, not optional
`queue_adapter.py` and `idempotency_adapter.py` connect when they are
constructed, and raise if they cannot. The service does not start without Redis
and the broker.

They used to fall back to an in-process queue and dictionary. That produced a
service returning `202 Accepted` for events it was dropping on the next
restart, and duplicate detection that silently stopped working as soon as a
second replica existed — with a green health check throughout.

Start the datastores first:

```bash
./scripts/dev.sh up
```

## Run locally
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

## Auth (pilot)
Send `Authorization: Bearer dev-ingestion-token` (see `auth.py` — swap for real
workload-identity verification before production).

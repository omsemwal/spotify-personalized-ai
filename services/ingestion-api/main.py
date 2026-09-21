"""
Ingestion API — POST /v1/events (§7.3 endpoint #1).

Validates service identity, subject scope, consent, schema version, and
idempotency, then publishes accepted events to the durable queue. The caller
never waits on graph processing — that happens asynchronously in
services/memory-processor. Spec ref: §5.4 Interaction Capture, §6.1 step 1.
"""
import os
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root))
sys.path.insert(0, str(_repo_root / "packages" / "graph-schema"))
sys.path.insert(0, str(_repo_root / "packages" / "policy-engine"))

from datetime import datetime

from auth import verify_service_token
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from idempotency_adapter import IdempotencyAdapter
from pydantic import ValidationError
from queue_adapter import QueueAdapter

from packages.contracts import SCHEMA_VERSION, InteractionEvent

app = FastAPI(
    title="Spotify Memory System — Ingestion API",
    description="Validates and queues eligible interaction events (§7.3 POST /v1/events).",
    version="1.0.0",
)

# Browser product surfaces (apps/memory-controls, apps/memory-console) call these
# APIs directly from the page. Without this the browser blocks every request under
# its same-origin rule. Narrow CORS_ALLOW_ORIGINS before any non-pilot deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:3001,null"
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

idempotency = IdempotencyAdapter()
queue = QueueAdapter()


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ingestion-api", "local_mode": queue.local_mode}


@app.post("/v1/events", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(raw_event: dict, service_name: str = Depends(verify_service_token)):
    # 1. Schema validation against the SHARED contract (fixes the earlier bug of
    #    each service defining its own duplicate event model).
    try:
        event = InteractionEvent(**raw_event)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "error_code": "malformed", "message": str(e)
        }) from e

    # 2. Schema-version compatibility check.
    if event.schema_version != SCHEMA_VERSION:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "error_code": "unsupported_schema_version",
            "message": f"expected {SCHEMA_VERSION}, got {event.schema_version}",
        })

    # 3. Consent check — denied consent is rejected before it ever reaches the queue.
    if event.consent_state == "denied":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={
            "error_code": "consent_denied", "message": "Subject consent denied for event ingestion"
        })

    # 4. Idempotency check.
    if idempotency.seen(event.idempotency_key):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={
            "error_code": "duplicate_event", "message": "idempotency_key already processed"
        })
    idempotency.mark_seen(event.idempotency_key)

    # 5. Publish — async, does not block on downstream graph/vector writes.
    queue.publish(event.model_dump(mode="json"))

    return {
        "status": "accepted",
        "event_id": event.event_id,
        "accepted_by": service_name,
        "accepted_at": datetime.utcnow().isoformat(),
    }

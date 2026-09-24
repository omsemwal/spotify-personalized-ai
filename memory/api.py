"""All ten API endpoints, on one app and one port.

Endpoints that are still stubs accept a request and return a placeholder.
The real logic gets filled in one endpoint at a time.

Every endpoint except /health requires a bearer token (abc.md:162: "Every
read and write must bind to authenticated subject and service identities").
"""

import uuid

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from memory import cache, db, entities as entity_resolver, errors, extraction, graph, model_client, policy
from memory.auth import Caller, authenticate, bind_subject
from memory.models import (
    SUPPORTED_SCHEMA_VERSION,
    Event,
    EventAccepted,
    ExtractRequest,
    ExtractionResult,
    CreateMemoryRequest,
    MemoryCreated,
)

app = FastAPI(
    title="Spotify Personalized AI Memory System",
    version="0.1.0",
)

# abc.md:322 - a tracking number on every request, a stable code on every
# error.
app.middleware("http")(errors.add_correlation_id)
app.add_exception_handler(RequestValidationError, errors.handle_validation_error)
app.add_exception_handler(StarletteHTTPException, errors.handle_http_error)


@app.get("/health")
def health():
    """Is the app alive? Public on purpose - no data is exposed."""
    return {"status": "ok"}


@app.get("/metrics")
def metrics(caller: Caller = Depends(authenticate)):
    """Operational numbers for the Overview screen.

    abc.md:143 - monitor ingestion lag, write failures and policy
    rejection rate. abc.md:339 - the console Overview shows service
    health, ingestion lag and quality metrics.

    Counts only. No subject ids, no event content - this is an
    operational view, not a window into anyone's data.
    """
    return db.ingestion_metrics()


# --- Write path -----------------------------------------------------------

@app.post("/v1/events", response_model=EventAccepted)
def create_event(
    event: Event,
    background: BackgroundTasks,
    caller: Caller = Depends(authenticate),
):
    """1. Accept an eligible interaction event.

    Validates subject, consent, schema, idempotency and source
    (abc.md:303), and rejects malformed, unauthenticated, out-of-policy and
    unsupported-version events before anything is stored (abc.md:110).
    """
    # The token must be authorized for the subject named in the body.
    bind_subject(caller, event.subject_id)

    def deny(status: int, code: str, message: str) -> HTTPException:
        """Refuse the event, and write down why.

        Written inline, not as a background task: raising an exception
        replaces the response, and background tasks attached to a response
        that never gets sent are discarded. A rejection is cheap and rare,
        so waiting for one small insert is fine.
        """
        db.record_audit(
            action="event.rejected",
            subject_id=event.subject_id,
            service_id=caller.service_id,
            outcome="rejected",
            correlation_id=errors.correlation_id.get(),
            reason=code,
        )
        return HTTPException(status_code=status, detail=errors.error(code, message))

    # One caller must not be able to flood us (abc.md:356).
    if cache.is_rate_limited(event.subject_id):
        raise deny(
            429,
            errors.RATE_LIMITED,
            f"more than {cache.RATE_LIMIT_PER_MINUTE} events in one minute",
        )

    # Unsupported contract versions are rejected before anything else.
    if event.schema_version != SUPPORTED_SCHEMA_VERSION:
        raise deny(
            400,
            errors.UNSUPPORTED_SCHEMA_VERSION,
            f"schema_version {event.schema_version} is not supported; "
            f"this service accepts {SUPPORTED_SCHEMA_VERSION}",
        )

    # Consent: we check OUR record, not what the caller claims.
    #
    # abc.md:187 - the ingestion API "verifies ... consent state". The
    # event carries the surface's belief (abc.md:108); the database says
    # what is actually true. If they disagree, the database wins.
    consent = db.get_consent(event.subject_id)

    if consent is None:
        # No record at all. We do not assume permission we never got.
        raise deny(403, errors.CONSENT_DENIED, "no consent record for this subject")

    if consent != "granted":
        raise deny(403, errors.CONSENT_DENIED, f"consent is {consent}")

    # Same key sent twice by the same subject: return the first event_id
    # and store nothing new. Kept in Redis so it expires after 24 hours
    # (abc.md:222) instead of growing forever.
    seen = cache.get_event_id(event.subject_id, event.idempotency_key)
    if seen is not None:
        background.add_task(
            db.record_audit,
            action="event.duplicate",
            subject_id=event.subject_id,
            service_id=caller.service_id,
            outcome="duplicate",
            correlation_id=errors.correlation_id.get(),
            event_id=seen,
        )
        return EventAccepted(event_id=seen, duplicate=True)

    event_id = f"evt_{uuid.uuid4().hex[:12]}"

    # Postgres first, then Redis. In that order a crash in between means a
    # stored event whose key is forgotten - a retry writes a second row,
    # which is recoverable. The other order would lose the event entirely.
    db.save_event(event_id, event.model_dump(mode="json"), caller.service_id)
    cache.remember(event.subject_id, event.idempotency_key, event_id)

    # The audit line is written after the reply is sent, so the caller does
    # not wait for it (abc.md:324 - "Keep the user path independent of
    # downstream graph-write latency").
    background.add_task(
        db.record_audit,
        action="event.accepted",
        subject_id=event.subject_id,
        service_id=caller.service_id,
        outcome="accepted",
        correlation_id=errors.correlation_id.get(),
        event_id=event_id,
    )

    return EventAccepted(event_id=event_id)


@app.post("/v1/memories/extract", response_model=ExtractionResult)
def extract_memories(
    request: ExtractRequest,
    background: BackgroundTasks,
    caller: Caller = Depends(authenticate),
):
    """2. Turn an approved event into typed candidate memories.

    abc.md:304 - "Convert an approved event into typed candidate memories
    for deterministic validation."

    The model reads the language; memory/extraction.py decides what is
    acceptable (abc.md:296 - never treat extraction as authoritative).
    """
    bind_subject(caller, request.subject_id)

    def deny(status: int, code: str, message: str) -> HTTPException:
        db.record_audit(
            action="extract.rejected",
            subject_id=request.subject_id,
            service_id=caller.service_id,
            outcome="rejected",
            correlation_id=errors.correlation_id.get(),
            reason=code,
            event_id=request.event_id,
        )
        return HTTPException(status_code=status, detail=errors.error(code, message))

    if cache.is_rate_limited(request.subject_id):
        raise deny(429, errors.RATE_LIMITED, "too many requests this minute")

    # Consent can change between capture and extraction, so it is checked
    # again here - abc.md:53 wants it enforced "before memory reaches
    # retrieval", not only at the door.
    consent = db.get_consent(request.subject_id)
    if consent != "granted":
        raise deny(403, errors.CONSENT_DENIED, f"consent is {consent}")

    # Subject-scoped read: knowing an event id is not enough (abc.md:110).
    event = db.get_event(request.event_id, request.subject_id)
    if event is None:
        raise deny(404, errors.NOT_FOUND, "no such event for this subject")

    try:
        proposals = model_client.propose_candidates(event)
    except model_client.ModelUnavailable as exc:
        # abc.md:158 - the experience degrades gracefully rather than
        # failing. No memory is invented when the model cannot be reached.
        raise deny(503, errors.SERVICE_UNAVAILABLE, str(exc)) from exc

    result = extraction.extract(event, proposals)

    background.add_task(
        db.record_audit,
        action="extract.completed",
        subject_id=request.subject_id,
        service_id=caller.service_id,
        outcome="no_memory" if result.no_memory else "extracted",
        correlation_id=errors.correlation_id.get(),
        event_id=request.event_id,
    )

    return result


@app.post("/v1/memories", response_model=MemoryCreated)
def create_memory(
    request: CreateMemoryRequest,
    background: BackgroundTasks,
    caller: Caller = Depends(authenticate),
):
    """3. Create an explicit or approved memory, and store it in the graph.

    abc.md:306 - "Create an explicit or approved memory and return stable
    ID, graph version, and policy state."
    """
    bind_subject(caller, request.subject_id)

    # Refuse and record why.
    def deny(status: int, code: str, message: str) -> HTTPException:
        db.record_audit(
            action="memory.rejected",
            subject_id=request.subject_id,
            service_id=caller.service_id,
            outcome="rejected",
            correlation_id=errors.correlation_id.get(),
            reason=code,
        )
        return HTTPException(status_code=status, detail=errors.error(code, message))

    if cache.is_rate_limited(request.subject_id):
        raise deny(429, errors.RATE_LIMITED, "too many requests this minute")

    consent = db.get_consent(request.subject_id)
    if consent != "granted":
        raise deny(403, errors.CONSENT_DENIED, f"consent is {consent}")

    # The same sensitivity rule as extraction. A memory written directly
    # through this endpoint must not bypass abc.md:53.
    if extraction.looks_sensitive(request.fact):
        raise deny(403, errors.CONSENT_DENIED, "sensitive inference is not storable")

    # Resolve names to catalog ids (abc.md:113) and stamp the policy class
    # from the registry (abc.md:115). Neither is taken from the caller.
    resolved = entity_resolver.resolve_all(request.entities)
    policy_class = policy.classify(request.memory_type)

    candidate = {
        "memory_type": request.memory_type,
        "fact": request.fact,
        "confidence": request.confidence,
        "entities": [e.model_dump() for e in resolved],
        "policy": policy_class.model_dump(mode="json"),
        "source_event_ids": request.source_event_ids,
        "evidence_count": max(1, len(request.source_event_ids)),
    }

    if request.supersedes:
        # abc.md:118 - close the old fact, keep it as history.
        existing = graph.get_memory(request.supersedes, request.subject_id)
        if existing is None:
            raise deny(404, errors.NOT_FOUND, "no such memory for this subject")
        created = graph.supersede(request.supersedes, request.subject_id, candidate)
    else:
        created = graph.create_memory(request.subject_id, candidate)

    background.add_task(
        db.record_audit,
        action="memory.created",
        subject_id=request.subject_id,
        service_id=caller.service_id,
        outcome="created",
        correlation_id=errors.correlation_id.get(),
        memory_id=created["memory_id"],
    )

    return MemoryCreated(
        memory_id=created["memory_id"],
        graph_version=created["graph_version"],
        policy_state=policy_class.sensitivity,
        superseded=created.get("superseded"),
    )


# --- Read path ------------------------------------------------------------

@app.post("/v1/memories/search")
def search_memories(body: dict, caller: Caller = Depends(authenticate)):
    """4. Return ranked, subject-scoped memories for the current intent."""
    return {"results": [], "trace_id": "trc_stub"}


@app.post("/v1/context/compose")
def compose_context(body: dict, caller: Caller = Depends(authenticate)):
    """5. Apply policy and build the context package for the AI orchestrator."""
    return {"context": "", "included": [], "trace_id": "trc_stub"}


# --- Correction and deletion ---------------------------------------------

@app.patch("/v1/memories/{memory_id}")
def update_memory(
    memory_id: str, body: dict, caller: Caller = Depends(authenticate)
):
    """6. Correct, supersede, or expire an eligible memory."""
    return {"memory_id": memory_id, "graph_version": 2, "superseded": True}


@app.delete("/v1/memories/{memory_id}")
def delete_memory(memory_id: str, caller: Caller = Depends(authenticate)):
    """7. Start cross-store deletion and return a traceable job id."""
    return {"job_id": "job_stub", "memory_id": memory_id, "status": "accepted"}


@app.get("/v1/deletions/{job_id}")
def get_deletion(job_id: str, caller: Caller = Depends(authenticate)):
    """8. Report deletion status across every store."""
    return {
        "job_id": job_id,
        "status": "pending",
        "stores": {"graph": "pending", "vector": "pending", "cache": "pending"},
    }


# --- Feedback and explainability -----------------------------------------

@app.post("/v1/feedback")
def create_feedback(body: dict, caller: Caller = Depends(authenticate)):
    """9. Record relevance, correction, or rejection feedback."""
    return {"feedback_id": "fbk_stub", "recorded": True}


@app.get("/v1/traces/{trace_id}")
def get_trace(trace_id: str, caller: Caller = Depends(authenticate)):
    """10. Return the retrieval and policy decisions behind a response."""
    return {"trace_id": trace_id, "decisions": [], "redacted": True}

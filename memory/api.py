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

from memory import (
    cache,
    composer,
    db,
    deletion,
    feedback as feedback_service,
    embeddings,
    entities as entity_resolver,
    errors,
    extraction,
    graph,
    model_client,
    policy,
    queue,
    trace as trace_service,
    retrieval,
)
from memory.auth import Caller, authenticate, bind_subject
from memory.models import (
    SUPPORTED_SCHEMA_VERSION,
    Event,
    EventAccepted,
    ExtractRequest,
    ExtractionResult,
    CreateMemoryRequest,
    MemoryCreated,
    SearchRequest,
    SearchResult,
    ComposeRequest,
    ContextPackage,
    PatchMemoryRequest,
    MemoryUpdated,
    DeletionAccepted,
    DeletionStatus,
    FeedbackRequest,
    FeedbackRecorded,
    TraceRecord,
    TraceDecision,
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

    # abc.md:187 - "Accepted events enter a durable queue so graph
    # processing does not block the experience." The memory processor
    # picks it up from there; the listener does not wait for any of it.
    background.add_task(
        queue.publish,
        event_id,
        event.subject_id,
        errors.correlation_id.get(),
    )

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
        # The caller named the memory this replaces. abc.md:118 - close the
        # old fact, keep it as history.
        existing = graph.get_memory(request.supersedes, request.subject_id)
        if existing is None:
            raise deny(404, errors.NOT_FOUND, "no such memory for this subject")
        created = graph.supersede(request.supersedes, request.subject_id, candidate)

    else:
        # Nobody told us about a clash, so look for one ourselves.
        # abc.md:189 - "Contradictions close or supersede prior facts
        # instead of silently replacing history."
        entity_ids = [e.entity_id for e in resolved if e.entity_id]
        related = graph.find_about(request.subject_id, entity_ids)

        contradicted = next(
            (m for m in related
             if graph.contradicts(request.memory_type, m["memory_type"])),
            None,
        )
        same = next(
            (m for m in related if m["memory_type"] == request.memory_type),
            None,
        )

        if contradicted is not None:
            # "I don't want country" arriving after "I love country".
            created = graph.supersede(
                contradicted["memory_id"], request.subject_id, candidate
            )
        elif same is not None:
            # The same thing said again. abc.md:49 - repeated evidence
            # strengthens one memory rather than making a second.
            created = graph.strengthen(
                same["memory_id"], request.subject_id,
                request.source_event_ids, request.confidence,
            )
        else:
            created = graph.create_memory(request.subject_id, candidate)

    # abc.md:190 step 10 - embed the memory under the same id, right after
    # it is written. Done in the background so the caller does not wait for
    # the model to run.
    background.add_task(
        embeddings.store_for_memory,
        created["memory_id"],
        request.subject_id,
        request.fact,
    )

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

@app.post("/v1/memories/search", response_model=SearchResult)
def search_memories(
    request: SearchRequest,
    background: BackgroundTasks,
    caller: Caller = Depends(authenticate),
):
    """4. Return ranked, subject-scoped memories for the current intent.

    abc.md:309 - ranked for intent, surface, locale and token budget.
    Hybrid candidates (abc.md:123), reranked on seven signals
    (abc.md:124), then diversity and policy filters (abc.md:125, :192).
    """
    bind_subject(caller, request.subject_id)

    # Refuse and record why.
    def deny(status: int, code: str, message: str) -> HTTPException:
        db.record_audit(
            action="search.rejected",
            subject_id=request.subject_id,
            service_id=caller.service_id,
            outcome="rejected",
            correlation_id=errors.correlation_id.get(),
            reason=code,
        )
        return HTTPException(status_code=status, detail=errors.error(code, message))

    if cache.is_rate_limited(request.subject_id):
        raise deny(429, errors.RATE_LIMITED, "too many requests this minute")

    # abc.md:53 - consent is enforced "before memory reaches retrieval".
    # This is that point.
    consent = db.get_consent(request.subject_id)
    if consent != "granted":
        raise deny(403, errors.CONSENT_DENIED, f"consent is {consent}")

    # Anything the listener marked unhelpful counts against a memory
    # (abc.md:124, negative feedback).
    negative = db.negative_feedback(request.subject_id)

    found = retrieval.search(
        subject_id=request.subject_id,
        intent=request.intent,
        surface=request.surface,
        limit=request.limit,
        negative=negative,
    )

    # abc.md:322 - every response links to a trace. The correlation id is
    # that link, and it is already on the response header.
    trace_id = errors.correlation_id.get()

    # abc.md:101 - the trace has to be replayable, so the decisions are
    # written down as they are taken.
    background.add_task(
        trace_service.record_search,
        trace_id, request.subject_id, found["results"], found["removed"],
    )

    background.add_task(
        db.record_audit,
        action="search.completed",
        subject_id=request.subject_id,
        service_id=caller.service_id,
        outcome="found" if found["results"] else "empty",
        correlation_id=trace_id,
    )

    return SearchResult(**found, trace_id=trace_id)


@app.post("/v1/context/compose", response_model=ContextPackage)
def compose_context(
    request: ComposeRequest,
    background: BackgroundTasks,
    caller: Caller = Depends(authenticate),
):
    """5. Apply policy and build the context package for the AI orchestrator.

    abc.md:311 - the last step before a listener sees anything. Finds the
    relevant memories, drops what must not be used, fits the budget, and
    hands back a package whose memory text is fenced as data
    (abc.md:134).
    """
    bind_subject(caller, request.subject_id)
    trace_id = errors.correlation_id.get()

    # Refuse and record why.
    def deny(status: int, code: str, message: str) -> HTTPException:
        db.record_audit(
            action="compose.rejected",
            subject_id=request.subject_id,
            service_id=caller.service_id,
            outcome="rejected",
            correlation_id=trace_id,
            reason=code,
        )
        return HTTPException(status_code=status, detail=errors.error(code, message))

    if cache.is_rate_limited(request.subject_id):
        raise deny(429, errors.RATE_LIMITED, "too many requests this minute")

    # abc.md:53 - consent is enforced before memory reaches retrieval.
    # A paused listener gets the no-memory package, not an error: the
    # experience must carry on without memory (abc.md:158).
    consent = db.get_consent(request.subject_id)
    if consent != "granted":
        package = composer.compose([], request.surface, request.token_budget,
                                   trace_id, healthy=False)
        package.reason = f"consent is {consent}"
        return package

    found = retrieval.search(
        subject_id=request.subject_id,
        intent=request.intent,
        surface=request.surface,
        limit=request.token_budget // 50,   # a rough ceiling; the budget decides
        negative=db.negative_feedback(request.subject_id),
    )

    package = composer.compose(
        memories=found["results"],
        surface=request.surface,
        token_budget=request.token_budget,
        trace_id=trace_id,
    )
    # Anything retrieval dropped is part of the same story.
    package.removed = found["removed"] + package.removed

    # abc.md:101 - record the decisions so the trace can be replayed.
    background.add_task(
        trace_service.record_search,
        trace_id, request.subject_id, package.items, package.removed,
    )

    # abc.md:135 - "record which memories influenced each response".
    background.add_task(
        db.record_audit,
        action="compose.completed",
        subject_id=request.subject_id,
        service_id=caller.service_id,
        outcome="no_memory" if package.no_memory else "composed",
        correlation_id=trace_id,
        memory_id=",".join(i.memory_id for i in package.items) or None,
    )

    return package


# --- Correction and deletion ---------------------------------------------

@app.patch("/v1/memories/{memory_id}", response_model=MemoryUpdated)
def update_memory(
    memory_id: str,
    request: PatchMemoryRequest,
    background: BackgroundTasks,
    caller: Caller = Depends(authenticate),
):
    """6. Correct, supersede, or expire an eligible memory.

    abc.md:313 - "under optimistic concurrency": the caller says which
    version they last saw, and the request is refused if the memory has
    changed since. Two people editing at once cannot silently overwrite
    each other.
    """
    bind_subject(caller, request.subject_id)
    trace_id = errors.correlation_id.get()

    # Refuse and record why.
    def deny(status: int, code: str, message: str) -> HTTPException:
        db.record_audit(
            action="memory.update_rejected",
            subject_id=request.subject_id,
            service_id=caller.service_id,
            outcome="rejected",
            correlation_id=trace_id,
            reason=code,
            memory_id=memory_id,
        )
        return HTTPException(status_code=status, detail=errors.error(code, message))

    if cache.is_rate_limited(request.subject_id):
        raise deny(429, errors.RATE_LIMITED, "too many requests this minute")

    # Subject-scoped read: a memory id alone is not enough.
    existing = graph.get_memory(memory_id, request.subject_id)
    if existing is None:
        raise deny(404, errors.NOT_FOUND, "no such memory for this subject")

    # abc.md:313 - optimistic concurrency. The memory changed under them.
    if existing["graph_version"] != request.expected_version:
        raise deny(
            409,
            errors.CONFLICT,
            f"memory is at version {existing['graph_version']}, "
            f"not {request.expected_version}",
        )

    if request.operation == "expire":
        updated = graph.expire_one(memory_id, request.subject_id)
        result = MemoryUpdated(
            memory_id=updated["memory_id"],
            graph_version=updated["graph_version"],
            status=updated["status"],
        )

    else:  # correct
        if not (request.fact or "").strip():
            raise deny(422, errors.VALIDATION_FAILED, "a correction needs a fact")

        # The same sensitivity block as everywhere else (abc.md:53).
        if extraction.looks_sensitive(request.fact):
            raise deny(403, errors.CONSENT_DENIED,
                       "sensitive inference is not storable")

        resolved = entity_resolver.resolve_all(request.entities)
        candidate = {
            "memory_type": "correction",
            "fact": request.fact,
            "confidence": request.confidence,
            "entities": [e.model_dump() for e in resolved],
            "policy": policy.classify("correction").model_dump(mode="json"),
            "source_event_ids": existing.get("source_event_ids", []),
            "evidence_count": 1,
        }

        # abc.md:118 - a correction supersedes; it never overwrites.
        created = graph.supersede(memory_id, request.subject_id, candidate)
        background.add_task(
            embeddings.store_for_memory,
            created["memory_id"], request.subject_id, request.fact,
        )
        result = MemoryUpdated(
            memory_id=created["memory_id"],
            graph_version=created["graph_version"],
            status="active",
            superseded=memory_id,
        )

    background.add_task(
        db.record_audit,
        action=f"memory.{request.operation}",
        subject_id=request.subject_id,
        service_id=caller.service_id,
        outcome="updated",
        correlation_id=trace_id,
        memory_id=result.memory_id,
    )
    return result


@app.delete("/v1/memories/{memory_id}", response_model=DeletionAccepted)
def delete_memory(
    memory_id: str,
    subject_id: str,
    background: BackgroundTasks,
    caller: Caller = Depends(authenticate),
):
    """7. Start cross-store deletion and return a traceable job id.

    abc.md:315 - the work happens afterwards; this returns the receipt.
    abc.md:97 - retrieval eligibility is revoked immediately, so the
    memory stops being usable before any store has actually cleared.
    """
    bind_subject(caller, subject_id)
    trace_id = errors.correlation_id.get()

    existing = graph.get_memory(memory_id, subject_id)
    if existing is None:
        db.record_audit(
            action="memory.delete_rejected", subject_id=subject_id,
            service_id=caller.service_id, outcome="rejected",
            correlation_id=trace_id, reason=errors.NOT_FOUND,
            memory_id=memory_id,
        )
        raise HTTPException(
            status_code=404,
            detail=errors.error(errors.NOT_FOUND,
                                "no such memory for this subject"),
        )

    # abc.md:97 - revoke first. Even if a store is slow, the memory is
    # already unusable.
    deletion.revoke_eligibility(memory_id, subject_id)

    job_id = deletion.create_job(subject_id, memory_id)

    # The stores are cleared after the reply. abc.md:322 - asynchronous
    # work returns a job state.
    background.add_task(deletion.run_job, job_id, subject_id, memory_id)

    background.add_task(
        db.record_audit,
        action="memory.deleted",
        subject_id=subject_id,
        service_id=caller.service_id,
        outcome="accepted",
        correlation_id=trace_id,
        memory_id=memory_id,
    )
    return DeletionAccepted(job_id=job_id, memory_id=memory_id)


@app.get("/v1/deletions/{job_id}", response_model=DeletionStatus)
def get_deletion(
    job_id: str, subject_id: str, caller: Caller = Depends(authenticate)
):
    """8. Report deletion status across every store.

    abc.md:317 - "Report graph, vector, cache, operational-store, and
    backup-policy status." One line per store, so a partial failure is
    visible rather than hidden behind a single flag.
    """
    bind_subject(caller, subject_id)

    job = deletion.get_job(job_id, subject_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=errors.error(errors.NOT_FOUND, "no such job for this subject"),
        )

    return DeletionStatus(
        job_id=job["job_id"],
        memory_id=job["memory_id"],
        status=job["status"],
        stores={
            "graph": job["graph_status"],
            "vector": job["vector_status"],
            "cache": job["cache_status"],
            "operational": job["operational_status"],
            "backup": job["backup_status"],
        },
        requested_at=job["requested_at"],
        completed_at=job["completed_at"],
        error=job["error"],
    )


# --- Feedback and explainability -----------------------------------------

@app.post("/v1/feedback", response_model=FeedbackRecorded)
def create_feedback(
    request: FeedbackRequest,
    background: BackgroundTasks,
    caller: Caller = Depends(authenticate),
):
    """9. Record relevance, correction, rejection or experience feedback.

    abc.md:318 - "without self-validating model output". Negative feedback
    always counts; positive feedback counts only for memories the listener
    stated themselves. A thumbs-up on our own guess is not evidence for
    the guess.
    """
    bind_subject(caller, request.subject_id)
    trace_id = errors.correlation_id.get()

    if cache.is_rate_limited(request.subject_id):
        raise HTTPException(
            status_code=429,
            detail=errors.error(errors.RATE_LIMITED,
                                "too many requests this minute"),
        )

    # A memory named in feedback must belong to this subject.
    if request.memory_id and graph.get_memory(
        request.memory_id, request.subject_id
    ) is None:
        raise HTTPException(
            status_code=404,
            detail=errors.error(errors.NOT_FOUND,
                                "no such memory for this subject"),
        )

    result = feedback_service.record(
        subject_id=request.subject_id,
        kind=request.kind,
        sentiment=request.sentiment,
        memory_id=request.memory_id,
        trace_id=request.trace_id or trace_id,
    )

    background.add_task(
        db.record_audit,
        action="feedback.recorded",
        subject_id=request.subject_id,
        service_id=caller.service_id,
        outcome=request.sentiment,
        correlation_id=trace_id,
        memory_id=request.memory_id,
    )
    return FeedbackRecorded(**result)


@app.get("/v1/traces/{trace_id}", response_model=TraceRecord)
def get_trace(
    trace_id: str, subject_id: str, caller: Caller = Depends(authenticate)
):
    """10. Return the retrieval and policy decisions behind a response.

    abc.md:320 - "authorized retrieval and policy decisions with sensitive
    fields redacted." The trace carries memory ids, scores and reasons, so
    a reviewer can see the shape of a decision without reading anybody's
    private memories.
    """
    bind_subject(caller, subject_id)

    decisions = trace_service.get_trace(trace_id, subject_id)
    actions = trace_service.get_audit_for_trace(trace_id, subject_id)

    if not decisions and not actions:
        raise HTTPException(
            status_code=404,
            detail=errors.error(errors.NOT_FOUND,
                                "no such trace for this subject"),
        )

    return TraceRecord(
        trace_id=trace_id,
        decisions=[TraceDecision(**d) for d in decisions],
        actions=actions,
    )

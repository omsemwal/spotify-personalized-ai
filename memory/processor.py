"""Why this file exists
=====================

abc.md:188 - "Extract and normalize. A memory processor classifies the
              event, extracts candidate facts into a typed schema,
              resolves canonical content and concept entities, and applies
              minimization and sensitivity rules."
abc.md:257 - `memory-processor/` is one of the six services the
              specification lists.

This is the piece that makes the system automatic. Without it, a memory
only appears if somebody calls extract and then memories by hand - which
is fine for a demo and useless in production.

It reads an event id off the queue, runs the chain that was already built
for endpoints 2 and 3, and stores whatever survives. Nobody copies an id
anywhere: it came off the queue.

The whole chain is:

    event id from the queue
        -> read the event          (subject-scoped)
        -> check consent again     (it may have changed since capture)
        -> ask the model           (endpoint 2's work)
        -> apply our rules         (endpoint 2's work)
        -> store what survives     (endpoint 3's work)

Failures go to the dead-letter topic rather than being retried forever or
dropped (abc.md:144).
"""

import logging

from memory import db, embeddings, extraction, graph, model_client, policy, queue

logger = logging.getLogger("memory.processor")


# Turn one event into stored memories. Returns what happened.
def process_event(event_id: str, subject_id: str) -> dict:
    """The whole chain for a single event.

    Raises ModelUnavailable when the model cannot be reached, so the
    caller can dead-letter the message and try again later. Anything the
    model gets wrong is caught by our rules instead, and simply dropped.
    """
    # Subject-scoped read: the worker has no more privilege than a caller.
    event = db.get_event(event_id, subject_id)
    if event is None:
        return {"stored": 0, "reason": "event not found"}

    # abc.md:53 - consent is enforced before memory is created. It can be
    # withdrawn between capture and processing.
    if db.get_consent(subject_id) != "granted":
        return {"stored": 0, "reason": "consent withdrawn since capture"}

    # An event with no words in it has nothing to classify.
    if not (event.get("content") or "").strip():
        return {"stored": 0, "reason": "no content to classify"}

    proposals = model_client.propose_candidates(event)
    result = extraction.extract(event, proposals)

    if result.no_memory:
        return {"stored": 0, "reason": "no memory worth keeping",
                "rejected": result.rejected}

    stored = []
    for candidate in result.candidates:
        memory = store_candidate(subject_id, candidate, event_id)
        stored.append(memory["memory_id"])

    return {"stored": len(stored), "memory_ids": stored,
            "rejected": result.rejected}


# Write one approved candidate into the graph, the same way endpoint 3 does.
def store_candidate(subject_id: str, candidate, event_id: str) -> dict:
    """Contradiction, evidence and embedding, exactly as endpoint 3.

    The logic lives in graph.py, so the worker and the endpoint cannot
    drift apart - a memory written here is indistinguishable from one
    written through the API.
    """
    payload = {
        "memory_type": candidate.memory_type,
        "fact": candidate.fact,
        "confidence": candidate.confidence,
        "entities": [e.model_dump() for e in candidate.entities],
        "policy": policy.classify(candidate.memory_type).model_dump(mode="json"),
        "source_event_ids": candidate.source_event_ids or [event_id],
        "evidence_count": candidate.evidence_count,
    }

    entity_ids = [e.entity_id for e in candidate.entities if e.entity_id]
    related = graph.find_about(subject_id, entity_ids)

    clash = next(
        (m for m in related if graph.contradicts(candidate.memory_type, m["memory_type"])),
        None,
    )
    same = next(
        (m for m in related if m["memory_type"] == candidate.memory_type), None
    )

    if clash is not None:
        created = graph.supersede(clash["memory_id"], subject_id, payload)
    elif same is not None:
        created = graph.strengthen(
            same["memory_id"], subject_id, payload["source_event_ids"],
            candidate.confidence,
        )
    else:
        created = graph.create_memory(subject_id, payload)

    # abc.md:190 - embed under the same memory id.
    embeddings.store_for_memory(created["memory_id"], subject_id, candidate.fact)
    return created


# Read the queue and process what is on it, until it is empty.
def run_once(max_messages: int = 100) -> dict:
    """One pass over the queue. Used by the worker script and by tests.

    A message is only marked done after it has been processed, so a crash
    means it is picked up again rather than lost.
    """
    consumer = queue.consumer()
    handled, failed, memories = 0, 0, 0

    try:
        for message in consumer:
            body = message.value
            try:
                outcome = process_event(body["event_id"], body["subject_id"])
                memories += outcome.get("stored", 0)
                handled += 1

                db.record_audit(
                    action="processor.completed",
                    subject_id=body["subject_id"],
                    service_id="memory-processor",
                    outcome="stored" if outcome.get("stored") else "no_memory",
                    correlation_id=body.get("correlation_id", ""),
                    event_id=body["event_id"],
                )
            except Exception as exc:  # noqa: BLE001 - one bad event must not stop the rest
                logger.exception("event_id=%s failed", body.get("event_id"))
                queue.publish_dead_letter(body, f"{type(exc).__name__}: {exc}")
                failed += 1

            # Mark done only now, after the work actually happened.
            consumer.commit()

            if handled + failed >= max_messages:
                break
    finally:
        consumer.close()

    return {"handled": handled, "failed": failed, "memories_stored": memories}

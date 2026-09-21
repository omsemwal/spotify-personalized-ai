"""
Kafka consumer that closes the asynchronous capture loop (§6.1 steps 1-3):
ingestion-api publishes an accepted event to the durable queue, and this
consumer classifies it, applies the policy gate, and writes time-bounded facts
to the temporal graph — so the user path is never blocked by graph-write
latency (§5.4 "Interaction capture must be asynchronous").

Runs in a daemon thread started by main.py. When LOCAL_MODE=true, or the broker
is unreachable, the consumer simply does not start: the service still serves its
three synchronous APIs, matching the fail-open posture in §5.5 Reliability.
"""
import json
import logging
import os
import threading
from datetime import UTC, datetime

from classifier import extract_candidates
from engine import PolicyContext, PolicyEngine

from packages.contracts import InteractionEvent, Memory

log = logging.getLogger("memory-processor.consumer")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_INTERACTION_EVENTS_TOPIC", "interaction-events")
CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "memory-processor")

_policy_engine = PolicyEngine()


def process_event(event: InteractionEvent, store) -> list[str]:
    """Classify one event into candidates and write the approved ones. Returns
    the memory_ids written. Candidate IDs are deterministic (see classifier),
    so replaying the same event upserts rather than duplicates — the idempotent
    replay requirement in §5.4 Observability and Operations."""
    written: list[str] = []
    ctx = PolicyContext(
        consent_state=event.consent_state,
        surface_policy=["continuity", "personalization", "correction"],
    )

    for candidate in extract_candidates(event):
        if candidate.decision != "accept":
            continue

        allowed, codes = _policy_engine.evaluate_write(candidate.memory_type, ctx)
        if not allowed:
            log.info("policy denied event=%s type=%s codes=%s",
                     event.event_id, candidate.memory_type, codes)
            continue

        now = datetime.now(UTC)
        memory = Memory(
            memory_id=candidate.memory_id,
            subject_id=event.subject_id,
            fact_text=candidate.normalized_fact,
            memory_type=candidate.memory_type,
            entities=candidate.entities,
            confidence=candidate.confidence,
            policy_class=candidate.policy_class,
            source_event_id=event.event_id,
            valid_from=now,
            recorded_at=now,
            status="active",
            surface=event.surface,
        )
        store.write_memory(memory.model_dump(mode="json"))
        written.append(candidate.memory_id)

    return written


def _consume_loop(store):
    from kafka import KafkaConsumer

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    log.info("consuming topic=%s brokers=%s", KAFKA_TOPIC, KAFKA_BOOTSTRAP_SERVERS)

    for message in consumer:
        try:
            event = InteractionEvent(**message.value)
        except Exception:
            # Malformed payloads are dead-lettered by logging rather than
            # crashing the consumer (§5.4 "dead-letter handling").
            log.exception("dropping malformed event at offset %s", message.offset)
            continue
        try:
            written = process_event(event, store)
            log.info("event=%s wrote=%s", event.event_id, written)
        except Exception:
            log.exception("failed processing event=%s", event.event_id)


def start_consumer(store) -> bool:
    """Start the consumer thread. Returns True if it was started."""
    if os.getenv("LOCAL_MODE", "true").lower() == "true":
        log.info("LOCAL_MODE=true — queue consumer not started")
        return False
    try:
        from kafka import KafkaConsumer  # noqa: F401  (import check before threading)
    except ImportError:
        log.warning("kafka client not installed — queue consumer not started")
        return False

    thread = threading.Thread(target=_consume_loop, args=(store,), daemon=True)
    thread.start()
    return True

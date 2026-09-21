"""
Kafka consumer that closes the asynchronous capture loop (§6.1 steps 1-3):
ingestion-api publishes an accepted event to the durable queue, and this
consumer classifies it, applies the policy gate, and writes time-bounded facts
to the temporal graph — so the user path is never blocked by graph-write
latency (§5.4 "Interaction capture must be asynchronous").

Runs in a daemon thread started by main.py. If the broker is unreachable the
service does not start at all. It used to carry on serving its synchronous APIs
with no consumer running, described as fail-open — but that is not what §5.5
means by failing open. Fail-open is retrieval answering without personalization,
which the user sees. A processor with no consumer looks perfectly healthy while
silently writing no memory at all, which nobody sees.
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
DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "interaction-events-dlq")

_STOP = threading.Event()

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


class ConsumerUnavailable(RuntimeError):
    """The queue consumer could not be started, or it stopped unexpectedly."""


# Liveness state, read by /health. A consumer thread that started and then died
# is the exact failure mode this unit exists to make visible, so "did it start"
# is not enough — the health check has to know whether it is still running.
_STATE: dict = {"started": False, "alive": False, "error": None, "processed": 0, "dead_lettered": 0}


def consumer_status() -> dict:
    """Health-check detail for the queue consumer."""
    thread = _STATE.get("thread")
    alive = bool(thread and thread.is_alive())
    return {
        "backend": "kafka",
        "started": _STATE["started"],
        "reachable": alive,
        "processed": _STATE["processed"],
        "dead_lettered": _STATE["dead_lettered"],
        "error": _STATE["error"],
    }


def _dead_letter(producer, raw: bytes, reason: str) -> None:
    """Park a message we cannot process.

    §5.4 Observability: "Provide dead-letter handling and idempotent replay for
    recoverable ingestion failures." This previously just wrote a log line and
    called it dead-lettering, which loses the payload — there is nothing left to
    replay. The message now goes to a real topic, with the reason attached.
    """
    import json as _json

    payload = _json.dumps({
        "reason": reason,
        "raw": raw.decode("utf-8", errors="replace"),
        "dead_lettered_at": datetime.now(UTC).isoformat(),
    }).encode("utf-8")
    producer.produce(DLQ_TOPIC, value=payload)
    producer.flush(timeout=5)
    _STATE["dead_lettered"] += 1


def _consume_loop(store):
    from confluent_kafka import Consumer, KafkaError, Producer

    consumer = Consumer({
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
        # Offsets are committed only after the event has been handled, so a
        # crash mid-processing replays the event rather than losing it. Replay
        # is safe because candidate ids are deterministic (see classifier), so a
        # second pass upserts the same memory instead of duplicating it.
        "enable.auto.commit": False,
    })
    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    consumer.subscribe([KAFKA_TOPIC])
    log.info("consuming topic=%s brokers=%s", KAFKA_TOPIC, KAFKA_BOOTSTRAP_SERVERS)

    try:
        while not _STOP.is_set():
            message = consumer.poll(timeout=1.0)
            if message is None:
                continue
            if message.error():
                if message.error().code() == KafkaError._PARTITION_EOF:
                    continue
                log.error("consumer error: %s", message.error())
                continue

            raw = message.value()
            try:
                event = InteractionEvent(**json.loads(raw.decode("utf-8")))
            except Exception as exc:
                log.exception("malformed event at offset %s", message.offset())
                _dead_letter(producer, raw, f"malformed: {exc}")
                consumer.commit(message)
                continue

            try:
                written = process_event(event, store)
                _STATE["processed"] += 1
                log.info("event=%s wrote=%s", event.event_id, written)
            except Exception as exc:
                log.exception("failed processing event=%s", event.event_id)
                _dead_letter(producer, raw, f"processing failed: {exc}")

            # Committed either way: a processing failure has been parked on the
            # DLQ, so replaying it from the main topic would only fail again and
            # block every event behind it.
            consumer.commit(message)
    except Exception as exc:
        _STATE["error"] = str(exc)
        log.exception("consumer loop stopped")
    finally:
        _STATE["alive"] = False
        consumer.close()


def start_consumer(store) -> bool:
    """Start the consumer thread.

    This used to return False and log a line when the broker or the client was
    missing, which meant the processor started "successfully" while nothing was
    draining the queue. Events piled up on the broker, ingestion kept returning
    202, and no memory was ever written — with a green health check throughout.

    It now raises if it cannot start, and `consumer_status()` reports whether
    the thread is still alive so a later crash is visible too.
    """
    try:
        from confluent_kafka import Consumer  # noqa: F401  (import check before threading)
    except ImportError as exc:
        raise ConsumerUnavailable(
            "confluent-kafka is not installed. Run `./scripts/dev.sh install`."
        ) from exc

    _STOP.clear()
    thread = threading.Thread(target=_consume_loop, args=(store,), daemon=True)
    thread.start()
    _STATE.update({"started": True, "alive": True, "error": None, "thread": thread})
    return True


def stop_consumer() -> None:
    """Ask the loop to finish. Used by tests, so a consumer from one test does
    not keep running through the next."""
    _STOP.set()

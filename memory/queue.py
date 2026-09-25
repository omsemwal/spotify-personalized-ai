"""Why this file exists
=====================

abc.md:187 - "Accepted events enter a durable queue so graph processing
              does not block the experience."
abc.md:207 - Redpanda gives "durable event capture, partitioning, replay,
              backpressure, and consumer isolation."
abc.md:144 - "Provide dead-letter handling and idempotent replay for
              recoverable ingestion failures."

A listener asking for music must never wait while we call a model and
write a graph. So the ingestion API drops the event here and replies
immediately; a worker picks it up afterwards.

The queue is a separate program holding the message on disk. That is the
difference from a background task: a background task lives inside this
process and dies with it. If the server restarts mid-job, a queued message
is still there.

Two topics, already created on this Redpanda:
    interaction-events       accepted events waiting to be processed
    interaction-events-dlq   ones that failed, kept for inspection
"""

import json
import os

from dotenv import load_dotenv

load_dotenv()

# Redpanda's EXTERNAL listener. The internal one on 9092 is advertised as
# `redpanda:9092`, a hostname only other containers can resolve.
BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:19092")

TOPIC = "interaction-events"
DEAD_LETTER_TOPIC = "interaction-events-dlq"

_producer = None


# Open the producer once and reuse it.
def producer():
    global _producer
    if _producer is None:
        from kafka import KafkaProducer

        _producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            # Wait for the broker to confirm. An event we said we accepted
            # must not vanish because the broker had not written it yet.
            acks="all",
            retries=3,
        )
    return _producer


# Close the producer, used on shutdown and by tests.
def close() -> None:
    global _producer
    if _producer is not None:
        _producer.flush()
        _producer.close()
        _producer = None


# Put one accepted event on the queue for the processor to pick up.
def publish(event_id: str, subject_id: str, correlation_id: str = "") -> None:
    """Only identifiers go on the queue, never the event content.

    The worker reads the event from Postgres using the id, so the content
    is never copied into a second place it would have to be deleted from
    (abc.md:145 - redact payloads, keep identifiers).

    Partitioned by subject, so one subject's events are processed in
    order - abc.md:207 lists partitioning as the point of the broker.
    """
    producer().send(
        TOPIC,
        key=subject_id.encode("utf-8"),
        value={
            "event_id": event_id,
            "subject_id": subject_id,
            "correlation_id": correlation_id,
        },
    )


# Put a failed message aside so it can be looked at and replayed.
def publish_dead_letter(message: dict, error: str) -> None:
    """abc.md:144 - dead-letter handling.

    A message that keeps failing must not block everything behind it, and
    must not be silently dropped either.
    """
    producer().send(
        DEAD_LETTER_TOPIC,
        value={**message, "error": error},
    )


# Make a consumer for the processor to read with.
def consumer(group_id: str = "memory-processor", timeout_ms: int = 1000):
    """abc.md:207 - "consumer isolation". The group id is how Redpanda
    knows which messages this worker has already handled, so a restart
    resumes rather than reprocessing everything.
    """
    from kafka import KafkaConsumer

    return KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id=group_id,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        # Start from the beginning the first time this group runs, so no
        # event is missed.
        auto_offset_reset="earliest",
        # Only mark a message done after it has actually been processed.
        enable_auto_commit=False,
        consumer_timeout_ms=timeout_ms,
    )

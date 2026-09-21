"""
Publishes accepted interaction events to the durable queue.

§4, Backend Engineering Lead: "Interaction capture must be asynchronous so the
user path is not blocked by graph writes. A durable queue can absorb events."

The word that matters there is **durable**. This adapter used to fall back to an
in-process `queue.Queue` whenever the broker was unreachable, which produced a
system that looked healthy and returned 202 Accepted while quietly dropping
every event on restart. Accepting an event we cannot actually durably store is
worse than refusing it: the caller believes the memory was captured.

So: no fallback. If the broker is unreachable the service does not start, and if
a publish fails the request fails with a retryable error.
"""

import json
import os

DEFAULT_TOPIC = os.getenv("KAFKA_INTERACTION_EVENTS_TOPIC", "interaction-events")
DEFAULT_DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "interaction-events-dlq")


def _block_ms() -> int:
    """How long a produce call may block. Configurable so tests fail fast."""
    return int(os.getenv("KAFKA_MAX_BLOCK_MS", "5000"))


class QueueUnavailable(RuntimeError):
    """The event broker could not be reached, or a publish failed."""


class QueueAdapter:
    """Kafka/Redpanda producer.

    Constructing it connects. That is deliberate — it means a broken broker is
    discovered at service startup rather than on the first user request.
    """

    def __init__(self, bootstrap_servers: str | None = None, topic: str | None = None):
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"
        )
        self.topic = topic or DEFAULT_TOPIC
        self.dlq_topic = DEFAULT_DLQ_TOPIC

        try:
            from kafka import KafkaProducer
        except ImportError as exc:
            raise QueueUnavailable(
                "the kafka client is not installed. Run `./scripts/dev.sh install`."
            ) from exc

        try:
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                # Wait for the broker to acknowledge from all in-sync replicas.
                # Anything weaker means "durable" is not true.
                acks="all",
                retries=3,
                request_timeout_ms=_block_ms(),
                max_block_ms=_block_ms(),
            )
        except Exception as exc:
            raise QueueUnavailable(
                f"cannot reach the event broker at {self.bootstrap_servers}: {exc}\n"
                "Start it with `./scripts/dev.sh up`. Ingestion will not start without a "
                "durable queue, because accepting events it cannot store would tell callers "
                "their memory was captured when it was not."
            ) from exc

    def publish(self, event: dict) -> None:
        """Publish one event, waiting for the broker to acknowledge it.

        Blocking on the acknowledgement is what lets the API return 202 honestly:
        by the time the caller is told the event was accepted, it is on the
        broker's log. The wait is bounded by `request_timeout_ms`.
        """
        try:
            future = self._producer.send(self.topic, event)
            future.get(timeout=5)
        except Exception as exc:
            raise QueueUnavailable(f"failed publishing to {self.topic}: {exc}") from exc

    def publish_to_dlq(self, event: dict, reason: str) -> None:
        """Park an event that could not be processed.

        §5.4 Observability: "Provide dead-letter handling and idempotent replay
        for recoverable ingestion failures." Kept separate from `publish` so a
        DLQ write can never be mistaken for a successful ingest.
        """
        payload = {"reason": reason, "event": event}
        try:
            self._producer.send(self.dlq_topic, payload).get(timeout=5)
        except Exception as exc:
            raise QueueUnavailable(f"failed publishing to DLQ {self.dlq_topic}: {exc}") from exc

    def status(self) -> dict:
        """Health-check detail. Re-checks rather than reporting the state at
        boot, so a broker that dies later turns the health check red."""
        try:
            self._producer.partitions_for(self.topic)
        except Exception as exc:
            return {"backend": "kafka", "reachable": False, "error": str(exc)}
        return {"backend": "kafka", "reachable": True, "topic": self.topic}

    def close(self) -> None:
        self._producer.close()

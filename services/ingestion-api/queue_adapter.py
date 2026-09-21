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

Client choice
-------------
`confluent-kafka`, not `kafka-python-ng`. The pure-Python client crashes on
Python 3.14 — its selector calls `unregister()` on an already-closed socket and
raises `ValueError: Invalid file descriptor: -1`, which killed the consumer
thread on the first coordinator poll. confluent-kafka wraps librdkafka, which is
the reference implementation and ships a cp314 wheel.
"""

import json
import os

DEFAULT_TOPIC = os.getenv("KAFKA_INTERACTION_EVENTS_TOPIC", "interaction-events")
DEFAULT_DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "interaction-events-dlq")


def _timeout_seconds() -> float:
    """How long a produce call may block. Configurable so tests fail fast."""
    return float(os.getenv("KAFKA_MAX_BLOCK_MS", "5000")) / 1000.0


class QueueUnavailable(RuntimeError):
    """The event broker could not be reached, or a publish failed."""


class QueueAdapter:
    """Kafka/Redpanda producer.

    Constructing it connects and verifies the broker is really there. That is
    deliberate — it means a broken broker is discovered at service startup
    rather than on the first user request.
    """

    def __init__(self, bootstrap_servers: str | None = None, topic: str | None = None):
        self.bootstrap_servers = bootstrap_servers or os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "localhost:19092"
        )
        self.topic = topic or DEFAULT_TOPIC
        self.dlq_topic = DEFAULT_DLQ_TOPIC

        try:
            from confluent_kafka import Producer
        except ImportError as exc:
            raise QueueUnavailable(
                "confluent-kafka is not installed. Run `./scripts/dev.sh install`."
            ) from exc

        timeout = _timeout_seconds()
        self._producer = Producer({
            "bootstrap.servers": self.bootstrap_servers,
            # Wait for all in-sync replicas to acknowledge. Anything weaker
            # means "durable" is not true.
            "acks": "all",
            "enable.idempotence": True,
            "message.timeout.ms": int(timeout * 1000),
            "socket.timeout.ms": int(timeout * 1000),
        })

        # Constructing a librdkafka producer never fails, even with nothing
        # listening — it connects in the background. Ask for metadata so an
        # unreachable broker is discovered here, at startup, rather than on the
        # first user request.
        try:
            self._producer.list_topics(timeout=timeout)
        except Exception as exc:
            raise QueueUnavailable(
                f"cannot reach the event broker at {self.bootstrap_servers}: {exc}\n"
                "Start it with `./scripts/dev.sh up`. Ingestion will not start without a "
                "durable queue, because accepting events it cannot store would tell callers "
                "their memory was captured when it was not."
            ) from exc

    def _send(self, topic: str, payload: dict) -> None:
        """Produce one message and wait for the broker to acknowledge it.

        Blocking on the acknowledgement is what lets the API return 202
        honestly: by the time the caller is told the event was accepted, it is
        on the broker's log.
        """
        errors: list[str] = []

        def _on_delivery(err, _msg):
            if err is not None:
                errors.append(str(err))

        try:
            self._producer.produce(
                topic, value=json.dumps(payload).encode("utf-8"), on_delivery=_on_delivery
            )
            remaining = self._producer.flush(timeout=_timeout_seconds())
        except Exception as exc:
            raise QueueUnavailable(f"failed publishing to {topic}: {exc}") from exc

        if remaining:
            raise QueueUnavailable(
                f"failed publishing to {topic}: {remaining} message(s) not acknowledged "
                "before the timeout"
            )
        if errors:
            raise QueueUnavailable(f"failed publishing to {topic}: {errors[0]}")

    def publish(self, event: dict) -> None:
        """Publish one accepted interaction event."""
        self._send(self.topic, event)

    def publish_to_dlq(self, event: dict, reason: str) -> None:
        """Park an event that could not be processed.

        §5.4 Observability: "Provide dead-letter handling and idempotent replay
        for recoverable ingestion failures." Kept separate from `publish` so a
        DLQ write can never be mistaken for a successful ingest.
        """
        self._send(self.dlq_topic, {"reason": reason, "event": event})

    def status(self) -> dict:
        """Health-check detail. Re-checks rather than reporting the state at
        boot, so a broker that dies later turns the health check red."""
        try:
            metadata = self._producer.list_topics(timeout=_timeout_seconds())
        except Exception as exc:
            return {"backend": "kafka", "reachable": False, "error": str(exc)}
        return {
            "backend": "kafka",
            "reachable": True,
            "topic": self.topic,
            "brokers": len(metadata.brokers),
        }

    def close(self) -> None:
        self._producer.flush(timeout=_timeout_seconds())

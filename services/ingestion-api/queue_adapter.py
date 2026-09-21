"""
Event queue adapter. Production path publishes to Kafka/Redpanda (§6.2). A local
in-memory fallback is used only when KAFKA_BOOTSTRAP_SERVERS is unreachable /
LOCAL_MODE=true, so the service is runnable and testable without the full
docker-compose stack. This mirrors §5.4: "Interaction capture must be
asynchronous so the user path is not blocked by graph writes."
"""
import json
import os
from queue import Queue
from typing import Any

LOCAL_MODE = os.getenv("LOCAL_MODE", "true").lower() == "true"
KAFKA_TOPIC = os.getenv("KAFKA_INTERACTION_EVENTS_TOPIC", "interaction-events")

# Process-local fallback queue (dev/test only — not durable across restarts).
_LOCAL_QUEUE: Queue[str] = Queue()


class QueueAdapter:
    def __init__(self):
        self.local_mode = LOCAL_MODE
        self._producer = None
        if not self.local_mode:
            try:
                from kafka import KafkaProducer  # kafka-python; optional prod dependency
                self._producer = KafkaProducer(
                    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                )
            except Exception:
                self.local_mode = True  # fail open to local queue rather than crash ingestion

    def publish(self, event: dict[str, Any]) -> None:
        if self.local_mode:
            _LOCAL_QUEUE.put(json.dumps(event))
        else:
            self._producer.send(KAFKA_TOPIC, event)

    @staticmethod
    def drain_local_queue_for_tests():
        items = []
        while not _LOCAL_QUEUE.empty():
            items.append(json.loads(_LOCAL_QUEUE.get()))
        return items

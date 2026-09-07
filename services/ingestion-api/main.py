from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import redis
import json
import os

app = FastAPI(
    title="Spotify Memory System - Ingestion API",
    description="Ingests interaction events, validates consent & idempotency, and queues for processing.",
    version="1.0.0"
)

# Environment setup
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
KAFKA_TOPIC = os.getenv("KAFKA_INTERACTION_EVENTS_TOPIC", "interaction-events")

# Connect to Redis for idempotency checks
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

class InteractionEventPayload(BaseModel):
    event_id: str
    subject_id: str
    surface: str
    event_type: str
    payload: dict = {}
    locale: str = "en-US"
    consent_state: str  # 'granted', 'denied', or 'partial'
    idempotency_key: str

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ingestion-api"}

@app.post("/v1/events", status_code=status.HTTP_202_ACCEPTED)
async def ingest_event(event: InteractionEventPayload):
    # 1. Consent check
    if event.consent_state == "denied":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "consent_denied", "message": "User consent denied for event ingestion"}
        )

    # 2. Idempotency check via Redis (TTL 24 hours)
    redis_key = f"idempotency:{event.idempotency_key}"
    if redis_client.exists(redis_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "duplicate_event", "message": "Duplicate idempotency key detected"}
        )
    
    # Store idempotency key with 24 hour expiry
    redis_client.setex(redis_key, 86400, event.event_id)

    # 3. Simulated publish to Kafka event queue
    # (In production, aiokafka producer publishes event.dict() to KAFKA_TOPIC)
    
    return {
        "status": "accepted",
        "event_id": event.event_id,
        "message": f"Event queued to Kafka topic '{KAFKA_TOPIC}'"
    }

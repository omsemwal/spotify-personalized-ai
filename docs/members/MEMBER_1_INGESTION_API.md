# 👤 Member 1 — Ingestion API Task Specification

- **Target Folder**: [`services/ingestion-api/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/ingestion-api/)
- **Primary Goal**: Build the high-throughput, async event ingestion endpoint for incoming user interactions.

---

## 📌 Service Overview
Receives interaction events from AI surfaces (music chat, playlist UI, voice assistant), validates schema and consent state, performs Redis idempotency checks, and pushes events to Kafka.

## 🔗 Shared Contracts
- [`packages/contracts/event_schema.py`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/contracts/event_schema.py) (`InteractionEvent`)

## 📥 Required API Endpoints
- `POST /v1/events`
  - **Input**: `InteractionEvent` payload
  - **Validation Rules**:
    1. Ensure `subject_id` is present.
    2. Reject if `consent_state == "denied"`.
    3. Verify idempotency key in Redis (`idempotency_key`).
  - **Success (202 Accepted)**: Publish event to Kafka topic `interaction-events`.
  - **Failure (400 Bad Request / 403 Forbidden)**: Return error JSON with code (`invalid_schema`, `consent_denied`, `duplicate_event`).

## 📋 Implementation Checklist
- [ ] Set up FastAPI application in `services/ingestion-api/`.
- [ ] Integrate Kafka Producer using `aiokafka` or `confluent-kafka`.
- [ ] Connect Redis client for idempotency checking with configurable TTL.
- [ ] Implement `POST /v1/events` handler with async event dispatch.
- [ ] Add unit tests for valid event, missing consent, duplicate event, and malformed payload.
- [ ] Create `README.md` explaining standalone Docker/local setup.

## 🚫 Constraints
- **NO** direct database writes (Postgres/Neo4j/Qdrant).
- **NO** blocking operations on the main event loop.

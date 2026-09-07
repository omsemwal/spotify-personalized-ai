# 🧪 Tests Directory Guide & Tasks

**Folder**: `tests/`  
**Purpose**: Centralized testing suite ensuring quality, security, contract compliance, and end-to-end system reliability.

---

## 📁 Subdirectory Breakdown & What We Do Inside

### 1. `tests/unit/`
- **What we do**: Unit tests for isolated functions without external database/network calls.
- **Examples**:
  - Validating event payload parsing in `ingestion-api`.
  - Testing token budget calculation math in `context-composer`.
  - Testing confidence scoring formulas in `memory-processor`.

### 2. `tests/integration/`
- **What we do**: Integration tests verifying communication between services and local databases (Redis, Neo4j, Qdrant, Kafka).
- **Examples**:
  - Ingestion API publishing real events to local Kafka topic.
  - Retrieval API querying live Qdrant vector index and Neo4j graph layer.

### 3. `tests/contract/`
- **What we do**: Contract tests ensuring API requests/responses strictly match `packages/contracts/` Pydantic schemas.
- **Examples**:
  - Ensuring `POST /v1/events` schema validation rejects invalid JSON structures.

### 4. `tests/security/`
- **What we do**: Security and privacy compliance testing.
- **Examples**:
  - **Subject Isolation Test**: Verifying user A can NEVER view or retrieve user B's memories.
  - **Prompt Injection Defense**: Testing if malformed memory facts containing malicious instructions alter LLM output.

### 5. `tests/end-to-end/`
- **What we do**: E2E pipeline tests executing the entire workflow from ingestion to response and deletion.
- **Flow**: Event Ingest ➔ Kafka ➔ Memory Processor ➔ Neo4j + Qdrant ➔ Context Composer ➔ LLM Chat ➔ Deletion Orchestrator.

---

## 🚀 How to Run Tests
```bash
pytest tests/unit               # Run fast unit tests
pytest tests/integration        # Run integration tests
pytest tests/security           # Run security & isolation tests
pytest tests/end-to-end         # Run full E2E system tests
```

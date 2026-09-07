# 📋 9-MEMBER TEAM WORK DISTRIBUTION

Here is the exact 1-page work assignment for all **9 Team Members** (1 Lead + 8 Developers).

---

### 👑 Lead (You)
- **Folder**: `packages/contracts/` & Root
- **Goal**: Shared Pydantic data schemas, Docker stack, pipeline architecture, & overall project integration.

---

### 👤 Member 1 — Ingestion API
- **Folder**: `services/ingestion-api/`
- **Goal**: Build `POST /v1/events` endpoint (event validation, Redis idempotency check, push to Kafka).

---

### 👤 Member 2 — Memory Extraction & Processing
- **Folder**: `services/memory-processor/`
- **Goal**: Kafka consumer worker to classify interaction events, extract facts, resolve Spotify entities, and compute confidence scores.

---

### 👤 Member 3 — Temporal Graph Layer (Neo4j)
- **Folder**: `packages/graph-schema/`
- **Goal**: Write Neo4j graph storage & query functions (`write_memory`, `correct_memory`, `expire_memory`, `traverse_related`).

---

### 👤 Member 4 — Embeddings & Vector Search (Qdrant)
- **Folder**: `services/retrieval-api/`
- **Goal**: Embed facts with SentenceTransformers, store vectors in Qdrant, build hybrid graph+vector candidate retriever & reranker (`POST /v1/memories/search`).

---

### 👤 Member 5 — Context Composer & LLM Integration
- **Folder**: `services/context-composer/`
- **Goal**: Package retrieved memories safely into prompts (`POST /v1/context/compose`), enforce token budget, and handle LLM chat responses.

---

### 👤 Member 6 — MCP Tools Server
- **Folder**: `services/memory-mcp-server/`
- **Goal**: Build dedicated FastMCP tool server exposing 5 tools (`search_memory`, `add_preference`, `correct_memory`, `delete_memory`, `explain_memory`).

---

### 👤 Member 7 — Privacy & Deletion Orchestrator
- **Folder**: `services/deletion-orchestrator/` & `packages/policy-engine/`
- **Goal**: Build multi-store deletion engine (`DELETE /v1/memories/{id}`) and consent/isolation policy engine (`check_consent`, `check_subject_isolation`).

---

### 👤 Member 8 — Frontend User Controls & Admin Console
- **Folder**: `apps/memory-controls/` & `apps/memory-console/`
- **Goal**: Build Next.js/React web interfaces (User memory control sidebar + Internal admin console dashboard).

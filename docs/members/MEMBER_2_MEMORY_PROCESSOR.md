# 👤 Member 2 — Memory Extraction & Processing Task Specification

- **Target Folder**: [`services/memory-processor/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/memory-processor/)
- **Primary Goal**: Asynchronous memory extraction pipeline consuming Kafka interaction events.

---

## 📌 Service Overview
Worker service that consumes raw interaction events from Kafka (`interaction-events`), classifies intent/memory type, extracts candidate facts, resolves Spotify entities to canonical IDs, computes confidence scores, and enforces default policy flags before sending candidate memories to the graph store.

## 🔗 Shared Contracts
- [`packages/contracts/event_schema.py`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/contracts/event_schema.py) (`InteractionEvent`)
- [`packages/contracts/memory_schema.py`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/contracts/memory_schema.py) (`Memory`)

## 📥 Components & Interfaces
- **Kafka Consumer Worker**: Background worker consuming `interaction-events` topic.
- **REST Test Endpoint**: `POST /v1/memories/extract` (Takes one event, returns candidate memories synchronously for debugging).

## 📋 Implementation Checklist
- [ ] Build Event Classifier (`episode`, `explicit_preference`, `candidate_preference`, `exclusion`, `correction`, `non_memory`).
- [ ] Build Entity Resolution module (mapping mentions to canonical IDs).
- [ ] Build Confidence Scoring Engine (explicit statements = 0.9+, implicit actions = 0.5-0.7).
- [ ] Implement Policy Class Assigner (mark sensitive inferences like emotional state as `sensitive`/`blocked`).
- [ ] Pass valid memory objects to Member 3's `write_memory()` graph function.
- [ ] Write unit tests for classification, entity lookup, and policy rejection.

## 🚫 Constraints
- **DO NOT** write directly to Neo4j database — invoke Member 3's graph layer functions.
- **DO NOT** auto-approve sensitive inferences.

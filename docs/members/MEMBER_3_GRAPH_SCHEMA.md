# 👤 Member 3 — Temporal Graph Layer (Neo4j) Task Specification

- **Target Folder**: [`packages/graph-schema/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/graph-schema/)
- **Primary Goal**: Temporal graph storage engine in Neo4j with time-bounded facts, full provenance, and strict subject isolation.

---

## 📌 Package Overview
Provides Neo4j storage and graph query functions for time-bounded memory facts. Keeps complete historical lineage by marking corrected facts with `SUPERSEDES` relationships and closing `valid_to` timestamps without destroying raw history.

## 🔗 Shared Contracts
- [`packages/contracts/memory_schema.py`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/contracts/memory_schema.py) (`Memory`)

## 🛠️ Required Exported Python Functions
- `write_memory(memory: Memory) -> str`: Upserts graph node & relationships (`User`, `Memory`, `Entity`). Returns `memory_id`.
- `correct_memory(memory_id: str, new_fact: Memory) -> str`: Closes old memory's `valid_to`, creates new memory node, links via `SUPERSEDES`.
- `expire_memory(memory_id: str) -> bool`: Sets `valid_to = now()`, status = `"expired"`.
- `get_memory_by_id(memory_id: str) -> Optional[Memory]`: Fetches single memory node by ID.
- `traverse_related(subject_id: str, intent_entities: list[str]) -> list[Memory]`: Multi-hop graph traversal for candidate retrieval (must filter by `subject_id`).

## 📋 Implementation Checklist
- [ ] Connect to Neo4j database using official Neo4j Python Driver.
- [ ] Define database constraints and indexes (unique `memory_id`, indexed `subject_id`).
- [ ] Implement `write_memory` using `MERGE` Cypher queries.
- [ ] Implement `correct_memory` Cypher workflow.
- [ ] Implement `traverse_related` with mandatory `subject_id` scoping.
- [ ] Write integration tests verifying write, update, correction lineage, and cross-subject isolation.

## 🚫 Constraints
- **NEVER** perform hard deletion in Cypher (`DETACH DELETE`) during correction — soft expiration/superseding only (Hard deletion is handled by Member 7).
- **NEVER** omit `subject_id` filter in Cypher queries.

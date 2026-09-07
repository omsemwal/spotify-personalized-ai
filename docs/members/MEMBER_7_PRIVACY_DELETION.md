# 👤 Member 7 — Privacy, Deletion Orchestrator & Policy Engine Task Specification

- **Target Folders**: [`services/deletion-orchestrator/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/deletion-orchestrator/) & [`packages/policy-engine/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/policy-engine/)
- **Primary Goal**: Cross-store data deletion engine and shared policy/consent/isolation evaluation package.

---

## 📌 Service & Package Overview
- **Deletion Orchestrator (`services/deletion-orchestrator/`)**: Manages multi-store asynchronous memory deletion workflows across Neo4j graph, Qdrant vector index, Redis caches, and operational Postgres tables.
- **Policy Engine (`packages/policy-engine/`)**: Central policy library for consent validation (`check_consent`), cross-subject isolation (`check_subject_isolation`), and sensitivity classification rules.

## 📥 Required API Endpoints (Deletion Orchestrator)
- `PATCH /v1/memories/{memory_id}`: Supersede / update memory state.
- `DELETE /v1/memories/{memory_id}`: Initiates multi-store deletion job. Returns `job_id`.
- `GET /v1/deletions/{job_id}`: Returns deletion status per storage layer (`graph`, `vector`, `cache`, `postgres`).

## 🛠️ Required Module Exports (Policy Engine)
- `check_consent(subject_id: str, memory_type: str) -> bool`: Verifies active user consent.
- `check_subject_isolation(requester_id: str, target_subject_id: str) -> bool`: Returns `True` iff `requester_id == target_subject_id` (or authorized admin).

## 📋 Implementation Checklist
- [ ] Implement Postgres `deletion_jobs` table tracking status per storage subsystem.
- [ ] Connect Neo4j deletion, Qdrant vector removal (`delete_vector`), and Redis key invalidation.
- [ ] Build retry mechanism for partial deletion failures; job stays `in_progress` until ALL stores confirm.
- [ ] Define policy registry with memory taxonomy, retention limits, and sensitivity defaults.
- [ ] Write integration tests for multi-store deletion completion and subject isolation security checks.

## 🚫 Constraints
- **NEVER** mark a deletion job `completed` if any store (graph, vector, cache) failed or timed out.
- **NEVER** allow bypassing `check_subject_isolation`.

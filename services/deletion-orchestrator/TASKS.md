# 👤 Member 7 — Deletion Orchestrator

**Folder**: `services/deletion-orchestrator/`  
**Assigned To**: Member 7 (Privacy & Deletion Developer)

---

## 🎯 What is this service for? (Simple Words)
When a user asks to delete a memory ("forget my preference for pop music"), this service completely deletes that memory across **ALL databases** (Neo4j graph, Qdrant vector store, Redis cache, and Postgres).

---

## 📥 APIs to Build
- `DELETE /v1/memories/{memory_id}`: Starts deletion job across all databases.
- `GET /v1/deletions/{job_id}`: Checks status of deletion job (`pending`, `in_progress`, `completed`).

---

## 📝 Simple Steps to Complete
1. Create a deletion job entry in Postgres.
2. Call Neo4j delete function.
3. Call Qdrant `delete_vector` function.
4. Clear Redis cache key.
5. Only mark job as `completed` when **all** stores confirm complete removal.

---

## 🧪 How to Test
- Call `DELETE /v1/memories/123` -> verify memory is gone from Neo4j, Qdrant, and Redis!

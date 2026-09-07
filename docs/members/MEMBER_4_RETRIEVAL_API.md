# 👤 Member 4 — Retrieval API & Embeddings Task Specification

- **Target Folder**: [`services/retrieval-api/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/retrieval-api/)
- **Primary Goal**: Vector search index (Qdrant), embedding generation, and hybrid candidate retriever & reranker.

---

## 📌 Service Overview
Generates embeddings for stored memory facts, indexes vectors in Qdrant (or Neo4j vector index), performs hybrid search (combining relational candidates from Member 3's graph and semantic vector candidates from Qdrant), and applies a multi-factor reranking model.

## 🔗 Shared Contracts & Dependencies
- [`packages/contracts/memory_schema.py`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/contracts/memory_schema.py) (`Memory`)
- [`packages/graph-schema/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/graph-schema/) (`traverse_related`)

## 📥 Required API Endpoints
- `POST /v1/memories/search`
  - **Input**: `{ subject_id: str, current_intent_text: str, surface: str, locale: str, token_budget: int }`
  - **Output**: Ranked list of `Memory` objects with relevance scores and candidate sources (`graph`, `vector`, `hybrid`).

## 📋 Implementation Checklist
- [ ] Set up SentenceTransformers (`all-MiniLM-L6-v2` or similar model) for text embeddings.
- [ ] Connect to Qdrant vector database (or Neo4j vector index). Ensure vector IDs map 1:1 to `memory_id`.
- [ ] Implement `delete_vector(memory_id: str)` helper function for Member 7 (Deletion Orchestrator).
- [ ] Build Hybrid Retrieval:
  - Fetch graph candidates via `traverse_related()`.
  - Fetch vector candidates via Qdrant similarity search.
  - Merge & deduplicate by `memory_id`.
- [ ] Build Reranker combining similarity score, explicitness bonus, recency decay, and confidence weight.
- [ ] Filter out expired, superseded, or policy-blocked memories.
- [ ] Write unit & benchmark tests for search relevance and token budget constraint validation.

## 🚫 Constraints
- **NEVER** return superseded (`status == "superseded"`), expired (`status == "expired"`), or policy-blocked memories.
- **NEVER** return candidates belonging to a different `subject_id`.

# 👤 Member 4 — Retrieval API & Embeddings

**Folder**: `services/retrieval-api/`  
**Assigned To**: Member 4 (Retrieval & Search Developer)

---

## 🎯 What is this service for? (Simple Words)
When a user asks a question (like "play something I like for driving"), this service finds the **best matching memories** using Vector Search (Qdrant) + Graph relationships (Neo4j) and ranks them.

---

## 📥 API to Build
- **URL**: `POST /v1/memories/search`
- **Input**: User query text, `subject_id`, and `token_budget`

---

## 📝 Simple Steps to Complete
1. **Generate Vector Embeddings**: Convert memory text into numerical vectors using SentenceTransformers.
2. **Qdrant Vector Store**: Save vectors to Qdrant database using `memory_id`.
3. **Hybrid Search**:
   - Get relational matches from Member 3's Neo4j `traverse_related()`.
   - Get vector matches from Qdrant.
   - Combine both lists.
4. **Rerank & Filter**: Rank memories by relevance, confidence, and freshness. Filter out expired or blocked memories.

---

## 🧪 How to Test
- Send query "workout music" -> ensure memories about "gym playlist" rank at the top!

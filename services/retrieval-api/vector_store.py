"""
Vector index. Production path is Neo4j vector indexes or Qdrant (§6.2). Pilot
ships an in-memory index keyed by the SAME memory_id used in the graph, so
deletion/update stay deterministic and aligned across stores (§5.4
"Embeddings and Retrieval": "store vectors under the same stable memory
identifier used in the graph").
"""
from typing import Dict, List, Tuple

from embeddings import cosine_similarity


class InMemoryVectorStore:
    def __init__(self):
        self._vectors: Dict[str, List[float]] = {}
        self._deleted: set = set()

    def upsert(self, memory_id: str, vector: List[float]) -> None:
        self._vectors[memory_id] = vector
        self._deleted.discard(memory_id)

    def delete(self, memory_id: str) -> None:
        self._vectors.pop(memory_id, None)
        self._deleted.add(memory_id)

    def search(self, query_vector: List[float], candidate_ids: List[str], top_k: int = 10) -> List[Tuple[str, float]]:
        scored = []
        for mid in candidate_ids:
            vec = self._vectors.get(mid)
            if vec is None or mid in self._deleted:
                continue
            scored.append((mid, cosine_similarity(query_vector, vec)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

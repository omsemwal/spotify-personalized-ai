"""
Test double for TemporalGraphStore (packages/graph-schema/graph.py).

This lives under tests/ deliberately. It used to sit in packages/graph-schema
next to the real store, and every service could — and did — fall back to it
whenever Neo4j was unreachable. A test double reachable from production code is
a production dependency, whatever the docstring says.

Nothing outside tests/ imports this module now. Tests inject it explicitly:

    from store_factory import reset_graph_store, set_graph_store
    from tests.doubles.graph_store import InMemoryGraphStore

    set_graph_store(InMemoryGraphStore())
    ...
    reset_graph_store()

It implements the same interface as the real store, so a test written against
it exercises the same calls. It does not implement the same *guarantees* —
there are no constraints, no transactions and no durability — so behaviour that
depends on those (idempotent upserts, uniqueness, subject partitioning) has to
be tested against a live Neo4j instead. Those tests arrive in U7.
"""
from datetime import datetime
from typing import Any


class InMemoryGraphStore:
    def __init__(self):
        self._memories: dict[str, dict[str, Any]] = {}
        self._user_memories: dict[str, list[str]] = {}
        self._entity_memories: dict[str, list[str]] = {}

    def write_memory(self, memory_dict: dict[str, Any]) -> str:
        mid = memory_dict["memory_id"]
        self._memories[mid] = dict(memory_dict)
        self._user_memories.setdefault(memory_dict["subject_id"], [])
        if mid not in self._user_memories[memory_dict["subject_id"]]:
            self._user_memories[memory_dict["subject_id"]].append(mid)
        for entity in memory_dict.get("entities", []):
            self._entity_memories.setdefault(entity, [])
            if mid not in self._entity_memories[entity]:
                self._entity_memories[entity].append(mid)
        return mid

    def correct_memory(self, old_memory_id: str, new_memory_dict: dict[str, Any]) -> str:
        new_id = self.write_memory(new_memory_dict)
        if old_memory_id in self._memories:
            self._memories[old_memory_id]["valid_to"] = datetime.utcnow().isoformat()
            self._memories[old_memory_id]["status"] = "superseded"
        return new_id

    def expire_memory(self, memory_id: str) -> None:
        if memory_id in self._memories:
            self._memories[memory_id]["valid_to"] = datetime.utcnow().isoformat()
            self._memories[memory_id]["status"] = "expired"

    def delete_memory(self, memory_id: str) -> None:
        """Hard delete for cross-store erasure (deletion-orchestrator). Not the
        same as expire — deletion must be irreversible per §5.4 privacy rules."""
        mem = self._memories.pop(memory_id, None)
        if not mem:
            return
        subj_list = self._user_memories.get(mem["subject_id"], [])
        if memory_id in subj_list:
            subj_list.remove(memory_id)
        for entity in mem.get("entities", []):
            ent_list = self._entity_memories.get(entity, [])
            if memory_id in ent_list:
                ent_list.remove(memory_id)

    def traverse_related(self, subject_id: str, intent_entities: list[str]) -> list[dict[str, Any]]:
        """Subject-scoped traversal — never crosses subject_id boundaries (§5.4 subject isolation)."""
        candidate_ids = set(self._user_memories.get(subject_id, []))
        if intent_entities:
            entity_ids = set()
            for e in intent_entities:
                entity_ids |= set(self._entity_memories.get(e, []))
            candidate_ids &= entity_ids
        results = []
        for mid in candidate_ids:
            mem = self._memories.get(mid)
            if mem and mem.get("status") == "active":
                results.append(mem)
        return results

    def set_embedding(self, memory_id: str, vector: list[float]) -> None:
        """Kept in parity with TemporalGraphStore so retrieval behaves the same
        in local mode."""
        if memory_id in self._memories:
            self._memories[memory_id]["embedding"] = vector

    def vector_search(self, subject_id: str, query_vector: list[float], top_k: int = 20):
        from math import sqrt
        def cos(a, b):
            if not a or not b:
                return 0.0
            dot = sum(x*y for x, y in zip(a, b, strict=False))
            na = sqrt(sum(x*x for x in a)) or 1.0
            nb = sqrt(sum(y*y for y in b)) or 1.0
            return dot/(na*nb)
        out = []
        for mid in self._user_memories.get(subject_id, []):
            mem = self._memories.get(mid)
            if mem and mem.get("embedding"):
                out.append((mid, cos(query_vector, mem["embedding"])))
        out.sort(key=lambda x: x[1], reverse=True)
        return out[:top_k]

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        """Single memory lookup by stable ID, used by correction/expiry paths."""
        return self._memories.get(memory_id)

    def get_all_for_subject(self, subject_id: str) -> list[dict[str, Any]]:
        return [self._memories[m] for m in self._user_memories.get(subject_id, []) if m in self._memories]

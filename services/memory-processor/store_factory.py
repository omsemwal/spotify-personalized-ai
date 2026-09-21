"""Dependency-injection factory: returns the real Neo4j-backed store in
production, or the in-memory test double when LOCAL_MODE=true / Neo4j is
unreachable. Every service that touches the graph uses this same factory so
swapping backends never requires touching business logic."""
import os

_STORE_SINGLETON = None


def get_graph_store():
    global _STORE_SINGLETON
    if _STORE_SINGLETON is not None:
        return _STORE_SINGLETON
    local_mode = os.getenv("LOCAL_MODE", "true").lower() == "true"
    if not local_mode:
        try:
            from graph import TemporalGraphStore
            _STORE_SINGLETON = TemporalGraphStore()
            return _STORE_SINGLETON
        except Exception:
            pass
    from memory_store import InMemoryGraphStore
    _STORE_SINGLETON = InMemoryGraphStore()
    return _STORE_SINGLETON

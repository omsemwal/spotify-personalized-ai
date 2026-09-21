"""Same DI pattern as memory-processor/retrieval-api — kept per-service on
purpose (not a shared package) since infra wiring, unlike domain contracts,
is expected to vary slightly per service's deployment footprint."""
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

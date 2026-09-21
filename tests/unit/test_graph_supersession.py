"""Unit: temporal graph supersession never destroys history (§6.1 step 3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "graph-schema"))

from tests.doubles.graph_store import InMemoryGraphStore


def test_correction_supersedes_without_deleting():
    store = InMemoryGraphStore()
    old = {"memory_id": "m1", "subject_id": "u1", "fact_text": "likes lofi",
           "memory_type": "explicit_preference", "entities": ["lofi"], "confidence": 0.9,
           "recorded_at": "2026-01-01T00:00:00", "status": "active"}
    store.write_memory(old)

    new = {"memory_id": "m2", "subject_id": "u1", "fact_text": "likes instrumental piano",
           "memory_type": "correction", "entities": ["instrumental"], "confidence": 1.0,
           "recorded_at": "2026-01-08T00:00:00", "status": "active"}
    store.correct_memory("m1", new)

    old_record = store._memories["m1"]
    assert old_record["status"] == "superseded"
    assert old_record["valid_to"] is not None  # history preserved, not deleted
    assert "m1" in store._memories  # still present, just superseded

    active = store.traverse_related("u1", [])
    active_ids = [m["memory_id"] for m in active]
    assert "m2" in active_ids
    assert "m1" not in active_ids  # superseded fact excluded from active traversal

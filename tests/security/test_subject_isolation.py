"""Security: cross-subject leakage must be impossible at the graph traversal
boundary (§5.5 Security, §7.7 'Cross-subject isolation... tests pass' release gate)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "graph-schema"))

from memory_store import InMemoryGraphStore


def test_traverse_never_crosses_subject_boundary():
    store = InMemoryGraphStore()
    store.write_memory({"memory_id": "m_a", "subject_id": "u_A", "fact_text": "A's secret preference",
                         "memory_type": "explicit_preference", "entities": [], "confidence": 0.9,
                         "recorded_at": "2026-01-01T00:00:00", "status": "active"})
    store.write_memory({"memory_id": "m_b", "subject_id": "u_B", "fact_text": "B's preference",
                         "memory_type": "explicit_preference", "entities": [], "confidence": 0.9,
                         "recorded_at": "2026-01-01T00:00:00", "status": "active"})

    results_for_b = store.get_all_for_subject("u_B")
    ids = [r["memory_id"] for r in results_for_b]
    assert "m_a" not in ids, "CROSS-SUBJECT LEAKAGE — release-blocking per §7.7"
    assert "m_b" in ids

"""Integration: an accepted event, once classified, must be write-able into
the graph store end to end (ingestion -> classification -> graph), using the
in-memory adapters so this runs without live infra (§7.7 Functional coverage)."""
import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "packages" / "graph-schema"))
sys.path.insert(0, str(repo_root / "services" / "memory-processor"))

from packages.contracts import InteractionEvent
from classifier import classify
from memory_store import InMemoryGraphStore
from datetime import datetime, timezone


def test_explicit_statement_flows_to_graph():
    event = InteractionEvent(
        event_id="e_it_1", subject_id="u_it_1", surface="music_chat", event_type="statement",
        payload={"text": "I like jazz in the evening", "entities": ["jazz"], "explicit": True},
        locale="en-US", timestamp=datetime.now(timezone.utc).isoformat(),
        consent_state="granted", idempotency_key="idem_it_1",
    )
    candidates = classify(event)
    assert len(candidates) == 1
    assert candidates[0].decision == "accept"

    store = InMemoryGraphStore()
    now = datetime.now(timezone.utc).isoformat()
    store.write_memory({
        "memory_id": candidates[0].memory_id, "subject_id": event.subject_id,
        "fact_text": candidates[0].normalized_fact, "memory_type": candidates[0].memory_type,
        "entities": candidates[0].entities, "confidence": candidates[0].confidence,
        "recorded_at": now, "status": "active",
    })
    results = store.get_all_for_subject("u_it_1")
    assert len(results) == 1
    assert results[0]["fact_text"] == "I like jazz in the evening"

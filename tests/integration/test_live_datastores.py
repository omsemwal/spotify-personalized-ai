"""Tests that run against the real datastores.

These are the other half of U4. `test_no_silent_fallback.py` proves the services
refuse to run against a substitute; this proves they actually work against the
real thing — that `./scripts/dev.sh up` produces a stack the code can use, and
that the migrations really applied.

Skipped, loudly, when the datastores are not running. Not quietly rerouted to a
double: a test that changes what it is testing when infrastructure is missing is
the same failure this unit removed from the services.

    ./scripts/dev.sh up

Everything written here is namespaced under a `test_` subject id and cleaned up
afterwards, so running the suite against a local stack does not leave rubbish in
the graph.
"""

import sys
import uuid
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "packages" / "graph-schema"))
sys.path.insert(0, str(_REPO_ROOT / "services" / "ingestion-api"))

from tests.conftest import requires_live_datastores

pytestmark = pytest.mark.integration


# ─────────────────────────────────────────────────────────────────────────────
# Neo4j
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def live_graph():
    from store_factory import get_graph_store, reset_graph_store

    reset_graph_store()
    store = get_graph_store()
    written: list[str] = []
    yield store, written
    for memory_id in written:
        store.delete_memory(memory_id)
    reset_graph_store()


@requires_live_datastores("neo4j")
def test_graph_round_trip_against_real_neo4j(live_graph):
    """Write, read back, delete. The basic proof that the Cypher in
    packages/graph-schema/graph.py is valid against a real database — it had
    never actually been executed before this unit."""
    store, written = live_graph
    subject = f"test_subject_{uuid.uuid4().hex[:8]}"
    memory_id = f"test_mem_{uuid.uuid4().hex[:8]}"
    written.append(memory_id)

    store.write_memory({
        "memory_id": memory_id,
        "subject_id": subject,
        "fact_text": "prefers low-vocal music while working",
        "memory_type": "explicit_preference",
        "confidence": 0.9,
        "policy_class": "normal",
        "source_event_id": "test_event_1",
        "entities": ["attribute:low_vocal", "activity:focus_work"],
    })

    stored = store.get_memory(memory_id)
    assert stored is not None
    assert stored["fact_text"] == "prefers low-vocal music while working"
    assert stored["subject_id"] == subject
    assert set(stored["entities"]) == {"attribute:low_vocal", "activity:focus_work"}

    store.delete_memory(memory_id)
    assert store.get_memory(memory_id) is None


@requires_live_datastores("neo4j")
def test_subject_isolation_holds_in_real_cypher(live_graph):
    """§9 makes cross-subject leakage a release blocker, and the in-memory
    double cannot prove anything about the real query — the isolation lives in
    the Cypher, not in Python."""
    store, written = live_graph
    subject_a = f"test_subject_a_{uuid.uuid4().hex[:8]}"
    subject_b = f"test_subject_b_{uuid.uuid4().hex[:8]}"

    for subject, text in ((subject_a, "likes jazz"), (subject_b, "likes techno")):
        memory_id = f"test_mem_{uuid.uuid4().hex[:8]}"
        written.append(memory_id)
        store.write_memory({
            "memory_id": memory_id,
            "subject_id": subject,
            "fact_text": text,
            "memory_type": "explicit_preference",
            "confidence": 0.9,
            "policy_class": "normal",
            "source_event_id": "test_event",
            "entities": ["genre:shared_entity"],
        })

    a_rows = store.get_all_for_subject(subject_a)
    assert len(a_rows) == 1
    assert a_rows[0]["fact_text"] == "likes jazz"

    # Both memories point at the same entity. A traversal that walked the entity
    # without re-anchoring on the subject would return both.
    traversed = store.traverse_related(subject_a, ["genre:shared_entity"])
    assert {row["fact_text"] for row in traversed} == {"likes jazz"}


@requires_live_datastores("neo4j")
def test_migrations_created_the_constraints():
    """§6.4 step 4 requires constraints applied before traffic. Without the
    uniqueness constraint, an idempotent upsert is not idempotent — a replayed
    event would create a second node with the same memory_id."""
    from graph import TemporalGraphStore

    store = TemporalGraphStore()
    try:
        with store.driver.session() as session:
            names = {record["name"] for record in session.run("SHOW CONSTRAINTS YIELD name")}
        assert {"memory_id_unique", "user_id_unique", "entity_name_unique"} <= names, (
            f"expected constraints are missing: {names}. Run `./scripts/dev.sh migrate`."
        )
    finally:
        store.close()


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

@requires_live_datastores("postgres")
def test_migrations_created_the_operational_tables():
    """The operational store holds consent, deletion jobs, feedback and the tool
    audit. A missing table here is a silent failure of the deletion path, which
    §9 treats as a release blocker."""
    import psycopg

    conn = psycopg.connect(
        host="localhost",
        port=5433,
        dbname="memory_system",
        user="postgres",
        password="postgres_password_secure",
        connect_timeout=5,
    )
    try:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchall()
    finally:
        conn.close()

    tables = {r[0] for r in rows}
    expected = {"consent_state", "ingestion_status", "tool_audit", "experiments",
                "feedback", "deletion_jobs"}
    missing = sorted(expected - tables)
    assert not missing, f"missing operational tables: {missing}. Run `./scripts/dev.sh migrate`."


# ─────────────────────────────────────────────────────────────────────────────
# Redis
# ─────────────────────────────────────────────────────────────────────────────

@requires_live_datastores("redis")
def test_idempotency_claim_is_atomic_against_real_redis():
    """The behaviour that actually matters: the second claim of the same key
    must fail. A check-then-set could let two concurrent requests both pass."""
    from idempotency_adapter import IdempotencyAdapter

    adapter = IdempotencyAdapter(ttl_seconds=60)
    key = f"test_idem_{uuid.uuid4().hex}"

    assert adapter.claim(key) is True, "first claim should succeed"
    assert adapter.claim(key) is False, "second claim of the same key must fail"
    assert adapter.seen(key) is True
    assert adapter.status()["reachable"] is True


# ─────────────────────────────────────────────────────────────────────────────
# Redpanda
# ─────────────────────────────────────────────────────────────────────────────

@requires_live_datastores("redpanda")
def test_events_reach_the_real_broker():
    """Publishing waits for the broker's acknowledgement, which is what makes
    ingestion's 202 an honest answer rather than a hope."""
    from queue_adapter import QueueAdapter

    adapter = QueueAdapter(bootstrap_servers="localhost:19092")
    try:
        adapter.publish({
            "event_id": f"test_event_{uuid.uuid4().hex[:8]}",
            "subject_id": "test_subject",
            "note": "written by the U4 integration test",
        })
        assert adapter.status()["reachable"] is True
    finally:
        adapter.close()

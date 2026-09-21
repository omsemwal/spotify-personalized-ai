"""The fallbacks are gone, and must stay gone.

Every adapter in this system used to catch connection errors and quietly
continue against an in-process substitute — a Python dict for the graph, a
`queue.Queue` for the broker, a list for the audit log. The effect was a system
that reported itself healthy while storing nothing durable. Tests passed, health
checks were green, and the README described an architecture the running code was
not using.

These tests point each adapter at a port where nothing is listening and assert
that it **raises**. They are the regression guard: if someone reintroduces a
`try/except: pass` around a connection, one of these turns red.

There is a matching lint rule. `pyproject.toml` ignores BLE001, S110 and S112
"until U4 lands" — that ignore is what U4 removes, and these tests are what
keeps the behaviour once the linter is watching.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "packages" / "graph-schema"))
sys.path.insert(0, str(_REPO_ROOT / "services" / "ingestion-api"))

# A port nothing listens on. Port 1 is reserved and never bound in practice.
DEAD_HOST = "127.0.0.1"
DEAD_PORT = "1"


@pytest.fixture(autouse=True)
def _fast_timeouts(monkeypatch):
    """Every client here is pointed at a dead port, and each one defaults to a
    multi-second timeout so that a real outage is not mistaken for a slow
    network. That is right in production and far too slow for a suite that runs
    on every pull request, so the timeouts are configurable and these tests turn
    them down. What is asserted is that the call raises, not how long it waits.
    """
    monkeypatch.setenv("REDIS_CONNECT_TIMEOUT", "0.2")
    monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT", "1")
    monkeypatch.setenv("KAFKA_MAX_BLOCK_MS", "500")
    monkeypatch.setenv("NEO4J_CONNECTION_TIMEOUT", "1")
    monkeypatch.setenv("NEO4J_MAX_RETRY_TIME", "1")


@pytest.fixture(autouse=True)
def _clean_store_singleton():
    """Each test starts with no cached or injected store, and leaves none
    behind — otherwise one test's double silently satisfies the next."""
    from store_factory import reset_graph_store

    reset_graph_store()
    yield
    reset_graph_store()


# ─────────────────────────────────────────────────────────────────────────────
# Graph store
# ─────────────────────────────────────────────────────────────────────────────

def test_graph_store_raises_when_neo4j_is_unreachable(monkeypatch):
    """The most important test in this file. This is the fallback that made a
    dead database look identical to a healthy one."""
    from store_factory import BackendUnavailable, get_graph_store

    monkeypatch.setenv("NEO4J_URI", f"bolt://{DEAD_HOST}:{DEAD_PORT}")
    with pytest.raises(BackendUnavailable) as exc:
        get_graph_store()
    assert "cannot reach Neo4j" in str(exc.value)


def test_graph_store_error_says_how_to_fix_it(monkeypatch):
    """An error that stops a service has to tell you what to do next, or the
    first thing anyone does is add the fallback back."""
    from store_factory import BackendUnavailable, get_graph_store

    monkeypatch.setenv("NEO4J_URI", f"bolt://{DEAD_HOST}:{DEAD_PORT}")
    with pytest.raises(BackendUnavailable) as exc:
        get_graph_store()
    assert "./scripts/dev.sh up" in str(exc.value)


def test_graph_health_reports_unreachable_rather_than_raising(monkeypatch):
    """A health check must answer, not explode — an endpoint that raises gives
    the orchestrator no detail to report."""
    from store_factory import graph_store_status

    monkeypatch.setenv("NEO4J_URI", f"bolt://{DEAD_HOST}:{DEAD_PORT}")
    result = graph_store_status()
    assert result["reachable"] is False
    assert result["backend"] == "neo4j"


def test_no_environment_variable_can_select_a_fake_store(monkeypatch):
    """LOCAL_MODE used to do exactly this. A fake backend selected by an
    environment variable is how a fake backend ends up running in a place it
    should not."""
    from store_factory import BackendUnavailable, get_graph_store

    monkeypatch.setenv("NEO4J_URI", f"bolt://{DEAD_HOST}:{DEAD_PORT}")
    for value in ("true", "1", "yes"):
        monkeypatch.setenv("LOCAL_MODE", value)
        with pytest.raises(BackendUnavailable):
            get_graph_store()


def test_tests_can_still_inject_a_double():
    """Explicit injection is the supported route, and it has to work or every
    other test in the suite has no store."""
    from store_factory import get_graph_store, set_graph_store

    from tests.doubles.graph_store import InMemoryGraphStore

    double = InMemoryGraphStore()
    set_graph_store(double)
    assert get_graph_store() is double


def test_injected_double_is_reported_as_a_double_in_health():
    """A health check must never describe a test double as a live Neo4j."""
    from store_factory import graph_store_status, set_graph_store

    from tests.doubles.graph_store import InMemoryGraphStore

    set_graph_store(InMemoryGraphStore())
    assert graph_store_status()["backend"] == "injected_test_double"


def test_production_code_does_not_import_the_test_double():
    """The double lives under tests/ so that nothing shippable can reach it.
    This asserts the boundary rather than trusting it.

    Parsed rather than grepped: a docstring showing how a test should inject the
    double is fine, an actual import is not, and only the parse tells them
    apart.
    """
    import ast

    offenders = []
    for root in ("services", "packages"):
        for path in (_REPO_ROOT / root).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    names = {alias.name for alias in node.names}
                    if module.startswith("tests") or "InMemoryGraphStore" in names:
                        offenders.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("tests"):
                            offenders.append(f"{path.relative_to(_REPO_ROOT)}:{node.lineno}")
    assert not offenders, f"production code imports the test double: {offenders}"


# ─────────────────────────────────────────────────────────────────────────────
# Event queue
# ─────────────────────────────────────────────────────────────────────────────

def test_queue_adapter_raises_when_the_broker_is_unreachable(monkeypatch):
    """Falling back to an in-process queue meant ingestion returned 202 —
    "accepted" — for events that were dropped on the next restart."""
    from queue_adapter import QueueAdapter, QueueUnavailable

    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", f"{DEAD_HOST}:{DEAD_PORT}")
    with pytest.raises(QueueUnavailable):
        QueueAdapter()


# ─────────────────────────────────────────────────────────────────────────────
# Idempotency
# ─────────────────────────────────────────────────────────────────────────────

def test_idempotency_adapter_raises_when_redis_is_unreachable(monkeypatch):
    """A per-process dict stops detecting duplicates the moment a second
    replica exists, and nothing reports that it has stopped."""
    from idempotency_adapter import IdempotencyAdapter, IdempotencyStoreUnavailable

    monkeypatch.setenv("REDIS_HOST", DEAD_HOST)
    monkeypatch.setenv("REDIS_PORT", DEAD_PORT)
    with pytest.raises(IdempotencyStoreUnavailable):
        IdempotencyAdapter()


# ─────────────────────────────────────────────────────────────────────────────
# Operational stores
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "service_dir,call",
    [
        ("deletion-orchestrator", lambda m: m.get_job("job_1")),
        ("deletion-orchestrator", lambda m: m.save_job(
            {"job_id": "j1", "memory_id": "m1", "status": "pending", "stores": {}}
        )),
        ("context-composer", lambda m: m.save_feedback({"trace_id": "t", "subject_id": "s"})),
        ("retrieval-api", lambda m: m.negative_feedback_memory_ids("s")),
    ],
    ids=[
        "deletion job read",
        "deletion job write",
        "feedback write",
        "negative feedback read",
    ],
)
def test_operational_stores_raise_when_postgres_is_unreachable(monkeypatch, service_dir, call):
    """Each of these used to swallow the failure and return an empty or
    in-memory result.

    The deletion ones were the worst: the user is told their data was erased,
    while the job record lives in one process's memory. §9 makes a deletion
    failure a release blocker.

    The negative-feedback read was subtler but also a trust failure — an empty
    set means "this subject rejected nothing", so an outage silently resurfaced
    the exact memories a user had rejected.
    """
    import importlib

    sys.path.insert(0, str(_REPO_ROOT / "services" / service_dir))
    module_name = f"operational_store_{service_dir.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(
        module_name, _REPO_ROOT / "services" / service_dir / "operational_store.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setenv("POSTGRES_HOST", DEAD_HOST)
    monkeypatch.setenv("POSTGRES_PORT", DEAD_PORT)
    module.set_connection(None)

    with pytest.raises(module.OperationalStoreUnavailable):
        call(module)


def test_deletion_job_lookup_distinguishes_missing_from_broken(monkeypatch):
    """`get_job` returning None must mean "no such job" and nothing else.

    When it also meant "the database was unreachable", a completed deletion
    could be reported to the user as though it had never been requested.
    """
    import importlib

    spec = importlib.util.spec_from_file_location(
        "operational_store_deletion_semantics",
        _REPO_ROOT / "services" / "deletion-orchestrator" / "operational_store.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    monkeypatch.setenv("POSTGRES_HOST", DEAD_HOST)
    monkeypatch.setenv("POSTGRES_PORT", DEAD_PORT)
    module.set_connection(None)

    # The unreachable case raises. It does not return None.
    with pytest.raises(module.OperationalStoreUnavailable):
        module.get_job("never-existed")

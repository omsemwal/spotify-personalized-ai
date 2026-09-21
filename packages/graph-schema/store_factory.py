"""
The single place that decides which graph store a service uses.

Why this file exists
--------------------
Four services previously carried their own near-identical copy of this logic,
and every copy did the same dangerous thing: it tried to connect to Neo4j,
caught *any* exception, and silently fell back to an in-memory Python
dictionary. A dead database looked exactly like a healthy one. Tests passed,
health checks were green, the README described an architecture the running code
was not using.

That fallback is gone. The rule now:

    A service reads its dependency configuration at boot and refuses to start if
    it cannot reach that dependency.

The only legitimate fallback in this system is the one the requirements
actually name — retrieval failing open to an explicit **no-memory** response
(§5.5 Reliability). That is a product behaviour decided in the retrieval path,
not an error handler hidden in a connection helper.

Testing
-------
Tests inject a double explicitly with `set_graph_store()`. There is no
environment variable that makes production code pick a fake store, because an
environment variable is exactly how a fake store ends up running somewhere it
should not.

    from tests.doubles import InMemoryGraphStore
    set_graph_store(InMemoryGraphStore())
    ...
    reset_graph_store()
"""

import os

_STORE_SINGLETON = None
_INJECTED = False


class BackendUnavailable(RuntimeError):
    """A required datastore could not be reached.

    Raised rather than handled. Callers at service startup should let it
    propagate so the process exits and the orchestrator reports the service as
    unhealthy — which is the accurate signal.
    """


def set_graph_store(store) -> None:
    """Inject a store. For tests, and for nothing else."""
    global _STORE_SINGLETON, _INJECTED
    _STORE_SINGLETON = store
    _INJECTED = True


def reset_graph_store() -> None:
    """Drop the injected or cached store. Call in test teardown so one test's
    double cannot leak into the next.

    Closes the driver on the way out. Without this each reset leaks a Neo4j
    connection pool, which surfaces as ResourceWarnings in the test suite and as
    exhausted connections in anything long-running.
    """
    global _STORE_SINGLETON, _INJECTED
    store, _STORE_SINGLETON = _STORE_SINGLETON, None
    _INJECTED = False
    close = getattr(store, "close", None)
    if callable(close):
        close()


def get_graph_store():
    """The graph store for this process.

    Returns an injected double if one was set. Otherwise connects to Neo4j and
    verifies the connection actually works before handing it back — constructing
    the driver alone proves nothing, because the Neo4j driver connects lazily
    and would happily return an object that fails on first query.
    """
    global _STORE_SINGLETON
    if _STORE_SINGLETON is not None:
        return _STORE_SINGLETON

    try:
        from graph import TemporalGraphStore
    except ImportError as exc:  # pragma: no cover - import wiring, not logic
        raise BackendUnavailable(
            "the neo4j driver is not installed. Run `./scripts/dev.sh install`."
        ) from exc

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    try:
        store = TemporalGraphStore()
        store.verify_connectivity()
    except BackendUnavailable:
        raise
    except Exception as exc:
        raise BackendUnavailable(
            f"cannot reach Neo4j at {uri}: {exc}\n"
            "Start the datastores with `./scripts/dev.sh up`. "
            "This service will not start without the graph, because running it "
            "against an in-memory substitute would make every health check, test "
            "result and demo misleading."
        ) from exc

    _STORE_SINGLETON = store
    return _STORE_SINGLETON


def graph_store_status() -> dict:
    """Health-check detail: is the graph actually reachable right now?

    Used by every service's /health endpoint. Deliberately re-checks rather than
    reporting a cached value, so stopping Neo4j turns the health check red
    instead of it reporting the state at boot forever.
    """
    if _INJECTED:
        return {"backend": "injected_test_double", "reachable": True}
    try:
        store = get_graph_store()
        store.verify_connectivity()
    except BackendUnavailable as exc:
        return {"backend": "neo4j", "reachable": False, "error": str(exc).splitlines()[0]}
    except Exception as exc:
        return {"backend": "neo4j", "reachable": False, "error": str(exc)}
    return {"backend": "neo4j", "reachable": True}

"""
Reads negative feedback from the PostgreSQL operational store so ranking can
demote memories a subject has rejected (§5.4 "Rerank by ... negative feedback").

Read-only here — feedback is written by context-composer.

This used to return an empty set when Postgres was unreachable, on the reasoning
that retrieval should still work without the negative signal. The problem is
what an empty set *means* to the caller: "this subject has rejected nothing". So
a database outage silently turned into resurfacing the exact memories a user
had explicitly rejected, with no trace of why.

That is a trust failure, not graceful degradation. §5.5 Reliability does allow
retrieval to fail open — but to an explicit **no-memory** response, not to a
personalized answer built from incomplete safety signals. So this raises, and
the retrieval path decides what to do about it.
"""

import os

# Feedback types that mean "this memory was not wanted"
# (see packages/contracts/feedback.py)
NEGATIVE_TYPES = ("irrelevant", "rejection", "satisfaction_negative")

_CONN = None


class OperationalStoreUnavailable(RuntimeError):
    """Postgres could not be reached, or a statement failed."""


def _dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5433')} "
        f"dbname={os.getenv('POSTGRES_DB', 'memory_system')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASSWORD', 'postgres_password_secure')}"
    )


def _conn():
    global _CONN
    if _CONN is not None and not _CONN.closed:
        return _CONN
    try:
        import psycopg
    except ImportError as exc:
        raise OperationalStoreUnavailable(
            "psycopg is not installed. Run `./scripts/dev.sh install`."
        ) from exc
    try:
        _CONN = psycopg.connect(_dsn(), autocommit=True, connect_timeout=int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "5")))
    except Exception as exc:
        raise OperationalStoreUnavailable(
            f"cannot reach PostgreSQL: {exc}\nStart it with `./scripts/dev.sh up`."
        ) from exc
    return _CONN


def set_connection(conn) -> None:
    """Inject a connection. For tests only."""
    global _CONN
    _CONN = conn


def status() -> dict:
    try:
        _conn().execute("SELECT 1")
    except Exception as exc:
        return {"backend": "postgres", "reachable": False, "error": str(exc).splitlines()[0]}
    return {"backend": "postgres", "reachable": True}


def negative_feedback_memory_ids(subject_id: str) -> set[str]:
    """Memory ids this subject gave negative feedback on.

    Subject-scoped, so one subject's feedback can never influence another's
    ranking (§5.4 subject isolation).
    """
    try:
        rows = _conn().execute(
            "SELECT DISTINCT memory_id FROM feedback "
            "WHERE subject_id = %s AND memory_id IS NOT NULL AND feedback_type = ANY(%s)",
            (subject_id, list(NEGATIVE_TYPES)),
        ).fetchall()
    except OperationalStoreUnavailable:
        raise
    except Exception as exc:
        raise OperationalStoreUnavailable(
            f"failed reading negative feedback for {subject_id!r}: {exc}"
        ) from exc
    return {r[0] for r in rows}

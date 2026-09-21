"""
Operational store for feedback (§6.2 PostgreSQL: "Stores consent state,
ingestion status, tool audit, experiments, feedback, and deletion jobs").

Feedback used to be appended to an in-process list when Postgres was
unreachable, so that recording it never failed the caller. The cost of that is
silent data loss in the one signal the whole quality story depends on: §9 scores
"measured impact", and §2 asks for uplift measured against a memory-disabled
baseline. Feedback that vanishes on restart cannot support either, and nothing
would have reported that it was vanishing.

So: Postgres or an explicit error.
"""

import os
from typing import Any

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


def save_feedback(fb: dict[str, Any]) -> None:
    """Records what the user or a reviewer said.

    §5.4 Experimentation: "Capture user corrections and reviewer decisions
    without automatically reinforcing model-generated claims." Nothing the model
    produced is ever written here — only an explicit human signal.
    """
    try:
        _conn().execute(
            "INSERT INTO feedback (trace_id, subject_id, memory_id, feedback_type, comment) "
            "VALUES (%s, %s, %s, %s, %s)",
            (
                fb.get("trace_id"),
                fb.get("subject_id"),
                fb.get("memory_id"),
                fb.get("feedback_type"),
                fb.get("comment"),
            ),
        )
    except OperationalStoreUnavailable:
        raise
    except Exception as exc:
        raise OperationalStoreUnavailable(f"failed recording feedback: {exc}") from exc

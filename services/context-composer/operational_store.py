"""
Operational store for feedback (§6.2 PostgreSQL: "Stores consent state,
ingestion status, tool audit, experiments, feedback, and deletion jobs").

Same per-service DI pattern as the other services. Falls back to an in-process
list when Postgres is unreachable so recording feedback never fails the caller;
that fallback is not durable — get_backend() says which one is live.
"""
import os
from typing import Any, Dict, List

_CONN = None
_BACKEND = "memory"
_FALLBACK: List[dict] = []


def _dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'memory_system')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASSWORD', 'postgres_password_secure')}"
    )


def _conn():
    global _CONN, _BACKEND
    if _CONN is not None:
        return _CONN
    if os.getenv("LOCAL_MODE", "true").lower() == "true":
        return None
    try:
        import psycopg
        _CONN = psycopg.connect(_dsn(), autocommit=True)
        _BACKEND = "postgres"
        return _CONN
    except Exception:
        return None


def get_backend() -> str:
    _conn()
    return _BACKEND


def save_feedback(fb: Dict[str, Any]) -> None:
    """Records what the user or reviewer said. Never records model output as if
    it were feedback (§5.4 "without self-validating model output")."""
    c = _conn()
    if c is None:
        _FALLBACK.append(fb)
        return
    try:
        c.execute(
            "INSERT INTO feedback (trace_id, subject_id, memory_id, feedback_type, comment) "
            "VALUES (%s, %s, %s, %s, %s)",
            (fb.get("trace_id"), fb.get("subject_id"), fb.get("memory_id"),
             fb.get("feedback_type"), fb.get("comment")),
        )
    except Exception:
        _FALLBACK.append(fb)

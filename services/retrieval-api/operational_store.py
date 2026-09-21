"""
Reads negative feedback from the PostgreSQL operational store so reranking can
demote memories a subject has rejected (§5.4 "Rerank by ... negative feedback").

Read-only here — feedback is written by context-composer. Falls back to an empty
set when Postgres is unreachable, so retrieval still works, just without the
negative signal.
"""
import os

# Feedback types that mean "this memory was not wanted" (packages/contracts/feedback.py)
NEGATIVE_TYPES = ("irrelevant", "rejection", "satisfaction_negative")

_CONN = None
_BACKEND = "memory"


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


def negative_feedback_memory_ids(subject_id: str) -> set[str]:
    """Memory IDs this subject gave negative feedback on. Subject-scoped: one
    subject's feedback can never influence another's ranking (§5.4 isolation)."""
    c = _conn()
    if c is None:
        return set()
    try:
        rows = c.execute(
            "SELECT DISTINCT memory_id FROM feedback "
            "WHERE subject_id = %s AND memory_id IS NOT NULL AND feedback_type = ANY(%s)",
            (subject_id, list(NEGATIVE_TYPES)),
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        return set()

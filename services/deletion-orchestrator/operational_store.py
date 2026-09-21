"""
Operational store for deletion jobs (§6.2 PostgreSQL: "Stores consent state,
ingestion status, tool audit, experiments, feedback, and deletion jobs").

Same per-service DI pattern as store_factory.py. Falls back to an in-process
dict when Postgres is unreachable, so a deletion still completes and reports
rather than failing the user's erasure request (§5.5 Reliability: fail open).
The fallback is not durable — get_backend() says which one is live.
"""
import json
import os
from typing import Any, Dict, Optional

_POOL = None
_BACKEND = "memory"
_FALLBACK: Dict[str, dict] = {}


def _dsn() -> str:
    return (
        f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
        f"port={os.getenv('POSTGRES_PORT', '5432')} "
        f"dbname={os.getenv('POSTGRES_DB', 'memory_system')} "
        f"user={os.getenv('POSTGRES_USER', 'postgres')} "
        f"password={os.getenv('POSTGRES_PASSWORD', 'postgres_password_secure')}"
    )


def _conn():
    """One lazily-opened connection. Returns None when Postgres is unavailable."""
    global _POOL, _BACKEND
    if _POOL is not None:
        return _POOL
    if os.getenv("LOCAL_MODE", "true").lower() == "true":
        return None
    try:
        import psycopg
        _POOL = psycopg.connect(_dsn(), autocommit=True)
        _BACKEND = "postgres"
        return _POOL
    except Exception:
        return None


def get_backend() -> str:
    _conn()
    return _BACKEND


def save_job(job: Dict[str, Any]) -> None:
    """Insert or update one deletion job. Store status is kept as JSON so a
    partial failure stays visible per store (§5.4: never silent partial completion)."""
    c = _conn()
    if c is None:
        _FALLBACK[job["job_id"]] = job
        return
    try:
        c.execute(
            """
            INSERT INTO deletion_jobs (job_id, memory_id, status, store_status, started_at, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_id) DO UPDATE
              SET status = EXCLUDED.status,
                  store_status = EXCLUDED.store_status,
                  completed_at = EXCLUDED.completed_at
            """,
            (job["job_id"], job["memory_id"], job["status"],
             json.dumps(job.get("stores", {})), job.get("started_at"), job.get("completed_at")),
        )
    except Exception:
        _FALLBACK[job["job_id"]] = job


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    c = _conn()
    if c is None:
        return _FALLBACK.get(job_id)
    try:
        row = c.execute(
            "SELECT job_id, memory_id, status, store_status, started_at, completed_at "
            "FROM deletion_jobs WHERE job_id = %s", (job_id,)
        ).fetchone()
        if row is None:
            return _FALLBACK.get(job_id)
        return {
            "job_id": row[0], "memory_id": row[1], "status": row[2],
            "stores": row[3] or {},
            "started_at": row[4].isoformat() if row[4] else None,
            "completed_at": row[5].isoformat() if row[5] else None,
        }
    except Exception:
        return _FALLBACK.get(job_id)

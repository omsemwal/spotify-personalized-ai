"""
Operational store for deletion jobs (§6.2 PostgreSQL: "Stores consent state,
ingestion status, tool audit, experiments, feedback, and deletion jobs").

This module previously fell back to an in-process dictionary when Postgres was
unreachable, justified as "failing open" so an erasure request would still
complete. That reasoning was wrong, and this was the most dangerous fallback in
the codebase:

  * The user is told their deletion completed.
  * The job record lives in one process's memory and disappears on restart.
  * `GET /v1/deletions/{job_id}` then reports nothing, or reports success from a
    replica that never did the work.

§9 makes a deletion failure a release blocker regardless of any other score, and
§5.4 requires deletion status to be reported per store with no silent partial
completion. Both require a durable record. "Fail open" applies to *retrieval* —
answering without personalization is harmless. It has never applied to erasure,
where failing open means claiming to have deleted data that still exists.

So: Postgres or an explicit error.
"""

import json
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
    """The connection, opening it on first use. Raises if unreachable."""
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
            f"cannot reach PostgreSQL: {exc}\n"
            "Start it with `./scripts/dev.sh up`. Deletion jobs must be durable — "
            "an in-process record would tell the user their data was erased while "
            "leaving no way to prove or resume it."
        ) from exc
    return _CONN


def set_connection(conn) -> None:
    """Inject a connection. For tests only."""
    global _CONN
    _CONN = conn


def status() -> dict:
    """Health-check detail, re-checked on every call."""
    try:
        _conn().execute("SELECT 1")
    except Exception as exc:
        return {"backend": "postgres", "reachable": False, "error": str(exc).splitlines()[0]}
    return {"backend": "postgres", "reachable": True}


def save_job(job: dict[str, Any]) -> None:
    """Insert or update one deletion job.

    Per-store status is kept as JSON so a partial failure stays visible for each
    store individually (§5.4: never silent partial completion).
    """
    try:
        _conn().execute(
            """
            INSERT INTO deletion_jobs (job_id, memory_id, status, store_status, started_at, completed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (job_id) DO UPDATE
              SET status = EXCLUDED.status,
                  store_status = EXCLUDED.store_status,
                  completed_at = EXCLUDED.completed_at
            """,
            (
                job["job_id"],
                job["memory_id"],
                job["status"],
                json.dumps(job.get("stores", {})),
                job.get("started_at"),
                job.get("completed_at"),
            ),
        )
    except OperationalStoreUnavailable:
        raise
    except Exception as exc:
        raise OperationalStoreUnavailable(
            f"failed recording deletion job {job.get('job_id')!r}: {exc}"
        ) from exc


def get_job(job_id: str) -> dict[str, Any] | None:
    """One job, or None if there is no such job.

    None means "no such job" and nothing else. It must never also mean "the
    database was unreachable", because the caller cannot tell those apart and
    would report a real deletion as missing.
    """
    try:
        row = _conn().execute(
            "SELECT job_id, memory_id, status, store_status, started_at, completed_at "
            "FROM deletion_jobs WHERE job_id = %s",
            (job_id,),
        ).fetchone()
    except OperationalStoreUnavailable:
        raise
    except Exception as exc:
        raise OperationalStoreUnavailable(f"failed reading deletion job {job_id!r}: {exc}") from exc

    if row is None:
        return None
    return {
        "job_id": row[0],
        "memory_id": row[1],
        "status": row[2],
        "stores": row[3] or {},
        "started_at": row[4].isoformat() if row[4] else None,
        "completed_at": row[5].isoformat() if row[5] else None,
    }

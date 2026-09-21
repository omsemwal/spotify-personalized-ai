"""Audit log for every MCP tool call — required by §5.4: "Each tool needs...
an audit event", and §6.2 PostgreSQL: "Stores ... tool audit".

Input summaries are redacted before they are stored (§5.4 "Redact sensitive
payloads from logs while preserving identifiers needed for investigation"), so
identifiers and outcomes stay debuggable while free text does not persist.

This used to fall back to an in-process list so that a tool call was never
failed by the audit path. An audit log is a security control, and a security
control that silently stops recording is worse than one that is absent: §5.4
requires an audit event per tool call, and §7.7 lists tool abuse among the
security tests. If the record cannot be written, the call does not happen.
Failing closed is the standard position for audit, and it is the only one that
makes "every tool call is audited" a true statement.
"""
import json
import os
from typing import Any

from packages.observability import redact_payload

_CONN = None


class AuditUnavailable(RuntimeError):
    """The audit log could not be written. The calling tool must not proceed."""


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
        raise AuditUnavailable("psycopg is not installed. Run `./scripts/dev.sh install`.") from exc
    try:
        _CONN = psycopg.connect(_dsn(), autocommit=True, connect_timeout=int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "5")))
    except Exception as exc:
        raise AuditUnavailable(
            f"cannot reach the audit store: {exc}. "
            "Start it with `./scripts/dev.sh up`. MCP tools refuse to run without an "
            "audit trail, because §5.4 requires an audit event for every tool call."
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


def record(tool_name: str, subject_id: str, input_summary: dict[str, Any], outcome: str) -> None:
    """Write one audit row. Raises if it cannot — see the module docstring."""
    safe = redact_payload(input_summary or {})
    try:
        _conn().execute(
            "INSERT INTO tool_audit (tool_name, subject_id, input_summary, outcome) "
            "VALUES (%s, %s, %s, %s)",
            (tool_name, subject_id, json.dumps(safe), outcome),
        )
    except AuditUnavailable:
        raise
    except Exception as exc:
        raise AuditUnavailable(f"failed writing audit row for {tool_name!r}: {exc}") from exc


def recent(subject_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Recent audit rows, for the console's audit trace view (§7.6)."""
    # Two complete statements rather than one assembled from fragments. The
    # values were always bound parameters, but a query built by concatenation
    # is the shape SQL injection takes, and it should not appear in a file whose
    # job is to be the trustworthy record.
    try:
        conn = _conn()
        if subject_id:
            rows = conn.execute(
                "SELECT tool_name, subject_id, input_summary, outcome, created_at "
                "FROM tool_audit WHERE subject_id = %s ORDER BY created_at DESC LIMIT %s",
                (subject_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT tool_name, subject_id, input_summary, outcome, created_at "
                "FROM tool_audit ORDER BY created_at DESC LIMIT %s",
                (limit,),
            ).fetchall()
    except AuditUnavailable:
        raise
    except Exception as exc:
        raise AuditUnavailable(f"failed reading audit log: {exc}") from exc
    return [
        {
            "tool_name": r[0],
            "subject_id": r[1],
            "input_summary": r[2],
            "outcome": r[3],
            "timestamp": r[4].isoformat() if r[4] else None,
        }
        for r in rows
    ]

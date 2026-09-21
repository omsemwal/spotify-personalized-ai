"""Audit log for every MCP tool call — required by §5.4: "Each tool needs...
an audit event", and §6.2 PostgreSQL: "Stores ... tool audit".

Input summaries are redacted before they are stored (§5.4 "Redact sensitive
payloads from logs while preserving identifiers needed for investigation"), so
identifiers and outcomes stay debuggable while free text does not persist.
Falls back to an in-process list when Postgres is unreachable, so a tool call is
never failed by the audit path.
"""
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from packages.observability import redact_payload

_AUDIT_LOG: List[Dict[str, Any]] = []
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


def record(tool_name: str, subject_id: str, input_summary: Dict[str, Any], outcome: str) -> None:
    safe = redact_payload(input_summary or {})
    entry = {
        "tool_name": tool_name, "subject_id": subject_id,
        "input_summary": safe, "outcome": outcome,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    c = _conn()
    if c is None:
        _AUDIT_LOG.append(entry)
        return
    try:
        import json
        c.execute(
            "INSERT INTO tool_audit (tool_name, subject_id, input_summary, outcome) "
            "VALUES (%s, %s, %s, %s)",
            (tool_name, subject_id, json.dumps(safe), outcome),
        )
    except Exception:
        _AUDIT_LOG.append(entry)


def get_audit_log() -> List[Dict[str, Any]]:
    return list(_AUDIT_LOG)

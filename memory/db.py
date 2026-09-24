"""Talking to PostgreSQL.

Three things this file does:

  1. get_consent(subject_id)  - what OUR record says about consent
  2. save_event(...)          - write one accepted event
  3. count_events(subject_id) - used by tests

abc.md:219 - PostgreSQL "stores consent state, ingestion status, tool
audit, experiments, feedback, and deletion jobs."

Plain SQL on purpose. No ORM, no models, no magic - what you read here is
what runs on the database.
"""

import atexit
from datetime import datetime, timedelta, timezone

from psycopg_pool import ConnectionPool

from memory import config

# abc.md:109 - "Separate raw event retention from memory retention."
# Raw events are short-lived; memories live much longer, on their own clock.
RAW_EVENT_RETENTION = timedelta(days=30)


_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    """One small pool, opened the first time it is needed.

    Opening a fresh TCP connection for every request is slow, so a few are
    kept open and handed out as needed.
    """
    global _pool
    if _pool is None:
        _pool = ConnectionPool(config.postgres_url(), min_size=1, max_size=5)
        # Close it tidily on shutdown, or Python complains about the
        # pool's background thread still running as it exits.
        atexit.register(close)
    return _pool


def close() -> None:
    """Shut the pool down."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def connect():
    """Borrow a connection from the pool. Use it with `with`."""
    return _get_pool().connection()


def get_consent(subject_id: str) -> str | None:
    """What our record says: 'granted', 'denied', 'paused', or None.

    None means we have no record for this subject at all.

    This is the point of the whole file. abc.md:187 says the API
    "verifies ... consent state" - and you cannot verify a claim against
    nothing. The caller tells us what they believe; this tells us what is
    true.
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT state FROM consent WHERE subject_id = %s",
            (subject_id,),
        ).fetchone()
    return row[0] if row else None


def save_event(event_id: str, event: dict, service_id: str) -> None:
    """Write one accepted event.

    `event` is the validated request body as a dict.
    """
    expires_at = datetime.now(timezone.utc) + RAW_EVENT_RETENTION

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ingested_event (
                event_id, subject_id, service_id, event_type, surface,
                locale, schema_version, source_event_id, idempotency_key,
                occurred_at, expires_at, content
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event_id,
                event["subject_id"],
                service_id,
                event["event_type"],
                event["surface"],
                event["locale"],
                event["schema_version"],
                event["source_event_id"],
                event["idempotency_key"],
                event["occurred_at"],
                expires_at,
                # Untrusted free text (abc.md:134). Stored as data only.
                event.get("content"),
            ),
        )


def count_events(subject_id: str) -> int:
    """How many events we hold for one subject. Used by tests."""
    with connect() as conn:
        row = conn.execute(
            "SELECT count(*) FROM ingested_event WHERE subject_id = %s",
            (subject_id,),
        ).fetchone()
    return row[0]


def delete_events(subject_id: str) -> None:
    """Remove one subject's events. Used by tests to clean up."""
    with connect() as conn:
        conn.execute(
            "DELETE FROM ingested_event WHERE subject_id = %s", (subject_id,)
        )


def set_consent(subject_id: str, state: str) -> None:
    """Set a subject's consent. Used by tests and by seeding."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO consent (subject_id, state) VALUES (%s, %s)
            ON CONFLICT (subject_id)
            DO UPDATE SET state = EXCLUDED.state, updated_at = now()
            """,
            (subject_id, state),
        )


# --- Audit trail ----------------------------------------------------------

def record_audit(
    action: str,
    subject_id: str,
    service_id: str,
    outcome: str,
    correlation_id: str,
    reason: str | None = None,
    event_id: str | None = None,
    memory_id: str | None = None,
) -> None:
    """Write one line saying what happened.

    abc.md:460 scores the backend on audit events. abc.md:322 says logs
    carry identifiers and outcomes, not private content - so there is no
    parameter here for what the listener played or said, by design.
    """
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_log
                (action, subject_id, service_id, outcome,
                 correlation_id, reason, event_id, memory_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (action, subject_id, service_id, outcome,
             correlation_id, reason, event_id, memory_id),
        )


def get_audit(subject_id: str) -> list[dict]:
    """Read one subject's audit trail, newest first."""
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT action, outcome, reason, event_id, correlation_id, service_id,
                   memory_id
            FROM audit_log WHERE subject_id = %s ORDER BY id DESC
            """,
            (subject_id,),
        ).fetchall()
    keys = ("action", "outcome", "reason", "event_id", "correlation_id",
            "service_id", "memory_id")
    return [dict(zip(keys, row)) for row in rows]


def delete_audit(subject_id: str) -> None:
    """Remove one subject's audit lines. Used by tests."""
    with connect() as conn:
        conn.execute("DELETE FROM audit_log WHERE subject_id = %s", (subject_id,))


# --- Retention ------------------------------------------------------------

def delete_expired_events() -> int:
    """Delete raw events past their expiry, and say how many went.

    abc.md:109 - raw events expire on their own clock. Storing expires_at
    is not enough; something has to actually remove them.
    """
    with connect() as conn:
        result = conn.execute(
            "DELETE FROM ingested_event WHERE expires_at < now()"
        )
        return result.rowcount


# --- Metrics --------------------------------------------------------------

def ingestion_metrics() -> dict:
    """Numbers for the Overview screen.

    abc.md:143 - "Monitor ingestion lag, write failures, ... and policy
    rejection rate."

    Everything here comes from the audit table we already write, so there
    is no separate counter to keep in step.
    """
    with connect() as conn:
        outcomes = dict(
            conn.execute(
                "SELECT outcome, count(*) FROM audit_log GROUP BY outcome"
            ).fetchall()
        )

        reasons = dict(
            conn.execute(
                "SELECT reason, count(*) FROM audit_log"
                " WHERE reason IS NOT NULL GROUP BY reason"
            ).fetchall()
        )

        # Ingestion lag: how long ago the newest event arrived. If this
        # grows, events have stopped coming in.
        lag = conn.execute(
            "SELECT extract(epoch FROM now() - max(received_at))"
            " FROM ingested_event"
        ).fetchone()[0]

        stored = conn.execute("SELECT count(*) FROM ingested_event").fetchone()[0]

    accepted = outcomes.get("accepted", 0)
    rejected = outcomes.get("rejected", 0)
    total = accepted + rejected + outcomes.get("duplicate", 0)

    return {
        "events": {
            "accepted": accepted,
            "rejected": rejected,
            "duplicate": outcomes.get("duplicate", 0),
            "stored": stored,
        },
        "rejection_rate": round(rejected / total, 4) if total else 0.0,
        "rejections_by_reason": reasons,
        "ingestion_lag_seconds": round(lag, 1) if lag is not None else None,
    }


def get_event(event_id: str, subject_id: str) -> dict | None:
    """Read one event back, for extraction.

    Takes the subject as well as the id: every read is subject-scoped
    (abc.md:110, "subject isolation at the query boundary"), so one
    subject can never read another's event even knowing its id.
    """
    with connect() as conn:
        row = conn.execute(
            """
            SELECT event_id, subject_id, event_type, surface, locale,
                   occurred_at, content
            FROM ingested_event
            WHERE event_id = %s AND subject_id = %s
            """,
            (event_id, subject_id),
        ).fetchone()

    if row is None:
        return None

    keys = ("event_id", "subject_id", "event_type", "surface", "locale",
            "occurred_at", "content")
    return dict(zip(keys, row))

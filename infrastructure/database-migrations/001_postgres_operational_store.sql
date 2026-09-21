-- Operational store schema (§6.2 PostgreSQL: "Stores consent state, ingestion
-- status, tool audit, experiments, feedback, and deletion jobs.")
BEGIN;

CREATE TABLE IF NOT EXISTS consent_state (
    subject_id      TEXT PRIMARY KEY,
    consent_state   TEXT NOT NULL CHECK (consent_state IN ('granted','denied','partial')),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ingestion_status (
    event_id        TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL,
    status          TEXT NOT NULL,          -- accepted | rejected | processed
    rejection_code  TEXT,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ingestion_idempotency ON ingestion_status(idempotency_key);

CREATE TABLE IF NOT EXISTS tool_audit (
    id              BIGSERIAL PRIMARY KEY,
    tool_name       TEXT NOT NULL,
    subject_id      TEXT NOT NULL,
    input_summary   JSONB NOT NULL DEFAULT '{}',
    outcome         TEXT NOT NULL,
    called_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiments (
    subject_id      TEXT NOT NULL,
    experiment_name TEXT NOT NULL,
    cohort          TEXT NOT NULL CHECK (cohort IN ('memory_enabled','memory_disabled')),
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (subject_id, experiment_name)
);

CREATE TABLE IF NOT EXISTS feedback (
    id              BIGSERIAL PRIMARY KEY,
    trace_id        TEXT NOT NULL,
    subject_id      TEXT NOT NULL,
    memory_id       TEXT,
    feedback_type   TEXT NOT NULL,
    comment         TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deletion_jobs (
    job_id              TEXT PRIMARY KEY,
    memory_id           TEXT NOT NULL,
    status              TEXT NOT NULL,      -- in_progress | completed | partial_failure
    store_status        JSONB NOT NULL DEFAULT '{}',
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ
);

COMMIT;

-- Rollback:
-- BEGIN;
-- DROP TABLE IF EXISTS deletion_jobs, feedback, experiments, tool_audit, ingestion_status, consent_state;
-- COMMIT;

"""Check every endpoint exists and responds.

These tests do not need the server running. TestClient starts the app
in-process, sends a real request, and gives back the real response.

Every endpoint except /health needs a token — see tests/test_auth.py for
the authentication and cross-subject isolation rules themselves.
"""

from fastapi.testclient import TestClient

from memory.api import app
from memory.auth import mint_token

client = TestClient(app)

AUTH = {"Authorization": f"Bearer {mint_token('user_001', 'chat-surface')}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# --- Write path -----------------------------------------------------------

def test_create_event():
    # Fully validated against the Event model — see tests/test_events.py
    # for the full behaviour of this endpoint.
    r = client.post(
        "/v1/events",
        json={
            "schema_version": "1.0",
            "subject_id": "user_001",
            "event_type": "playback",
            "surface": "player",
            "locale": "en-US",
            "occurred_at": "2026-09-23T10:00:00Z",
            "consent_state": "granted",
            "source_event_id": "src_api",
            "idempotency_key": "test_api_key",
        },
        headers=AUTH,
    )
    assert r.status_code == 200
    assert r.json()["accepted"] is True


def test_extract_memories():
    # Now a typed request needing subject_id and event_id, and the event
    # must exist. See tests/test_extract_api.py for its real behaviour.
    r = client.post(
        "/v1/memories/extract",
        json={"subject_id": "user_001", "event_id": "evt_does_not_exist"},
        headers=AUTH,
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_create_memory():
    r = client.post("/v1/memories", json={"subject_id": "user_001"}, headers=AUTH)
    assert r.status_code == 200
    assert "memory_id" in r.json()


# --- Read path ------------------------------------------------------------

def test_search_memories():
    r = client.post("/v1/memories/search", json={"subject_id": "user_001"}, headers=AUTH)
    assert r.status_code == 200
    assert "results" in r.json()


def test_compose_context():
    r = client.post("/v1/context/compose", json={"subject_id": "user_001"}, headers=AUTH)
    assert r.status_code == 200
    assert "context" in r.json()


# --- Correction and deletion ---------------------------------------------

def test_update_memory():
    r = client.patch("/v1/memories/mem_1", json={"statement": "corrected"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["memory_id"] == "mem_1"


def test_delete_memory():
    r = client.delete("/v1/memories/mem_1", headers=AUTH)
    assert r.status_code == 200
    assert "job_id" in r.json()


def test_get_deletion():
    r = client.get("/v1/deletions/job_1", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["job_id"] == "job_1"


# --- Feedback and explainability -----------------------------------------

def test_create_feedback():
    r = client.post("/v1/feedback", json={"rating": "good"}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["recorded"] is True


def test_get_trace():
    r = client.get("/v1/traces/trc_1", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["trace_id"] == "trc_1"

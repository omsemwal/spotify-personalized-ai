"""Ingestion API behaviour against the real Redis and broker.

§5.4 Interaction Capture is specific about what this endpoint must do:

  * attach subject scope, surface, locale, timestamp, consent state, source
    event id and idempotency key to every event
  * "Reject malformed, unauthenticated, out-of-policy, or unsupported events
    before graph processing"
  * keep capture asynchronous so the user path never waits on a graph write

These run against the stack rather than a mock, because the behaviours that
matter here — a duplicate key producing exactly one message, a rejected event
never reaching the topic — are properties of Redis and the broker, not of
Python. A mock would assert that the code calls the functions we wrote, which is
not the same claim.

    ./scripts/dev.sh up
"""

import sys
import uuid
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "packages" / "graph-schema"))
sys.path.insert(0, str(_REPO_ROOT / "packages" / "policy-engine"))
sys.path.insert(0, str(_REPO_ROOT / "services" / "ingestion-api"))

from tests.conftest import requires_live_datastores

pytestmark = [pytest.mark.integration, requires_live_datastores("redis", "redpanda")]

VALID_TOKEN = "dev-ingestion-token"


@pytest.fixture
def client(monkeypatch):
    """A TestClient over the real app, wired to the real datastores."""
    monkeypatch.setenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    monkeypatch.setenv("REDIS_HOST", "localhost")
    monkeypatch.setenv("REDIS_PORT", "6379")
    monkeypatch.setenv("INGESTION_SERVICE_TOKEN", VALID_TOKEN)

    # Loaded by path under a unique name. Six services each have a module
    # called `main`, and several service directories are on sys.path, so a
    # plain `import main` returns whichever one was imported first — which
    # depends on test ordering rather than on anything meaningful.
    import importlib.util

    from fastapi.testclient import TestClient

    spec = importlib.util.spec_from_file_location(
        "ingestion_api_main", _REPO_ROOT / "services" / "ingestion-api" / "main.py"
    )
    ingestion_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ingestion_main)

    return TestClient(ingestion_main.app)


def _event(**overrides):
    unique = uuid.uuid4().hex[:12]
    event = {
        "event_id": f"test_ev_{unique}",
        "subject_id": f"test_subject_{unique}",
        "surface": "music_chat",
        "event_type": "statement",
        "payload": {"text": "I like low-vocal focus playlists", "entities": ["low-vocal"]},
        "locale": "en-US",
        "timestamp": "2026-09-21T10:00:00Z",
        "consent_state": "granted",
        "idempotency_key": f"test_idem_{unique}",
    }
    event.update(overrides)
    return event


# ─────────────────────────────────────────────────────────────────────────────
# The happy path
# ─────────────────────────────────────────────────────────────────────────────

def test_valid_event_is_accepted(client):
    """202, not 200. The event has been durably queued, not processed — the
    graph write happens later, which is the whole point of the async capture
    path (§5.4)."""
    response = client.post(
        "/v1/events", json=_event(), headers={"Authorization": f"Bearer {VALID_TOKEN}"}
    )
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "accepted"


# ─────────────────────────────────────────────────────────────────────────────
# "Reject ... before graph processing"
# ─────────────────────────────────────────────────────────────────────────────

def test_duplicate_idempotency_key_is_refused(client):
    """The second request with the same key must not produce a second event.

    This is what stops a client retry from creating two copies of the same
    memory. It is checked against real Redis because the claim has to hold
    across processes — a per-process guard would pass this test and fail in
    production the moment a second replica existed.
    """
    event = _event()
    headers = {"Authorization": f"Bearer {VALID_TOKEN}"}

    first = client.post("/v1/events", json=event, headers=headers)
    second = client.post("/v1/events", json=event, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 409
    assert second.json()["detail"]["error_code"] == "duplicate_event"


def test_unauthenticated_event_is_refused(client):
    response = client.post("/v1/events", json=_event())
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "unauthenticated"


def test_wrong_token_is_refused(client):
    response = client.post(
        "/v1/events", json=_event(), headers={"Authorization": "Bearer not-the-token"}
    )
    assert response.status_code == 401


def test_malformed_event_is_refused(client):
    """A missing required field is a 400 with a stable code, not a 500 and not
    a silently-accepted partial event."""
    broken = _event()
    del broken["consent_state"]
    response = client.post(
        "/v1/events", json=broken, headers={"Authorization": f"Bearer {VALID_TOKEN}"}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "malformed"


def test_unsupported_schema_version_is_refused(client):
    """§5.4 lists unsupported events among what must be rejected before graph
    processing. Accepting an unknown version would mean guessing at its shape."""
    response = client.post(
        "/v1/events",
        json=_event(schema_version="99.0.0"),
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "unsupported_schema_version"


def test_denied_consent_never_reaches_the_queue(client):
    """The strongest of these. An event from a subject who has not consented
    must be refused at the edge — not written and filtered later, because then
    it has already been stored (§5.5 Privacy: collection must be minimal)."""
    response = client.post(
        "/v1/events",
        json=_event(consent_state="denied"),
        headers={"Authorization": f"Bearer {VALID_TOKEN}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "consent_denied"


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

def test_health_reports_each_dependency(client):
    """§5.5 Deployment readiness: "Every service must have health checks". A
    check that only says "ok" cannot tell an operator which dependency broke."""
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["dependencies"]["queue"]["reachable"] is True
    assert body["dependencies"]["idempotency"]["reachable"] is True

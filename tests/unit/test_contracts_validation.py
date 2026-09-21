"""Unit: contracts reject malformed input (§7.7 Functional: 'Event validation')."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from pydantic import ValidationError

from packages.contracts import InteractionEvent, Memory


def test_interaction_event_rejects_missing_consent():
    with pytest.raises(ValidationError):
        InteractionEvent(
            event_id="e1", subject_id="u1", surface="music_chat", event_type="play",
            payload={}, locale="en-US", timestamp="2026-01-01T00:00:00Z",
            idempotency_key="k1",
        )  # consent_state omitted -> should fail


def test_interaction_event_accepts_valid_payload():
    e = InteractionEvent(
        event_id="e1", subject_id="u1", surface="music_chat", event_type="play",
        payload={}, locale="en-US", timestamp="2026-01-01T00:00:00Z",
        consent_state="granted", idempotency_key="k1",
    )
    assert e.event_id == "e1"


def test_memory_confidence_bounds_enforced():
    with pytest.raises(ValidationError):
        Memory(
            memory_id="m1", subject_id="u1", fact_text="x", memory_type="episode",
            entities=[], confidence=1.5, source_event_id="e1",
            valid_from="2026-01-01T00:00:00Z", recorded_at="2026-01-01T00:00:00Z",
        )  # confidence > 1.0 must fail

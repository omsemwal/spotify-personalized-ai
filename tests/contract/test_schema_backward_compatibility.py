"""Contract: SCHEMA_VERSION must not silently change without a matching test
update (§5.5 Maintainability: 'Memory schemas... must be versioned and
independently testable'). This test pins the CURRENT expected version — bump
it deliberately, in the same PR that bumps packages/contracts/events.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from packages.contracts import SCHEMA_VERSION


def test_schema_version_is_pinned():
    assert SCHEMA_VERSION == "1.0.0", (
        "SCHEMA_VERSION changed — confirm all consuming services "
        "(ingestion-api's version check) were updated in the same change."
    )


def test_interaction_event_required_fields_unchanged():
    from packages.contracts import InteractionEvent
    required = InteractionEvent.model_fields.keys()
    expected_minimum = {
        "event_id", "subject_id", "surface", "event_type", "timestamp",
        "consent_state", "idempotency_key",
    }
    assert expected_minimum.issubset(set(required)), "a required field was removed — breaking change"

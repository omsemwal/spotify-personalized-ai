"""Unit: PolicyEngine write/retrieval eligibility (§5.4 policy tests)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "policy-engine"))

from engine import PolicyContext, PolicyEngine


def test_consent_denied_blocks_write():
    engine = PolicyEngine()
    ctx = PolicyContext(consent_state="denied", surface_policy=["personalization"])
    allowed, codes = engine.evaluate_write("explicit_preference", ctx)
    assert not allowed
    assert "consent_denied" in codes


def test_blocked_inferred_category_rejected():
    engine = PolicyEngine()
    ctx = PolicyContext(consent_state="granted", surface_policy=["personalization"], inferred_category="emotional_state")
    allowed, codes = engine.evaluate_write("candidate_preference", ctx)
    assert not allowed
    assert "blocked_sensitive_inference" in codes


def test_low_confidence_excluded_at_retrieval():
    engine = PolicyEngine()
    ctx = PolicyContext(consent_state="granted", surface_policy=["personalization"])
    memory = {"status": "active", "memory_type": "episode", "confidence": 0.1,
              "recorded_at": "2026-01-01T00:00:00", "surface": None}
    allowed, codes = engine.evaluate_retrieval(memory, ctx)
    assert not allowed
    assert "low_confidence" in codes

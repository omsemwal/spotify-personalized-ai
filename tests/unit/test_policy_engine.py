"""Unit tests for the PolicyEngine — the gate for §5.4 "User Control, Privacy,
and Safety".

These are table-driven on purpose. The policy rules are data
(`packages/policy-engine/policy_registry.yaml`), so the tests are data too, and
adding a rule means adding a row rather than writing another near-identical
test function.

Three things are checked:

  1. Every decision the engine can make, in both directions (allowed and
     refused), for every memory type.
  2. That every refusal carries a stable reason code. §7.3 requires stable
     error codes; the operations console groups on them and the web apps map
     them to user-facing text, so an unnamed refusal is unusable downstream.
  3. That the registry file, the engine's code constants, and
     docs/architecture/memory_taxonomy.md all agree on the same five types.
"""

import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "packages" / "policy-engine"))

import engine as engine_module
from engine import PolicyContext, PolicyEngine
from registry import PolicyRegistryError, load_registry

ALL_TYPES = ["explicit_preference", "exclusion", "correction", "candidate_preference", "episode"]
EXPLICIT_TYPES = ["explicit_preference", "exclusion", "correction"]

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def policy():
    return PolicyEngine()


def _memory(memory_type="explicit_preference", **overrides):
    """A memory that is eligible by default, so each test changes exactly one
    thing and the reason for a refusal is unambiguous."""
    base = {
        "memory_id": "mem_test",
        "subject_id": "user_001",
        "memory_type": memory_type,
        "fact_text": "prefers low-vocal music while working",
        "confidence": 0.9,
        "status": "active",
        "recorded_at": (NOW - timedelta(days=1)).isoformat(),
        "valid_to": None,
    }
    base.update(overrides)
    return base


def _granted(**overrides):
    ctx = PolicyContext(
        consent_state="granted",
        surface_policy=["continuity", "personalization", "correction", "safety"],
    )
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# Write decisions
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("memory_type", ALL_TYPES)
def test_write_allowed_for_every_type_under_full_consent(policy, memory_type):
    """The baseline. If this fails, every refusal test below is meaningless."""
    allowed, codes = policy.evaluate_write(memory_type, _granted())
    assert allowed, f"{memory_type} should be writable under full consent, got {codes}"
    assert codes == []


WRITE_REFUSALS = [
    # (label, memory_type, context kwargs, expected reason code)
    ("consent denied blocks everything", "explicit_preference",
     {"consent_state": "denied"}, "consent_denied"),
    ("opt-out blocks capture", "explicit_preference",
     {"opted_out": True}, "subject_opted_out"),
    ("prohibited inference is refused", "candidate_preference",
     {"inferred_category": "emotional_state"}, "blocked_sensitive_inference"),
    ("mood inference is refused", "candidate_preference",
     {"inferred_category": "mood_inference"}, "blocked_sensitive_inference"),
    ("medical inference is refused", "explicit_preference",
     {"inferred_category": "medical_inference"}, "blocked_sensitive_inference"),
    ("partial consent refuses inferred types", "candidate_preference",
     {"consent_state": "partial"}, "consent_partial_type_not_allowed"),
    ("partial consent refuses episodes", "episode",
     {"consent_state": "partial"}, "consent_partial_type_not_allowed"),
    ("minors: no inferred preferences", "candidate_preference",
     {"is_minor": True}, "minor_restricted"),
    ("minors: no behavioural episodes", "episode",
     {"is_minor": True}, "minor_restricted"),
    ("an unassessed region is refused, not defaulted", "explicit_preference",
     {"region": "ATLANTIS"}, "unknown_region"),
]


@pytest.mark.parametrize(
    "label,memory_type,ctx_kwargs,expected_code",
    WRITE_REFUSALS,
    ids=[row[0] for row in WRITE_REFUSALS],
)
def test_write_refusals(policy, label, memory_type, ctx_kwargs, expected_code):
    allowed, codes = policy.evaluate_write(memory_type, _granted(**ctx_kwargs))
    assert not allowed, f"{label}: expected refusal, was allowed"
    assert expected_code in codes, f"{label}: expected {expected_code!r}, got {codes}"


@pytest.mark.parametrize("memory_type", EXPLICIT_TYPES)
def test_partial_consent_still_allows_what_the_user_said_outright(policy, memory_type):
    """Partial consent is not the same as denial. It keeps what the user stated
    and drops what we inferred — that distinction is the whole point of the
    setting."""
    allowed, codes = policy.evaluate_write(memory_type, _granted(consent_state="partial"))
    assert allowed, f"{memory_type} should survive partial consent, got {codes}"


@pytest.mark.parametrize("memory_type", EXPLICIT_TYPES)
def test_minors_keep_their_explicit_statements(policy, memory_type):
    """Age protection restricts inference about a minor, not their own stated
    choices. A minor who says "no true crime" must still have that honoured."""
    allowed, codes = policy.evaluate_write(memory_type, _granted(is_minor=True))
    assert allowed, f"{memory_type} should be writable for a minor, got {codes}"


def test_pause_does_not_block_capture(policy):
    """§5.3 defines pause as revoking *retrieval* eligibility. Capture keeps
    running, which is what makes pause reversible without leaving a hole in the
    history. Opt-out is the control that stops capture."""
    allowed, _ = policy.evaluate_write("explicit_preference", _granted(memory_paused=True))
    assert allowed, "pause should stop memory being used, not stop it being recorded"


def test_unknown_memory_type_is_refused(policy):
    """This is the shape of a model inventing a type (§7.5 Validation)."""
    allowed, codes = policy.evaluate_write("favourite_colour", _granted())
    assert not allowed
    assert "unknown_memory_type" in codes


def test_all_applicable_reasons_are_reported_not_just_the_first(policy):
    """The operations console shows why something was refused. Returning on the
    first match would hide the rest and make a refusal look simpler than it is."""
    ctx = _granted(consent_state="denied", opted_out=True, inferred_category="emotional_state")
    allowed, codes = policy.evaluate_write("candidate_preference", ctx)
    assert not allowed
    assert {"consent_denied", "subject_opted_out", "blocked_sensitive_inference"}.issubset(set(codes))


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval decisions
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("memory_type", ALL_TYPES)
def test_retrieval_allowed_for_every_type_by_default(policy, memory_type):
    allowed, codes = policy.evaluate_retrieval(_memory(memory_type), _granted(), now=NOW)
    assert allowed, f"{memory_type} should be retrievable, got {codes}"


RETRIEVAL_REFUSALS = [
    # (label, memory overrides, context kwargs, expected code)
    ("superseded memory is not used", {"status": "superseded"}, {}, "status_superseded"),
    ("expired memory is not used", {"status": "expired"}, {}, "status_expired"),
    ("deleted memory is not used", {"status": "deleted"}, {}, "status_deleted"),
    ("low confidence is filtered", {"confidence": 0.1}, {}, "low_confidence"),
    ("consent withdrawn after the write", {}, {"consent_state": "denied"}, "consent_denied"),
    ("paused memory is not used", {}, {"memory_paused": True}, "memory_paused"),
    ("opted-out subject gets nothing", {}, {"opted_out": True}, "subject_opted_out"),
    ("surface without a matching purpose", {}, {"surface_policy": ["advertising"]}, "surface_ineligible"),
    ("closed valid-time beats retention", {"valid_to": (NOW - timedelta(days=1)).isoformat()}, {},
     "retention_expired"),
    ("past retention for the type", {"recorded_at": (NOW - timedelta(days=400)).isoformat()}, {},
     "retention_expired"),
]


@pytest.mark.parametrize(
    "label,mem_overrides,ctx_kwargs,expected_code",
    RETRIEVAL_REFUSALS,
    ids=[row[0] for row in RETRIEVAL_REFUSALS],
)
def test_retrieval_refusals(policy, label, mem_overrides, ctx_kwargs, expected_code):
    allowed, codes = policy.evaluate_retrieval(
        _memory(**mem_overrides), _granted(**ctx_kwargs), now=NOW
    )
    assert not allowed, f"{label}: expected refusal, was allowed"
    assert expected_code in codes, f"{label}: expected {expected_code!r}, got {codes}"


def test_episodes_age_out_faster_than_stated_preferences(policy):
    """Retention differs by type (30 days vs 365). An episode and a preference
    recorded on the same day must not expire on the same day."""
    recorded = {"recorded_at": (NOW - timedelta(days=60)).isoformat()}
    ep_allowed, ep_codes = policy.evaluate_retrieval(_memory("episode", **recorded), _granted(), now=NOW)
    pref_allowed, _ = policy.evaluate_retrieval(
        _memory("explicit_preference", **recorded), _granted(), now=NOW
    )
    assert not ep_allowed and "retention_expired" in ep_codes
    assert pref_allowed, "a 60-day-old stated preference is well inside its 365-day retention"


def test_regional_cap_shortens_retention_and_never_extends_it(policy):
    """§5.4 lists geography as a retention input. A region may only shorten."""
    assert policy.retention_days_for("explicit_preference", "GLOBAL") == 365
    assert policy.retention_days_for("explicit_preference", "EU") == 180

    old = _memory(recorded_at=(NOW - timedelta(days=200)).isoformat())
    eu_allowed, eu_codes = policy.evaluate_retrieval(old, _granted(region="EU"), now=NOW)
    global_allowed, _ = policy.evaluate_retrieval(old, _granted(region="GLOBAL"), now=NOW)
    assert not eu_allowed and "retention_expired" in eu_codes
    assert global_allowed


def test_consent_narrowed_after_the_write_takes_effect_on_existing_memories(policy):
    """A memory written under full consent must stop being used when the user
    narrows consent. §5.5 Privacy: retrieval must be "reversible"."""
    mem = _memory("candidate_preference")
    assert policy.evaluate_retrieval(mem, _granted(), now=NOW)[0]
    allowed, codes = policy.evaluate_retrieval(mem, _granted(consent_state="partial"), now=NOW)
    assert not allowed
    assert "consent_partial_type_not_allowed" in codes


def test_correction_is_never_filtered_for_low_confidence(policy):
    """A correction is the user exercising control. Suppressing it would mean
    continuing to use the thing they just told us was wrong."""
    allowed, codes = policy.evaluate_retrieval(
        _memory("correction", confidence=0.0), _granted(), now=NOW
    )
    assert allowed, f"a correction must survive any confidence value, got {codes}"


def test_unparseable_timestamp_does_not_silently_hide_a_memory(policy):
    """A malformed timestamp is a data-quality problem for the write path. It
    must not cause a memory the user can see in their own list to vanish from
    retrieval with no explanation."""
    allowed, codes = policy.evaluate_retrieval(
        _memory(recorded_at="not-a-date"), _granted(), now=NOW
    )
    assert allowed, f"expected the retention check to be skipped, got {codes}"


def test_naive_and_aware_timestamps_are_treated_identically(policy):
    """Services write timestamps both ways. Retention arithmetic must not
    depend on which one arrived."""
    naive = (NOW - timedelta(days=10)).replace(tzinfo=None).isoformat()
    aware = (NOW - timedelta(days=10)).isoformat()
    assert policy.evaluate_retrieval(_memory(recorded_at=naive), _granted(), now=NOW) == \
           policy.evaluate_retrieval(_memory(recorded_at=aware), _granted(), now=NOW)


# ─────────────────────────────────────────────────────────────────────────────
# Reason codes are a contract
# ─────────────────────────────────────────────────────────────────────────────

def test_every_refusal_returns_at_least_one_code(policy):
    """A refusal with no reason cannot be shown to a user or grouped in the
    console. Sweeps every refusal case defined above."""
    for _label, memory_type, ctx_kwargs, _expected in WRITE_REFUSALS:
        allowed, codes = policy.evaluate_write(memory_type, _granted(**ctx_kwargs))
        assert not allowed and codes, f"write refusal produced no reason code: {ctx_kwargs}"
    for _label, mem_overrides, ctx_kwargs, _expected in RETRIEVAL_REFUSALS:
        allowed, codes = policy.evaluate_retrieval(
            _memory(**mem_overrides), _granted(**ctx_kwargs), now=NOW
        )
        assert not allowed and codes, f"retrieval refusal produced no reason code: {ctx_kwargs}"


def test_reason_codes_are_stable_identifiers():
    """These strings are consumed by the API, the console and both web apps.
    Keeping them lowercase snake_case is what lets them be used as map keys and
    translation ids rather than displayed raw."""
    codes = [
        value
        for name, value in vars(engine_module).items()
        if name.isupper() and isinstance(value, str) and not name.startswith("_")
    ]
    assert codes, "no reason codes found — did the constants get renamed?"
    for code in codes:
        assert re.fullmatch(r"[a-z][a-z0-9_]*", code), f"{code!r} is not a stable snake_case identifier"


def test_allowed_decisions_carry_no_codes(policy):
    """An allow must be unambiguous. A code alongside `allowed=True` would leave
    a caller unsure whether to use the memory."""
    allowed, codes = policy.evaluate_retrieval(_memory(), _granted(), now=NOW)
    assert allowed and codes == []


# ─────────────────────────────────────────────────────────────────────────────
# The registry file itself
# ─────────────────────────────────────────────────────────────────────────────

def test_registry_defines_exactly_the_taxonomy_types():
    """The YAML registry, the engine and the taxonomy document must not drift
    apart. Widening the taxonomy is a governed change (§7.5), and silently
    adding a type in one place only is exactly how that gets bypassed."""
    registry = load_registry()
    assert set(registry.entries) == set(ALL_TYPES)

    taxonomy = (_REPO_ROOT / "docs" / "architecture" / "memory_taxonomy.md").read_text(encoding="utf-8")
    for memory_type in ALL_TYPES:
        assert f"`{memory_type}`" in taxonomy, (
            f"{memory_type} is in the policy registry but not documented in memory_taxonomy.md"
        )


def test_registry_rejects_a_type_missing_a_required_key(tmp_path):
    """A half-specified memory type must fail loudly at load. Defaulting the
    missing key would mean a type quietly getting the most permissive setting."""
    bad = tmp_path / "policy_registry.yaml"
    bad.write_text(
        "version: '1.0.0'\n"
        "memory_types:\n"
        "  episode:\n"
        "    sensitivity: normal\n"      # everything else missing
        "subject_controls:\n"
        "  paused: {blocks_retrieval: true, blocks_write: false}\n"
        "  opted_out: {blocks_retrieval: true, blocks_write: true}\n"
        "regions:\n"
        "  GLOBAL: {max_retention_days: null}\n",
        encoding="utf-8",
    )
    load_registry.cache_clear()
    try:
        with pytest.raises(PolicyRegistryError, match="missing key"):
            load_registry(bad)
    finally:
        load_registry.cache_clear()


def test_registry_must_exist(tmp_path):
    """No policy file means nothing is enforcing consent, retention or
    sensitivity. That has to stop a service starting, not be survivable."""
    load_registry.cache_clear()
    try:
        with pytest.raises(PolicyRegistryError, match="not found"):
            load_registry(tmp_path / "does_not_exist.yaml")
    finally:
        load_registry.cache_clear()


def test_blocked_inference_categories_are_loaded_from_the_registry():
    registry = load_registry()
    assert "emotional_state" in registry.blocked_inferred_categories
    assert "political_affiliation_inference" in registry.blocked_inferred_categories

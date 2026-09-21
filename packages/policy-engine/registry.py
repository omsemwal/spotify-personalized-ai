"""
Policy registry: allowed memory types, sensitivity, purposes, retention, and
retrieval eligibility. Spec ref: §5.4 "Data Governance Lead" requirement —
"a data catalog entry for each memory type: source, lawful basis or internal
policy basis, allowed purposes, sensitivity, retention period, and deletion path."

Any change to this registry is a governed change (§7.5 "Human review: require
policy or data-governance approval for new memory types, sensitive categories,
and scoring-rule changes").
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PolicyRegistryEntry:
    memory_type: str
    sensitivity: str            # "normal" | "sensitive" | "blocked"
    allowed_purposes: list[str] = field(default_factory=list)
    retention_days: int = 180
    requires_explicit_confirmation: bool = False


# The taxonomy is intentionally narrow for the pilot (§4: "Do not widen the
# stored-memory taxonomy until the evaluation data supports it.")
REGISTRY = {
    "episode": PolicyRegistryEntry(
        memory_type="episode", sensitivity="normal",
        allowed_purposes=["continuity", "personalization"],
        retention_days=30, requires_explicit_confirmation=False,
    ),
    "explicit_preference": PolicyRegistryEntry(
        memory_type="explicit_preference", sensitivity="normal",
        allowed_purposes=["continuity", "personalization", "correction"],
        retention_days=365, requires_explicit_confirmation=False,
    ),
    "candidate_preference": PolicyRegistryEntry(
        memory_type="candidate_preference", sensitivity="normal",
        allowed_purposes=["personalization"],
        retention_days=90, requires_explicit_confirmation=True,
    ),
    "exclusion": PolicyRegistryEntry(
        memory_type="exclusion", sensitivity="normal",
        allowed_purposes=["personalization", "safety"],
        retention_days=365, requires_explicit_confirmation=False,
    ),
    "correction": PolicyRegistryEntry(
        memory_type="correction", sensitivity="normal",
        allowed_purposes=["continuity", "correction"],
        retention_days=365, requires_explicit_confirmation=False,
    ),
}

# Explicitly blocked inference categories (§5.4 Privacy Lead requirement:
# "We should not store inferred emotional state as a durable profile by default.")
BLOCKED_INFERRED_CATEGORIES = {
    "emotional_state", "mood_inference", "mental_health_inference",
    "medical_inference", "political_affiliation_inference",
}

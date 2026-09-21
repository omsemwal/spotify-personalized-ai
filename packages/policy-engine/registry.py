"""
Loads the policy registry from `policy_registry.yaml`.

Spec ref: §4 Data Governance Lead — "a data catalog entry for each memory type:
source, lawful basis or internal policy basis, allowed purposes, sensitivity,
retention period, and deletion path"; §7.5 — changes to it require policy or
data-governance approval.

Why the rules live in YAML rather than in this file: a policy change should be
reviewable by someone who does not read Python. This module only loads and
validates; it holds no policy of its own. If you find yourself adding a rule
here, it belongs in the YAML.

The module fails loudly on a malformed or missing registry. There is no default
policy to fall back to — a service that cannot read its policy rules must not
start, because the failure mode would be a system that silently stops enforcing
them.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_REGISTRY_PATH = Path(__file__).parent / "policy_registry.yaml"

# Every memory type must define these. Missing one is a configuration error, not
# something to paper over with a default.
_REQUIRED_TYPE_KEYS = {
    "sensitivity",
    "allowed_purposes",
    "retention_days",
    "requires_explicit_confirmation",
    "minimum_confidence",
    "allowed_under_partial_consent",
    "allowed_for_minors",
    "restricted_regions",
}


class PolicyRegistryError(RuntimeError):
    """The registry file is missing, malformed, or internally inconsistent."""


@dataclass(frozen=True)
class PolicyRegistryEntry:
    """One memory type's catalog entry."""

    memory_type: str
    sensitivity: str  # "normal" | "sensitive" | "blocked"
    allowed_purposes: list[str] = field(default_factory=list)
    retention_days: int = 180
    requires_explicit_confirmation: bool = False
    minimum_confidence: float = 0.30
    allowed_under_partial_consent: bool = False
    allowed_for_minors: bool = False
    restricted_regions: list[str] = field(default_factory=list)
    description: str = ""
    basis: str = ""


@dataclass(frozen=True)
class SubjectControlRule:
    blocks_retrieval: bool
    blocks_write: bool


@dataclass(frozen=True)
class PolicyRegistry:
    """The whole registry, loaded once and treated as immutable."""

    version: str
    entries: dict[str, PolicyRegistryEntry]
    blocked_inferred_categories: frozenset[str]
    paused: SubjectControlRule
    opted_out: SubjectControlRule
    region_retention_caps: dict[str, int | None]
    usable_status: str

    def get(self, memory_type: str | None) -> PolicyRegistryEntry | None:
        """Entry for a type, or None if the type is not in the registry.

        Returning None rather than raising is deliberate: an unknown type is a
        policy decision (refuse it, with the code `unknown_memory_type`), not a
        crash. It is exactly what an LLM inventing a type looks like.
        """
        if memory_type is None:
            return None
        return self.entries.get(memory_type)

    def effective_retention_days(self, memory_type: str, region: str = "GLOBAL") -> int:
        """Retention for a type in a region — the shorter of the two limits.

        §5.4: "Apply retention by memory type, geography, age-related policy,
        consent state, and legal or internal governance requirements." A region
        may only shorten retention, never extend it.
        """
        entry = self.get(memory_type)
        base = entry.retention_days if entry else 30
        cap = self.region_retention_caps.get(region)
        if cap is None:
            return base
        return min(base, cap)

    def known_regions(self) -> set[str]:
        return set(self.region_retention_caps)


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise PolicyRegistryError(f"{where}: missing required key {key!r}")
    return mapping[key]


def _parse(raw: dict[str, Any]) -> PolicyRegistry:
    types_raw = _require(raw, "memory_types", "registry root")
    if not types_raw:
        raise PolicyRegistryError("registry defines no memory types")

    entries: dict[str, PolicyRegistryEntry] = {}
    for name, spec in types_raw.items():
        missing = sorted(_REQUIRED_TYPE_KEYS - set(spec))
        if missing:
            raise PolicyRegistryError(f"memory type {name!r}: missing key(s) {missing}")
        entries[name] = PolicyRegistryEntry(
            memory_type=name,
            sensitivity=spec["sensitivity"],
            allowed_purposes=list(spec["allowed_purposes"]),
            retention_days=int(spec["retention_days"]),
            requires_explicit_confirmation=bool(spec["requires_explicit_confirmation"]),
            minimum_confidence=float(spec["minimum_confidence"]),
            allowed_under_partial_consent=bool(spec["allowed_under_partial_consent"]),
            allowed_for_minors=bool(spec["allowed_for_minors"]),
            restricted_regions=list(spec["restricted_regions"]),
            description=spec.get("description", ""),
            basis=spec.get("basis", ""),
        )

    controls = _require(raw, "subject_controls", "registry root")
    paused_raw = _require(controls, "paused", "subject_controls")
    opted_out_raw = _require(controls, "opted_out", "subject_controls")

    regions_raw = _require(raw, "regions", "registry root")
    caps: dict[str, int | None] = {}
    for region, spec in regions_raw.items():
        cap = (spec or {}).get("max_retention_days")
        caps[region] = None if cap is None else int(cap)
    if "GLOBAL" not in caps:
        raise PolicyRegistryError("regions must define GLOBAL as the default region")

    return PolicyRegistry(
        version=str(_require(raw, "version", "registry root")),
        entries=entries,
        blocked_inferred_categories=frozenset(raw.get("blocked_inferred_categories") or []),
        paused=SubjectControlRule(
            blocks_retrieval=bool(_require(paused_raw, "blocks_retrieval", "subject_controls.paused")),
            blocks_write=bool(_require(paused_raw, "blocks_write", "subject_controls.paused")),
        ),
        opted_out=SubjectControlRule(
            blocks_retrieval=bool(_require(opted_out_raw, "blocks_retrieval", "subject_controls.opted_out")),
            blocks_write=bool(_require(opted_out_raw, "blocks_write", "subject_controls.opted_out")),
        ),
        region_retention_caps=caps,
        usable_status=str((raw.get("retrieval") or {}).get("usable_status", "active")),
    )


@lru_cache(maxsize=1)
def load_registry(path: Path | None = None) -> PolicyRegistry:
    """Read and validate the registry. Cached — it is immutable configuration.

    Call `load_registry.cache_clear()` in a test that points at a different
    file.
    """
    registry_path = path or _REGISTRY_PATH
    if not registry_path.exists():
        raise PolicyRegistryError(
            f"policy registry not found at {registry_path}. Services must not start without it — "
            "a missing registry means nothing is enforcing consent, retention or sensitivity."
        )
    try:
        raw = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PolicyRegistryError(f"policy registry at {registry_path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise PolicyRegistryError(f"policy registry at {registry_path} must be a YAML mapping")
    return _parse(raw)


# ── Backwards-compatible module-level names ─────────────────────────────────
# Existing imports (`from registry import REGISTRY, BLOCKED_INFERRED_CATEGORIES`)
# keep working. New code should call load_registry() and use the richer object.
REGISTRY: dict[str, PolicyRegistryEntry] = load_registry().entries
BLOCKED_INFERRED_CATEGORIES: frozenset[str] = load_registry().blocked_inferred_categories

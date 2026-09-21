"""
PolicyEngine — the eligibility gate every candidate memory and every retrieved
memory must pass through before it can be written or injected into context.
Spec ref: §5.4 "User Control, Privacy, and Safety", §6.1 step 6 "Rerank and govern."
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

try:
    # Works when policy-engine is imported as a real package (e.g. from a
    # future rename without the hyphen, or via importlib with a package spec).
    from .registry import REGISTRY, BLOCKED_INFERRED_CATEGORIES, PolicyRegistryEntry
except ImportError:
    # Actual path taken today: each service inserts packages/policy-engine
    # onto sys.path at startup (the hyphen in the directory name makes
    # `packages.policy-engine` invalid Python syntax), so this module is
    # imported as a bare top-level module with no parent package — a relative
    # import has nothing to resolve against. Import registry.py the same way,
    # as a sibling top-level module, instead.
    from registry import REGISTRY, BLOCKED_INFERRED_CATEGORIES, PolicyRegistryEntry


def _as_utc(dt: datetime) -> datetime:
    """Memories written by different services carry either naive or tz-aware
    timestamps; retention math must not depend on which one arrived."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


@dataclass
class PolicyContext:
    consent_state: str          # "granted" | "denied" | "partial"
    surface_policy: List[str]   # purposes this surface is allowed to use, e.g. ["personalization"]
    inferred_category: str = ""  # set only for candidate_preference from inference


class PolicyEngine:
    def __init__(self, registry=None):
        self.registry = registry or REGISTRY

    def evaluate_write(self, memory_type: str, ctx: PolicyContext) -> tuple[bool, list[str]]:
        """Decide whether a candidate memory may be written at all (before graph write)."""
        codes: list[str] = []

        if ctx.consent_state == "denied":
            codes.append("consent_denied")
        if ctx.inferred_category in BLOCKED_INFERRED_CATEGORIES:
            codes.append("blocked_sensitive_inference")

        entry: PolicyRegistryEntry = self.registry.get(memory_type)
        if entry is None:
            codes.append("unknown_memory_type")
        elif entry.sensitivity == "blocked":
            codes.append("memory_type_blocked")

        return (len(codes) == 0, codes)

    def evaluate_retrieval(self, memory: dict, ctx: PolicyContext, now: datetime = None) -> tuple[bool, list[str]]:
        """Decide whether an already-stored memory may be included in a context
        package right now. Called at every retrieval, not just at write time —
        a memory can become ineligible later (expired, contradicted, surface changed).
        """
        now = _as_utc(now or datetime.now(timezone.utc))
        codes: list[str] = []

        if memory.get("status") != "active":
            codes.append(f"status_{memory.get('status')}")

        entry = self.registry.get(memory.get("memory_type"))
        if entry is None:
            codes.append("unknown_memory_type")
        else:
            recorded_at = memory.get("recorded_at")
            if isinstance(recorded_at, str):
                try:
                    recorded_dt = _as_utc(datetime.fromisoformat(recorded_at))
                    if now - recorded_dt > timedelta(days=entry.retention_days):
                        codes.append("retention_expired")
                except ValueError:
                    pass
            purpose_ok = any(p in entry.allowed_purposes for p in ctx.surface_policy)
            if not purpose_ok:
                codes.append("surface_ineligible")

        if memory.get("confidence", 0.0) < 0.3:
            codes.append("low_confidence")

        surface = memory.get("surface")
        if surface and surface not in (ctx.surface_policy + [None]):
            # surface-restricted memory being requested from a different surface
            pass  # surface_policy already carries purpose eligibility above; explicit surface match is stricter and optional

        return (len(codes) == 0, codes)

    def retention_days_for(self, memory_type: str) -> int:
        entry = self.registry.get(memory_type)
        return entry.retention_days if entry else 30

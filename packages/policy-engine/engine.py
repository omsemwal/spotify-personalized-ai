"""
PolicyEngine — the gate every candidate memory and every retrieved memory must
pass before it can be written or put in front of the model.

Spec ref: §5.4 "User Control, Privacy, and Safety"; §6.1 step 6 "Rerank and
govern"; §5.5 Privacy — "Collection and retrieval must be purpose-limited,
minimal, and reversible."

Two decisions, deliberately separate:

  evaluate_write      may this candidate become a stored memory at all?
  evaluate_retrieval  may this stored memory be used in THIS response?

Retrieval is re-evaluated on every request rather than cached with the memory,
because eligibility changes underneath a stored fact: it expires, it gets
contradicted, the user pauses memory or withdraws consent, or the request comes
from a surface with a narrower purpose. A memory that was legal to write is not
therefore legal to use.

Every refusal returns stable reason codes. §7.3 requires stable error codes, the
operations console groups by them, and the two web apps map them to the text a
user sees — so the string values below are a contract. Adding a code is fine;
renaming one is a breaking change.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

try:
    # Works when policy-engine is imported as a real package.
    from .registry import PolicyRegistry, PolicyRegistryEntry, load_registry
except ImportError:
    # Actual path taken today: each service inserts packages/policy-engine onto
    # sys.path at startup (the hyphen in the directory name makes
    # `packages.policy-engine` invalid Python syntax), so this module is
    # imported as a bare top-level module with no parent package — a relative
    # import has nothing to resolve against. Import registry.py the same way,
    # as a sibling top-level module, instead.
    from registry import PolicyRegistry, PolicyRegistryEntry, load_registry


# ─────────────────────────────────────────────────────────────────────────────
# Reason codes — a contract. See the module docstring.
# ─────────────────────────────────────────────────────────────────────────────
CONSENT_DENIED = "consent_denied"
CONSENT_PARTIAL_TYPE_NOT_ALLOWED = "consent_partial_type_not_allowed"
SUBJECT_OPTED_OUT = "subject_opted_out"
MEMORY_PAUSED = "memory_paused"
BLOCKED_SENSITIVE_INFERENCE = "blocked_sensitive_inference"
UNKNOWN_MEMORY_TYPE = "unknown_memory_type"
MEMORY_TYPE_BLOCKED = "memory_type_blocked"
REGION_RESTRICTED = "region_restricted"
MINOR_RESTRICTED = "minor_restricted"
RETENTION_EXPIRED = "retention_expired"
LOW_CONFIDENCE = "low_confidence"
SURFACE_INELIGIBLE = "surface_ineligible"
UNKNOWN_REGION = "unknown_region"


def _as_utc(dt: datetime) -> datetime:
    """Memories written by different services carry either naive or tz-aware
    timestamps; retention arithmetic must not depend on which one arrived."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


@dataclass
class PolicyContext:
    """Everything about the subject and the surface that a policy decision needs.

    The first two fields are positional for backward compatibility with existing
    call sites. The rest default to the most permissive value, so a caller that
    has not been updated behaves exactly as it did before — while a caller that
    passes real subject state gets the full set of checks.

    Where the values come from: consent, pause and opt-out live in the
    operational store (§6.2 PostgreSQL, "consent state"); region and age band
    come from the authenticated subject claim; surface_policy comes from the
    calling surface's registration.
    """

    consent_state: str  # "granted" | "denied" | "partial"
    surface_policy: list[str] = field(default_factory=list)
    inferred_category: str = ""  # set only when a candidate came from inference
    memory_paused: bool = False
    opted_out: bool = False
    region: str = "GLOBAL"
    is_minor: bool = False


class PolicyEngine:
    def __init__(self, registry: PolicyRegistry | None = None):
        self.registry: PolicyRegistry = registry or load_registry()

    # ── write ───────────────────────────────────────────────────────────────
    def evaluate_write(self, memory_type: str, ctx: PolicyContext) -> tuple[bool, list[str]]:
        """May this candidate be stored at all? Runs before the graph write.

        Every applicable reason is collected rather than returning on the first
        one, so the operations console can show the full picture instead of
        whichever check happened to run first.
        """
        codes: list[str] = []

        if ctx.consent_state == "denied":
            codes.append(CONSENT_DENIED)

        if ctx.opted_out and self.registry.opted_out.blocks_write:
            codes.append(SUBJECT_OPTED_OUT)

        if ctx.memory_paused and self.registry.paused.blocks_write:
            codes.append(MEMORY_PAUSED)

        # A prohibited inference is refused whatever type it arrives as, and
        # there is no configuration that permits it (§4 Privacy Lead).
        if ctx.inferred_category in self.registry.blocked_inferred_categories:
            codes.append(BLOCKED_SENSITIVE_INFERENCE)

        entry: PolicyRegistryEntry | None = self.registry.get(memory_type)
        if entry is None:
            # Also the shape of a model inventing a type (§7.5 Validation).
            codes.append(UNKNOWN_MEMORY_TYPE)
            return (False, codes)

        if entry.sensitivity == "blocked":
            codes.append(MEMORY_TYPE_BLOCKED)

        if ctx.consent_state == "partial" and not entry.allowed_under_partial_consent:
            codes.append(CONSENT_PARTIAL_TYPE_NOT_ALLOWED)

        if ctx.is_minor and not entry.allowed_for_minors:
            codes.append(MINOR_RESTRICTED)

        if ctx.region in entry.restricted_regions:
            codes.append(REGION_RESTRICTED)

        if ctx.region not in self.registry.known_regions():
            # Refuse rather than fall back to GLOBAL. Falling back would apply
            # the most permissive retention to a region nobody has assessed.
            codes.append(UNKNOWN_REGION)

        return (not codes, codes)

    # ── retrieval ───────────────────────────────────────────────────────────
    def evaluate_retrieval(
        self, memory: dict, ctx: PolicyContext, now: datetime | None = None
    ) -> tuple[bool, list[str]]:
        """May this stored memory be used in the response being built right now?

        §5.4: "Exclude memories that are expired, contradicted, disallowed,
        low-confidence, or outside the active surface policy."
        """
        now = _as_utc(now or datetime.now(UTC))
        codes: list[str] = []

        # Subject-level controls first. These do not depend on the memory at
        # all, and they are the ones a user directly controls.
        if ctx.consent_state == "denied":
            codes.append(CONSENT_DENIED)
        if ctx.opted_out and self.registry.opted_out.blocks_retrieval:
            codes.append(SUBJECT_OPTED_OUT)
        if ctx.memory_paused and self.registry.paused.blocks_retrieval:
            codes.append(MEMORY_PAUSED)

        # Contradicted, superseded, expired or deleted memories are not usable.
        # Only the exact usable status passes, so a new status value added later
        # is excluded by default rather than silently allowed.
        status = memory.get("status")
        if status != self.registry.usable_status:
            codes.append(f"status_{status}")

        memory_type = memory.get("memory_type")
        entry = self.registry.get(memory_type)
        if entry is None:
            codes.append(UNKNOWN_MEMORY_TYPE)
            return (False, codes)

        if ctx.consent_state == "partial" and not entry.allowed_under_partial_consent:
            # Consent can be narrowed after a memory was written. Enforcing it
            # here is what makes that change take effect on existing memories
            # (§5.5 Privacy: "purpose-limited, minimal, and reversible").
            codes.append(CONSENT_PARTIAL_TYPE_NOT_ALLOWED)

        if ctx.is_minor and not entry.allowed_for_minors:
            codes.append(MINOR_RESTRICTED)

        if ctx.region in entry.restricted_regions:
            codes.append(REGION_RESTRICTED)

        # Retention, with the regional cap applied (§5.4 "retention by memory
        # type, geography...").
        retention_days = self.registry.effective_retention_days(memory_type, ctx.region)
        recorded_at = memory.get("recorded_at")
        recorded_dt = self._parse_timestamp(recorded_at)
        if recorded_dt is not None and now - recorded_dt > timedelta(days=retention_days):
            codes.append(RETENTION_EXPIRED)

        # An explicitly closed valid-time beats any retention arithmetic: the
        # fact has stopped being true, whether or not it has aged out.
        valid_to = self._parse_timestamp(memory.get("valid_to"))
        if valid_to is not None and valid_to <= now and RETENTION_EXPIRED not in codes:
            codes.append(RETENTION_EXPIRED)

        if memory.get("confidence", 0.0) < entry.minimum_confidence:
            codes.append(LOW_CONFIDENCE)

        # Purpose limitation: the surface must be allowed to use this type for
        # at least one of the purposes it declares.
        if not any(p in entry.allowed_purposes for p in ctx.surface_policy):
            codes.append(SURFACE_INELIGIBLE)

        return (not codes, codes)

    # ── helpers ─────────────────────────────────────────────────────────────
    def retention_days_for(self, memory_type: str, region: str = "GLOBAL") -> int:
        """Effective retention, used by the processor to stamp an expiry and by
        the console to show it."""
        return self.registry.effective_retention_days(memory_type, region)

    def requires_confirmation(self, memory_type: str) -> bool:
        """True for types that may not become durable without the user saying so
        (§5.3 "Preserve playlist preferences")."""
        entry = self.registry.get(memory_type)
        return bool(entry and entry.requires_explicit_confirmation)

    @staticmethod
    def _parse_timestamp(value: object) -> datetime | None:
        """Parse an ISO-8601 timestamp, or return None if there isn't a usable one.

        Returning None for an unparseable timestamp means the retention check is
        skipped rather than the memory being wrongly dropped. That is the safe
        direction here: a malformed timestamp is a data-quality problem for the
        graph write path to reject, not a reason to silently withhold a memory
        the user can see in their own memory list.
        """
        if isinstance(value, datetime):
            return _as_utc(value)
        if not isinstance(value, str) or not value:
            return None
        try:
            return _as_utc(datetime.fromisoformat(value))
        except ValueError:
            return None

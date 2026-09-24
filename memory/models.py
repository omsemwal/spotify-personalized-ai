"""Typed request and response models.

`Literal[...]` means "only these values are allowed". Anything else is
rejected with a 422 before our code ever runs.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# The event contract version this service understands. An event declaring
# anything else is rejected as unsupported (docs/REQUIREMENTS.md, §5.4).
SUPPORTED_SCHEMA_VERSION = "1.0"


class Event(BaseModel):
    """An interaction event arriving at POST /v1/events.

    The eight required fields come from §6.3 of the dossier: subject scope,
    surface, locale, timestamp, event type, consent state, source identifier
    and idempotency key. `schema_version` carries the "versioned event
    contract" §5.4 requires so unsupported versions can be rejected.
    """

    schema_version: str = Field(description="Event contract version")

    subject_id: str = Field(min_length=1, description="Subject scope")
    event_type: Literal[
        "ai_interaction",
        "playback",
        "save",
        "follow",
        "skip",
        "explicit_preference",
        "correction",
    ]
    surface: Literal["chat", "player", "search"]
    locale: str = Field(min_length=2, description="e.g. en-US")
    occurred_at: datetime
    consent_state: Literal["granted", "denied", "paused"]
    source_event_id: str = Field(min_length=1, description="Provenance")
    idempotency_key: str = Field(min_length=1, description="Dedupe key")

    # What was actually said or played.
    #
    # Optional, because a skip or a follow has no words in it. A chat
    # message or a stated preference does, and extraction cannot classify
    # text it never received.
    #
    # abc.md:107 accepts "explicit preference statements" as events,
    # abc.md:114 deduplicates "semantically equivalent statements", and
    # abc.md:134 calls this "stored free text". The specification requires
    # the text but never names the field - `content` is our name for it.
    #
    # abc.md:134 also says to treat it as UNTRUSTED data: it is never
    # placed in a system instruction, only quoted as data.
    content: str | None = Field(
        default=None,
        max_length=4000,
        description="What was said or played; untrusted free text",
    )


class EventAccepted(BaseModel):
    """What POST /v1/events returns when it keeps an event."""

    event_id: str
    accepted: bool = True
    duplicate: bool = False


# --- Extraction (POST /v1/memories/extract) -------------------------------
#
# abc.md:112 - "Classify events into episodes, explicit preferences,
# candidate preferences, exclusions, corrections, and non-memory
# interactions."

# The five kinds of memory, exactly as abc.md:112 names them. A sixth
# outcome, "non_memory", means the event is not worth remembering at all -
# which abc.md:341 requires: return "no memory" when evidence is thin.
MEMORY_TYPES = (
    "episode",
    "explicit_preference",
    "candidate_preference",
    "exclusion",
    "correction",
)


class ExtractRequest(BaseModel):
    """What POST /v1/memories/extract accepts.

    Only an event id and the subject it belongs to. The event itself is
    read from our own store, so a caller cannot hand us content we never
    validated or consented to.
    """

    subject_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)


class PolicyClass(BaseModel):
    """How one memory must be treated.

    abc.md:292 - each memory type documents "sensitivity, retention, and
    retrieval eligibility". Those three fields, plus the expiry date they
    imply, are what later endpoints read.
    """

    sensitivity: str
    retention_days: int
    retrieval_eligibility: list[str]
    expires_at: datetime


class CandidateMemory(BaseModel):
    """One memory the extractor proposes from an event.

    "Candidate" is the important word. Nothing here is trusted yet:
    abc.md:296 - "never treat LLM extraction as authoritative without
    validation." Our rules check every field before any of it is stored.
    """

    memory_type: Literal[
        "episode",
        "explicit_preference",
        "candidate_preference",
        "exclusion",
        "correction",
    ]

    # The memory in plain words, normalised. abc.md:188 calls these
    # "candidate facts".
    fact: str = Field(min_length=1, max_length=500)

    # Artists, tracks, topics, activities mentioned (abc.md:113). These are
    # raw names; resolving them to canonical ids comes later.
    entities: list[str] = Field(default_factory=list)

    # 0.0 to 1.0. abc.md:115 - assigned by "deterministic rules plus
    # structured model output", so our code always has the final say.
    confidence: float = Field(ge=0.0, le=1.0)

    # Why the extractor chose this type. abc.md:341 asks for a reason
    # field; it is also what makes a wrong classification debuggable.
    reason: str = Field(default="", max_length=300)

    # How this memory must be treated: sensitivity, retention, and which
    # surfaces may show it. abc.md:115 - assigned by our deterministic
    # rules, never by the model. Filled in by memory/policy.py.
    policy: PolicyClass | None = None


class ExtractionResult(BaseModel):
    """What POST /v1/memories/extract returns."""

    event_id: str
    candidates: list[CandidateMemory] = Field(default_factory=list)

    # True when the event carries nothing worth remembering. abc.md:341
    # requires an explicit "no memory" answer rather than a silent empty
    # list, so a caller can tell "nothing found" from "not run".
    no_memory: bool = False

    # Anything the model proposed that our rules threw out, and why.
    # abc.md:296 - the model is untrusted, so rejections are visible.
    rejected: list[str] = Field(default_factory=list)

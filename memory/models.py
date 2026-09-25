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


class CreateMemoryRequest(BaseModel):
    """What POST /v1/memories accepts.

    abc.md:306 - "Create an explicit or approved memory". Either a
    listener stating a preference outright, or a candidate that came
    through extraction and was approved.
    """

    subject_id: str = Field(min_length=1)
    memory_type: Literal[
        "episode", "explicit_preference", "candidate_preference",
        "exclusion", "correction",
    ]
    fact: str = Field(min_length=1, max_length=500)

    # Names as written. They are resolved to catalog ids on the way in.
    entities: list[str] = Field(default_factory=list)

    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    # Which events this came from. abc.md:114 - source lineage.
    source_event_ids: list[str] = Field(default_factory=list)

    # When correcting, the memory this replaces. abc.md:118 - corrections
    # supersede prior facts rather than overwriting them.
    supersedes: str | None = None


class MemoryCreated(BaseModel):
    """What POST /v1/memories returns.

    abc.md:306 - "return stable ID, graph version, and policy state."
    """

    memory_id: str
    graph_version: int
    policy_state: str
    superseded: str | None = None


class PatchMemoryRequest(BaseModel):
    """What PATCH /v1/memories/{memory_id} accepts.

    abc.md:313 - "Correct, supersede, expire, or change an eligible memory
    under optimistic concurrency."
    """

    subject_id: str = Field(min_length=1)

    # What to do. A correction replaces the memory with a new fact and
    # keeps the old one as history; expire just closes it.
    operation: Literal["correct", "expire"]

    # The version the caller last saw. If the memory has changed since,
    # the request is refused rather than silently overwriting somebody
    # else's edit - that is what "optimistic concurrency" means.
    expected_version: int = Field(ge=1)

    # Required for a correction, ignored for an expiry.
    fact: str | None = Field(default=None, max_length=500)
    entities: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class MemoryUpdated(BaseModel):
    """What PATCH /v1/memories/{memory_id} returns."""

    memory_id: str
    graph_version: int
    status: str

    # Set when a correction replaced an older memory.
    superseded: str | None = None


class DeletionAccepted(BaseModel):
    """What DELETE /v1/memories/{memory_id} returns.

    abc.md:315 - "Start cross-store deletion and return a traceable job
    identifier." The work happens afterwards; this is the receipt.
    """

    job_id: str
    memory_id: str
    status: str = "accepted"


class DeletionStatus(BaseModel):
    """What GET /v1/deletions/{job_id} returns.

    abc.md:317 - "Report graph, vector, cache, operational-store, and
    backup-policy status." One field per store, because a partial failure
    must be visible rather than hidden behind a single flag.
    """

    job_id: str
    memory_id: str
    status: str
    stores: dict[str, str]
    requested_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


class ComposeRequest(BaseModel):
    """What POST /v1/context/compose accepts.

    abc.md:311 - "Apply policy and build the context package consumed by
    an AI orchestrator."
    """

    subject_id: str = Field(min_length=1)
    intent: str = Field(min_length=1, max_length=500)
    surface: Literal["chat", "player", "search"] = "chat"
    locale: str = "en-US"

    # How much room the orchestrator has for memory. Applied here, because
    # only here do we know what the package looks like (abc.md:125).
    token_budget: int = Field(default=500, ge=50, le=4000)


class ContextItem(BaseModel):
    """One memory inside the package.

    abc.md:132 - "memory identifier, fact, type, confidence, time, source
    class, and relevance reason."
    """

    memory_id: str
    fact: str
    memory_type: str
    confidence: float

    # "stated" when the listener said it, "observed" when we inferred it.
    # An orchestrator needs that distinction; it does not need event ids.
    source_class: str

    # Why this one was included, in one line.
    relevance_reason: str

    evidence_count: int = 1


class ContextPackage(BaseModel):
    """What POST /v1/context/compose returns."""

    # abc.md:135 - an explicit no-memory answer, never a silent empty pack.
    no_memory: bool
    reason: str

    # The text an orchestrator puts in its prompt. Memory text is fenced
    # and labelled as data (abc.md:134).
    context_block: str

    # The same memories as structured objects, so a careful caller can use
    # them without touching the rendered text at all.
    items: list[ContextItem] = Field(default_factory=list)

    # What was found and then dropped, and why (abc.md:133).
    removed: list[str] = Field(default_factory=list)

    token_estimate: int

    # The fence markers used in this package. They carry a random suffix
    # per request, so a caller must be told what to look for. Empty on a
    # no-memory package, which has no data block.
    fence_open: str = ""
    fence_close: str = ""

    # abc.md:135 - "record which memories influenced each response". The
    # trace id ties the package to the audit trail.
    trace_id: str


class SearchRequest(BaseModel):
    """What POST /v1/memories/search accepts.

    abc.md:309 - "Return ranked subject-scoped memories for intent,
    surface, locale, and token budget."
    """

    subject_id: str = Field(min_length=1)

    # What the listener is asking for now.
    intent: str = Field(min_length=1, max_length=500)

    surface: Literal["chat", "player", "search"] = "chat"
    locale: str = "en-US"

    # How many to return. The token budget itself is applied by context
    # composition (endpoint 5), which knows what the pack looks like.
    limit: int = Field(default=10, ge=1, le=50)


class RankedMemory(BaseModel):
    """One memory, with why it scored as it did.

    The signals are returned, not just the total. abc.md:341 wants a
    reason on every result, and a score with no breakdown cannot be
    debugged when it ranks something wrongly.
    """

    memory_id: str
    memory_type: str
    fact: str
    confidence: float
    score: float
    signals: dict[str, float]
    entities: list[str] = Field(default_factory=list)
    evidence_count: int = 1


class SearchResult(BaseModel):
    """What POST /v1/memories/search returns."""

    results: list[RankedMemory] = Field(default_factory=list)

    # What was found but then dropped, and why. abc.md:192 - the policy
    # engine removes items; saying which makes that checkable.
    removed: list[str] = Field(default_factory=list)

    # How many candidates were considered before ranking.
    considered: int = 0

    # abc.md:322 - every response links to a trace.
    trace_id: str


class ExtractRequest(BaseModel):
    """What POST /v1/memories/extract accepts.

    Only an event id and the subject it belongs to. The event itself is
    read from our own store, so a caller cannot hand us content we never
    validated or consented to.
    """

    subject_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)


class ResolvedEntity(BaseModel):
    """One thing a memory is about, matched to the catalog where possible.

    abc.md:113 - resolve artists, tracks, topics, activities and
    contextual concepts to canonical identifiers.
    """

    # What the listener actually wrote.
    name: str

    # The catalog id, or None when we could not match it confidently. A
    # wrong id is worse than none - it attaches the memory to the wrong
    # artist.
    entity_id: str | None = None
    canonical_name: str | None = None
    entity_type: str | None = None

    # 1.0 for an exact alias match, lower for a near miss.
    match_confidence: float = 0.0


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

    # Artists, tracks, topics and activities this memory is about,
    # resolved to catalog ids where possible (abc.md:113).
    entities: list[ResolvedEntity] = Field(default_factory=list)

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

    # Which events produced this memory. abc.md:114 - "retaining source
    # lineage": merging duplicates must never lose where they came from.
    source_event_ids: list[str] = Field(default_factory=list)

    # How many separate events said this. abc.md:49 - repeated evidence is
    # what turns a guess into a durable preference.
    evidence_count: int = 1


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

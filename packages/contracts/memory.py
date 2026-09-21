"""
Memory and temporal-graph-fact contracts.
Spec ref: §5.4 "Temporal Graph Memory Layer", §6.1 step 3.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MemoryType = Literal["episode", "explicit_preference", "candidate_preference", "exclusion", "correction"]
PolicyClass = Literal["normal", "sensitive", "blocked"]
MemoryStatus = Literal["active", "superseded", "expired", "deleted"]


class Memory(BaseModel):
    """A single versioned memory fact — the unit stored in both the graph and the
    vector index under the same `memory_id` (§5.4 "Embeddings and Retrieval").
    """
    memory_id: str = Field(..., description="Stable identifier shared across graph + vector store")
    subject_id: str
    fact_text: str = Field(..., description="Canonical natural-language statement of the fact")
    memory_type: MemoryType
    entities: list[str] = Field(default_factory=list, description="Resolved canonical entity identifiers")
    confidence: float = Field(..., ge=0.0, le=1.0)
    policy_class: PolicyClass = "normal"
    source_event_id: str
    valid_from: datetime
    valid_to: datetime | None = None
    recorded_at: datetime
    status: MemoryStatus = "active"
    surface: str | None = Field(default=None, description="Surface this memory is eligible for; None = all")


class MemoryCorrectionRequest(BaseModel):
    """Input for PATCH /v1/memories/{memory_id} — correct, supersede, or expire."""
    action: Literal["correct", "expire", "reactivate"]
    new_fact_text: str | None = Field(default=None, description="Required when action == 'correct'")
    reason: str = Field(..., description="Human-readable justification, stored for audit")
    expected_version: str = Field(..., description="Optimistic-concurrency token from the last read")


class MemoryCreateRequest(BaseModel):
    """Input for POST /v1/memories — create an explicit or approved memory."""
    subject_id: str
    fact_text: str
    memory_type: MemoryType
    entities: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_event_id: str
    surface: str | None = None

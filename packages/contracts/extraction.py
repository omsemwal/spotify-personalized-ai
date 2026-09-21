"""
Structured-output contract for memory extraction (§7.5 "Prompting, Reasoning, and Agentic Approach").
The extractor (LLM or deterministic rules) must return exactly this shape — never
free text — so memory-processor can validate before anything touches the graph.
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from .memory import MemoryType, PolicyClass


class ExtractionCandidate(BaseModel):
    """One candidate memory proposed from a single interaction event.
    Fields mirror §7.5's required structured-output fields exactly:
    memory_id, decision, normalized_fact, entities, relevance_score, confidence,
    temporal_scope, policy_flags, reason.
    """
    memory_id: str = Field(..., description="Proposed stable id (deterministic hash of subject+fact+source)")
    decision: Literal["accept", "reject", "needs_confirmation"]
    normalized_fact: str
    entities: List[str] = Field(default_factory=list)
    memory_type: MemoryType
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    temporal_scope: Literal["episodic", "durable"]
    policy_flags: List[str] = Field(default_factory=list, description="e.g. ['sensitive_inference_blocked']")
    policy_class: PolicyClass = "normal"
    reason: str = Field(..., description="Why this decision was made — required for provenance")
    source_event_id: str


class ExtractionResult(BaseModel):
    event_id: str
    candidates: List[ExtractionCandidate] = Field(default_factory=list)
    rejected_reason: Optional[str] = Field(default=None, description="Set when the event yields zero candidates")

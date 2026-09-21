"""
Context-composition contracts (§5.4 "Context Composition and LLM Integration").
The LLM never touches the graph or vector store directly — it only ever sees a
ContextPackage built by the context-composer service.
"""
from typing import List
from pydantic import BaseModel, Field


class ContextItem(BaseModel):
    memory_id: str
    fact: str = Field(..., description="Quoted as DATA, never concatenated into system instructions")
    memory_type: str
    confidence: float
    source_class: str = Field(..., description="Provenance class, e.g. 'explicit_statement', 'repeated_evidence'")
    recorded_at: str
    relevance_reason: str


class ContextPackage(BaseModel):
    subject_id: str
    surface: str
    intent: str
    items: List[ContextItem] = Field(default_factory=list)
    fallback_used: bool = Field(default=False, description="True = no-memory deterministic fallback was returned")
    fallback_reason: str = Field(default="", description="Set when fallback_used is True")
    token_budget: int
    token_count: int
    trace_id: str

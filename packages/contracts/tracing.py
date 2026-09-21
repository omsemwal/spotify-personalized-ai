"""
Trace contracts for GET /v1/traces/{trace_id} (§5.4 "Observability and Operations").
"""
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class TraceStage(BaseModel):
    stage: str = Field(..., description="One of: intake, extraction, graph_write, embedding_write, retrieval, reranking, policy_filter, context_injection, fallback")
    duration_ms: float
    outcome: str
    detail: Dict[str, Any] = Field(default_factory=dict, description="Redacted — no raw private content")


class Trace(BaseModel):
    trace_id: str
    subject_id: str
    surface: str
    stages: List[TraceStage] = Field(default_factory=list)
    memory_ids_used: List[str] = Field(default_factory=list)
    fallback_used: bool = False
    total_latency_ms: float

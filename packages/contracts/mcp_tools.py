"""
Typed I/O for every MCP tool exposed by services/memory-mcp-server (§5.4 "MCP and Tool Interface").
No tool in this system may accept or return a bare dict — every call is validated
against one of these models. The model never receives a generic graph-query tool.
"""

from pydantic import BaseModel, Field

from .memory import MemoryType


class SearchMemoryInput(BaseModel):
    subject_id: str
    surface: str
    intent: str
    locale: str = "en-US"
    max_results: int = Field(default=5, le=20)


class SearchMemoryResult(BaseModel):
    memory_id: str
    fact: str
    memory_type: MemoryType
    confidence: float
    relevance_reason: str


class SearchMemoryOutput(BaseModel):
    results: list[SearchMemoryResult]
    fallback_used: bool = False
    # Callers need this to fetch the retrieval/policy trace via GET /v1/traces/{id}
    # (§5.5 Observability: "each response must link to a trace").
    trace_id: str | None = None


class AddExplicitPreferenceInput(BaseModel):
    subject_id: str
    fact_text: str
    surface: str
    entities: list[str] = Field(default_factory=list)


class AddExplicitPreferenceOutput(BaseModel):
    memory_id: str
    status: str


class CorrectMemoryInput(BaseModel):
    memory_id: str
    new_fact_text: str
    reason: str


class CorrectMemoryOutput(BaseModel):
    old_memory_id: str
    new_memory_id: str
    status: str


class DeleteMemoryInput(BaseModel):
    memory_id: str
    reason: str | None = None


class DeleteMemoryOutput(BaseModel):
    job_id: str
    status: str


class ExplainMemoryUseInput(BaseModel):
    memory_id: str
    trace_id: str | None = None


class ExplainMemoryUseOutput(BaseModel):
    memory_id: str
    fact: str
    source_event_id: str
    confidence: float
    policy_class: str
    recorded_at: str
    used_in_traces: list[str] = Field(default_factory=list)

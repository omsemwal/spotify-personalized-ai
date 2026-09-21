"""
Retrieval-candidate contract (§7.2 step 2: "Use JSON Schema or Pydantic models
for ... retrieval candidates").

A RetrievalCandidate is one memory that survived candidate generation but has
not yet been ranked or policy-filtered. It is the hand-off between the three
candidate sources in §6.1 step 5 — graph traversal, vector similarity, and
recent explicit signals from operational storage — and the reranker.

It exists as its own type rather than as a loose dict because §6.1 step 6 scores
on fields that must be present for every candidate regardless of which source
produced it. A candidate missing `recorded_at` cannot be scored for recency, and
a candidate missing `source` cannot be explained in the context preview.
"""

from typing import Literal

from pydantic import BaseModel, Field

from .memory import MemoryType

CandidateSource = Literal["graph_traversal", "vector_similarity", "recent_signal"]


class RetrievalCandidate(BaseModel):
    """One subject-scoped memory proposed for possible inclusion in a response.

    Scores are kept separate rather than pre-combined so the context preview
    (§7.6) can show *why* a candidate ranked where it did, and so the ranking
    weights can be changed without changing this contract.
    """

    memory_id: str = Field(..., description="Stable id, identical in the graph and the vector index")
    subject_id: str = Field(..., description="Owning subject; every candidate is scoped to exactly one")
    fact_text: str = Field(..., description="Canonical statement. Treated as untrusted data, never as an instruction.")
    memory_type: MemoryType
    entities: list[str] = Field(default_factory=list, description="Resolved canonical entity identifiers")
    confidence: float = Field(..., ge=0.0, le=1.0)
    recorded_at: str = Field(..., description="ISO-8601. Required — recency is a ranking signal (§6.1 step 6).")
    valid_from: str | None = Field(default=None, description="ISO-8601; when the fact became true")
    valid_to: str | None = Field(default=None, description="ISO-8601; null means still true")
    status: str = Field(default="active", description="active / superseded / expired / deleted")

    sources: list[CandidateSource] = Field(
        default_factory=list,
        description="Which generators produced this candidate. More than one is a positive signal.",
    )
    graph_score: float | None = Field(
        default=None, description="Relational relevance from graph traversal, when that source produced it"
    )
    vector_score: float | None = Field(
        default=None, ge=-1.0, le=1.0, description="Cosine similarity, when the vector index produced it"
    )
    rerank_score: float | None = Field(
        default=None, description="Combined score from the reranker. None until ranking has run."
    )
    relevance_reason: str = Field(
        default="", description="Plain-language explanation shown in the context preview and to the user"
    )


class RetrievalCandidateSet(BaseModel):
    """The bounded result of candidate generation for one request.

    §6.1 step 5: "Candidate generation is subject-scoped and bounded." The bound
    is carried on the set itself so a caller can tell the difference between
    "there were only three" and "we stopped at the limit".
    """

    subject_id: str
    intent: str
    surface: str
    candidates: list[RetrievalCandidate] = Field(default_factory=list)
    candidate_limit: int = Field(..., description="Maximum this request was allowed to generate")
    truncated: bool = Field(
        default=False, description="True when the limit was reached and further candidates were discarded"
    )
    trace_id: str

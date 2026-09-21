"""
Vector-record contract (§7.2 step 2: "Pydantic models for ... vectors";
§6.3: "Embedding corpus and metadata linking every vector to a memory
identifier, embedding model version, approved text fields, and deletion
status").

The point of this contract is deterministic erasure. §7.2 step 6:

    "Generate vectors only after policy approval. Store graph memory ID, model
    version, text-field version, and deletion status with each vector so updates
    and erasure remain deterministic."

Every field below exists to answer one of these questions:

  * Which graph fact is this vector for?          -> memory_id
  * Whose is it?                                  -> subject_id
  * Can I reproduce it?                           -> embedding_model, model_version, text_field_version
  * Which text was actually embedded?             -> approved_text_fields, source_text_hash
  * Has it been erased?                           -> deletion_status
"""

from typing import Literal

from pydantic import BaseModel, Field

DeletionStatus = Literal["live", "pending_deletion", "deleted"]


class VectorRecord(BaseModel):
    """Metadata for one embedding. The vector itself lives in the index; this is
    the record that makes the index auditable and erasable.

    `memory_id` is deliberately the same identifier used by the graph node. §5.4
    requires it: "store vectors under the same stable memory identifier used in
    the graph". Any code that generates a separate vector id is a bug — it makes
    deletion propagation unprovable.
    """

    memory_id: str = Field(..., description="Identical to the graph fact's id. Not a separate vector id.")
    subject_id: str = Field(..., description="Owning subject, so the index can be filtered before similarity search")

    embedding_model: str = Field(..., description="e.g. 'sentence-transformers/all-MiniLM-L6-v2'")
    embedding_model_version: str = Field(
        ..., description="Pinned version of that model. A change here invalidates every vector it produced."
    )
    vector_dimension: int = Field(..., gt=0, description="Length of the stored vector; must match the index")

    approved_text_fields: list[str] = Field(
        ...,
        description=(
            "Exactly which fields of the memory were embedded, e.g. ['fact_text']. "
            "§5.4: 'Generate embeddings only for approved memory fields.'"
        ),
    )
    text_field_version: str = Field(
        ...,
        description=(
            "Version of the text-assembly rule used to build the embedded string. "
            "Changing how the text is composed must invalidate old vectors even when the model is unchanged."
        ),
    )
    source_text_hash: str = Field(
        ..., description="Hash of the exact embedded string, so a stale vector can be detected without re-embedding"
    )

    deletion_status: DeletionStatus = Field(
        default="live",
        description=(
            "'pending_deletion' is set the moment a deletion job starts, so retrieval stops using the vector "
            "before the index write completes. Prevents a deleted memory surfacing during propagation."
        ),
    )
    policy_approved: bool = Field(
        default=True,
        description="A vector may only exist for a policy-approved fact (§7.2 step 6). Recorded for audit.",
    )
    embedded_at: str = Field(..., description="ISO-8601 timestamp of generation")


class VectorAlignmentReport(BaseModel):
    """Result of checking that the graph and the vector index agree.

    This is the invariant U8 tests and U14 monitors: every active fact has
    exactly one live vector, and every deleted fact has none. Drift here means
    deletion cannot be proven, which §9 treats as a release blocker.
    """

    checked_at: str
    subject_id: str | None = Field(default=None, description="None when the check ran across all subjects")
    active_facts: int
    live_vectors: int
    missing_vectors: list[str] = Field(
        default_factory=list, description="Active fact ids with no live vector — retrieval will silently miss these"
    )
    orphan_vectors: list[str] = Field(
        default_factory=list,
        description="Live vector ids with no active fact — a deleted memory that can still be retrieved",
    )

    @property
    def aligned(self) -> bool:
        return not self.missing_vectors and not self.orphan_vectors

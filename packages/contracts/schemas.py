from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field

class InteractionEvent(BaseModel):
    """
    Schema for user interaction events entering the system via Ingestion API.
    Owned by Member 1 (services/ingestion-api).
    """
    event_id: str = Field(..., description="Unique ID of the interaction event")
    subject_id: str = Field(..., description="User identifier (tenant subject)")
    surface: str = Field(..., description="Spotify AI surface name, e.g. 'music_chat', 'playlist_ui'")
    event_type: str = Field(..., description="Event type: play, save, follow, skip, statement, correction")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary for event details")
    locale: str = Field(default="en-US", description="Locale context of the interaction")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp of occurrence")
    consent_state: str = Field(..., description="Consent status: 'granted' | 'denied' | 'partial'")
    idempotency_key: str = Field(..., description="Unique client key to guarantee idempotent ingestion")

class Memory(BaseModel):
    """
    Schema for extracted memory objects stored in Neo4j Temporal Graph and Vector Store.
    Owned by Member 2 (services/memory-processor) & Member 3 (packages/graph-schema).
    """
    memory_id: str = Field(..., description="Canonical memory identifier")
    subject_id: str = Field(..., description="User identifier")
    fact_text: str = Field(..., description="Natural language statement of the fact/preference")
    memory_type: str = Field(..., description="Classification: episode | explicit_preference | candidate_preference | exclusion | correction")
    entities: List[str] = Field(default_factory=list, description="Resolved entity identifiers / canonical names")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    policy_class: str = Field(..., description="Privacy policy tier: 'normal' | 'sensitive' | 'blocked'")
    source_event_id: str = Field(..., description="ID of source InteractionEvent that generated this memory")
    valid_from: datetime = Field(default_factory=datetime.utcnow, description="Temporal start valid timestamp")
    valid_to: Optional[datetime] = Field(default=None, description="Temporal end valid timestamp (None if currently valid)")
    recorded_at: datetime = Field(default_factory=datetime.utcnow, description="System creation timestamp")
    status: str = Field(default="active", description="Lifecycle state: active | superseded | expired | deleted")

class ContextItem(BaseModel):
    """
    Individual context memory element formatted for LLM consumption.
    """
    memory_id: str = Field(..., description="Canonical memory ID")
    fact: str = Field(..., description="Fact text formatted for context window")
    memory_type: str = Field(..., description="Memory classification")
    confidence: float = Field(..., description="Memory confidence score")
    source: str = Field(..., description="Provenance / surface origin")
    relevance_reason: str = Field(..., description="Scoring explanation for inclusion")

class ContextPackage(BaseModel):
    """
    Safely packaged context delivery unit created by Context Composer for LLM prompts.
    Owned by Member 5 (services/context-composer).
    """
    subject_id: str = Field(..., description="Target user identifier")
    items: List[ContextItem] = Field(default_factory=list, description="Ranked, filtered context items")
    fallback_used: bool = Field(default=False, description="True if retrieval failed or yielded no safe memories")
    token_count: int = Field(default=0, description="Calculated total token footprint of packaged context items")

"""
Versioned interaction-event contract.
Owner: shared (all services import this — never redefine locally).
Spec ref: §5.4 "Interaction Capture and Input Handling", §7.1 packages/contracts.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

ConsentState = Literal["granted", "denied", "partial"]
EventType = Literal["play", "save", "follow", "skip", "statement", "correction", "opt_out", "delete_request"]


class InteractionEvent(BaseModel):
    """A single eligible interaction event entering the system via the Ingestion API.

    Every field here is required by §5.4: subject scope, surface, locale, timestamp,
    consent state, source-event identifier, and idempotency key must be attached to
    every event before it is allowed into graph processing.
    """
    schema_version: str = Field(default=SCHEMA_VERSION, description="Contract version for compatibility checks")
    event_id: str = Field(..., description="Unique source-event identifier")
    subject_id: str = Field(..., description="Authenticated subject (user) scope")
    surface: str = Field(..., description="Originating AI surface, e.g. 'music_chat', 'playlist_ui', 'podcast_chat'")
    event_type: EventType = Field(..., description="Interaction classification")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event-type-specific structured payload")
    locale: str = Field(default="en-US", description="Locale context of the interaction")
    timestamp: datetime = Field(..., description="Client-reported time of occurrence (UTC)")
    consent_state: ConsentState = Field(..., description="Consent status at time of capture")
    idempotency_key: str = Field(..., description="Client-supplied key; duplicate keys must not double-write")


class EventRejectionReason(BaseModel):
    """Structured reason an event was rejected before graph processing (§5.4)."""
    code: Literal[
        "malformed", "unauthenticated", "out_of_policy", "unsupported_schema_version",
        "consent_denied", "duplicate_event",
    ]
    message: str

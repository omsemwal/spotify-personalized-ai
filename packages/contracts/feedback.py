"""
Feedback contract for POST /v1/feedback (§5.4 "Experimentation and Quality Review").
Feedback records user or reviewer signal — it must never self-validate model output.
"""
from typing import Literal

from pydantic import BaseModel, Field


class FeedbackEvent(BaseModel):
    trace_id: str
    subject_id: str
    memory_id: str | None = Field(default=None, description="Set when feedback targets one specific memory")
    feedback_type: Literal["relevant", "irrelevant", "correction", "rejection", "satisfaction_positive", "satisfaction_negative"]
    comment: str | None = None

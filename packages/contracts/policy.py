"""
Policy decision contracts (§5.4 "User Control, Privacy, and Safety").
"""
from typing import Literal

from pydantic import BaseModel, Field


class PolicyDecision(BaseModel):
    memory_id: str
    allowed: bool
    policy_class: Literal["normal", "sensitive", "blocked"]
    rejection_codes: list[str] = Field(default_factory=list, description="e.g. ['expired','contradicted','low_confidence','surface_ineligible']")
    retention_days: int
    reviewed_by: str = Field(default="policy_engine", description="'policy_engine' for automatic, else reviewer id")

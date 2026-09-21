"""Shared, versioned data contracts. Every service imports from here — never
redefines these models locally. This is the single source of truth referenced
throughout §5.4 and required by the CTO's transcript instruction: "Define the
event contract, graph schema, retrieval contract, and policy boundary now."
"""
from .events import InteractionEvent, EventRejectionReason, EventType, ConsentState, SCHEMA_VERSION
from .memory import Memory, MemoryType, PolicyClass, MemoryStatus, MemoryCorrectionRequest, MemoryCreateRequest
from .extraction import ExtractionCandidate, ExtractionResult
from .context import ContextItem, ContextPackage
from .policy import PolicyDecision
from .feedback import FeedbackEvent
from .tracing import Trace, TraceStage
from .mcp_tools import (
    SearchMemoryInput, SearchMemoryOutput, SearchMemoryResult,
    AddExplicitPreferenceInput, AddExplicitPreferenceOutput,
    CorrectMemoryInput, CorrectMemoryOutput,
    DeleteMemoryInput, DeleteMemoryOutput,
    ExplainMemoryUseInput, ExplainMemoryUseOutput,
)

__all__ = [
    "InteractionEvent", "EventRejectionReason", "EventType", "ConsentState", "SCHEMA_VERSION",
    "Memory", "MemoryType", "PolicyClass", "MemoryStatus", "MemoryCorrectionRequest", "MemoryCreateRequest",
    "ExtractionCandidate", "ExtractionResult",
    "ContextItem", "ContextPackage",
    "PolicyDecision",
    "FeedbackEvent",
    "Trace", "TraceStage",
    "SearchMemoryInput", "SearchMemoryOutput", "SearchMemoryResult",
    "AddExplicitPreferenceInput", "AddExplicitPreferenceOutput",
    "CorrectMemoryInput", "CorrectMemoryOutput",
    "DeleteMemoryInput", "DeleteMemoryOutput",
    "ExplainMemoryUseInput", "ExplainMemoryUseOutput",
]

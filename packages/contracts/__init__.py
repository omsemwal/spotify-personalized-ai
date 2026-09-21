"""Shared, versioned data contracts. Every service imports from here — never
redefines these models locally. This is the single source of truth referenced
throughout §5.4 and required by the CTO's transcript instruction: "Define the
event contract, graph schema, retrieval contract, and policy boundary now."
"""
from .context import ContextItem, ContextPackage
from .events import SCHEMA_VERSION, ConsentState, EventRejectionReason, EventType, InteractionEvent
from .extraction import ExtractionCandidate, ExtractionResult
from .feedback import FeedbackEvent
from .mcp_tools import (
    AddExplicitPreferenceInput,
    AddExplicitPreferenceOutput,
    CorrectMemoryInput,
    CorrectMemoryOutput,
    DeleteMemoryInput,
    DeleteMemoryOutput,
    ExplainMemoryUseInput,
    ExplainMemoryUseOutput,
    SearchMemoryInput,
    SearchMemoryOutput,
    SearchMemoryResult,
)
from .memory import (
    Memory,
    MemoryCorrectionRequest,
    MemoryCreateRequest,
    MemoryStatus,
    MemoryType,
    PolicyClass,
)
from .policy import PolicyDecision
from .tracing import Trace, TraceStage

__all__ = [
    "SCHEMA_VERSION",
    "AddExplicitPreferenceInput",
    "AddExplicitPreferenceOutput",
    "ConsentState",
    "ContextItem",
    "ContextPackage",
    "CorrectMemoryInput",
    "CorrectMemoryOutput",
    "DeleteMemoryInput",
    "DeleteMemoryOutput",
    "EventRejectionReason",
    "EventType",
    "ExplainMemoryUseInput",
    "ExplainMemoryUseOutput",
    "ExtractionCandidate",
    "ExtractionResult",
    "FeedbackEvent",
    "InteractionEvent",
    "Memory",
    "MemoryCorrectionRequest",
    "MemoryCreateRequest",
    "MemoryStatus",
    "MemoryType",
    "PolicyClass",
    "PolicyDecision",
    "SearchMemoryInput",
    "SearchMemoryOutput",
    "SearchMemoryResult",
    "Trace",
    "TraceStage",
]

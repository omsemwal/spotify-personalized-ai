"""
The 5 narrow, typed MCP tools (§5.4 "MCP and Tool Interface"). No tool here
ever exposes a generic graph query — each is a single, authorized, audited
operation with a fixed input/output contract from packages/contracts/mcp_tools.py.
"""
import os
import uuid

import httpx
from audit import record
from rate_limiter import allow

from packages.contracts import (
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
)

RETRIEVAL_API_URL = "http://localhost:8002"
MEMORY_PROCESSOR_URL = "http://localhost:8006"
DELETION_ORCHESTRATOR_URL = "http://localhost:8004"

# Pooled client for the process — a per-call client pays TCP setup every time
# (~550ms measured), which made every tool call time out. Pooled, the same call
# returns in ~20ms.
_http = httpx.AsyncClient(timeout=2.0)


class RateLimitedError(Exception):
    pass


class SubjectMismatchError(Exception):
    pass


_STORE_SINGLETON = None


def get_graph_store():
    """Same DI pattern as the other services' store_factory.py — read-only here,
    used to return real provenance for explain_memory_use."""
    global _STORE_SINGLETON
    if _STORE_SINGLETON is not None:
        return _STORE_SINGLETON
    if os.getenv("LOCAL_MODE", "true").lower() != "true":
        try:
            from graph import TemporalGraphStore
            _STORE_SINGLETON = TemporalGraphStore()
            return _STORE_SINGLETON
        except Exception:
            pass
    from memory_store import InMemoryGraphStore
    _STORE_SINGLETON = InMemoryGraphStore()
    return _STORE_SINGLETON


def _check_rate(subject_id: str, tool_name: str):
    if not allow(subject_id, tool_name):
        record(tool_name, subject_id, {}, "rate_limited")
        raise RateLimitedError(f"rate limit exceeded for {tool_name}")


async def search_memory(inp: SearchMemoryInput) -> SearchMemoryOutput:
    _check_rate(inp.subject_id, "search_memory")
    resp = await _http.post(f"{RETRIEVAL_API_URL}/v1/memories/search", json=inp.model_dump())
    resp.raise_for_status()
    result = SearchMemoryOutput(**resp.json())
    record("search_memory", inp.subject_id, {"surface": inp.surface}, "ok")
    return result


async def add_explicit_preference(inp: AddExplicitPreferenceInput) -> AddExplicitPreferenceOutput:
    _check_rate(inp.subject_id, "add_explicit_preference")
    resp = await _http.post(f"{MEMORY_PROCESSOR_URL}/v1/memories", json={
        "subject_id": inp.subject_id, "fact_text": inp.fact_text, "memory_type": "explicit_preference",
        "entities": inp.entities, "confidence": 0.95,
        "source_event_id": f"mcp_{uuid.uuid4().hex[:8]}", "surface": inp.surface,
    })
    resp.raise_for_status()
    data = resp.json()
    record("add_explicit_preference", inp.subject_id, {"surface": inp.surface}, "ok")
    return AddExplicitPreferenceOutput(memory_id=data["memory_id"], status=data["status"])


async def correct_memory(inp: CorrectMemoryInput, subject_id: str) -> CorrectMemoryOutput:
    _check_rate(subject_id, "correct_memory")
    resp = await _http.patch(f"{MEMORY_PROCESSOR_URL}/v1/memories/{inp.memory_id}", json={
        "action": "correct", "new_fact_text": inp.new_fact_text,
        "reason": inp.reason, "expected_version": "",
    })
    resp.raise_for_status()
    data = resp.json()
    record("correct_memory", subject_id, {"memory_id": inp.memory_id}, "ok")
    return CorrectMemoryOutput(old_memory_id=data["old_memory_id"], new_memory_id=data["new_memory_id"], status=data["status"])


async def delete_memory(inp: DeleteMemoryInput, subject_id: str) -> DeleteMemoryOutput:
    _check_rate(subject_id, "delete_memory")
    resp = await _http.delete(f"{DELETION_ORCHESTRATOR_URL}/v1/memories/{inp.memory_id}")
    resp.raise_for_status()
    data = resp.json()
    record("delete_memory", subject_id, {"memory_id": inp.memory_id}, "ok")
    return DeleteMemoryOutput(job_id=data["job_id"], status=data["status"])


async def explain_memory_use(inp: ExplainMemoryUseInput, subject_id: str) -> ExplainMemoryUseOutput:
    _check_rate(subject_id, "explain_memory_use")
    resp = await _http.get(f"{RETRIEVAL_API_URL}/v1/traces/{inp.trace_id}") if inp.trace_id else None
    used_in = [inp.trace_id] if inp.trace_id and resp is not None and resp.status_code == 200 else []

    memory = get_graph_store().get_memory(inp.memory_id) or {}
    # Subject binding: a tool call may never return another subject's provenance
    # (§5.5 Security: "every read must bind to the authenticated subject").
    if memory and memory.get("subject_id") not in (None, subject_id):
        record("explain_memory_use", subject_id, {"memory_id": inp.memory_id}, "subject_mismatch")
        raise SubjectMismatchError("memory does not belong to the authenticated subject")

    record("explain_memory_use", subject_id, {"memory_id": inp.memory_id}, "ok")
    return ExplainMemoryUseOutput(
        memory_id=inp.memory_id,
        fact=memory.get("fact_text", ""),
        source_event_id=memory.get("source_event_id") or "",
        confidence=memory.get("confidence") or 0.0,
        policy_class=memory.get("policy_class") or "normal",
        recorded_at=memory.get("recorded_at") or "",
        used_in_traces=used_in,
    )

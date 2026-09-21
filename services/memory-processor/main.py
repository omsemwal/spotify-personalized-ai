"""
Memory Processor — owns three of the ten required APIs (§7.3):
  POST /v1/memories/extract   — deterministic candidate extraction
  POST /v1/memories           — create an explicit/approved memory
  PATCH /v1/memories/{id}     — correct, supersede, or expire a memory

Spec ref: §5.4 "Memory Extraction and Entity Resolution", §6.1 steps 2-3.
"""
import os
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root))
sys.path.insert(0, str(_repo_root / "packages" / "graph-schema"))
sys.path.insert(0, str(_repo_root / "packages" / "policy-engine"))

from datetime import UTC, datetime

from classifier import extract_candidates
from consumer import start_consumer
from engine import PolicyContext, PolicyEngine
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from store_factory import get_graph_store

from packages.contracts import (
    ExtractionResult,
    InteractionEvent,
    Memory,
    MemoryCorrectionRequest,
    MemoryCreateRequest,
)

app = FastAPI(
    title="Spotify Memory System — Memory Processor",
    description="Extraction, entity resolution, policy gate, and temporal graph writes.",
    version="1.0.0",
)

# Browser product surfaces (apps/memory-controls, apps/memory-console) call these
# APIs directly from the page. Without this the browser blocks every request under
# its same-origin rule. Narrow CORS_ALLOW_ORIGINS before any non-pilot deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:3001,null"
    ).split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

policy_engine = PolicyEngine()
store = get_graph_store()


_consumer_running = False


@app.on_event("startup")
def _start_queue_consumer():
    """Closes the async capture loop: events accepted by ingestion-api are
    consumed here and written to the graph (§6.1 steps 1-3)."""
    global _consumer_running
    _consumer_running = start_consumer(store)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "memory-processor", "queue_consumer": _consumer_running}


@app.post("/v1/memories/extract", response_model=ExtractionResult)
def extract(event: InteractionEvent):
    """Deterministic validation entry point — converts one approved event into
    typed candidates WITHOUT writing to the graph (§7.3 endpoint #2)."""
    candidates = extract_candidates(event)
    if not candidates:
        return ExtractionResult(event_id=event.event_id, candidates=[], rejected_reason="no_memory_eligible_content")
    return ExtractionResult(event_id=event.event_id, candidates=candidates)


@app.post("/v1/memories", status_code=status.HTTP_201_CREATED)
def create_memory(req: MemoryCreateRequest):
    """Create an explicit or approved memory (§7.3 endpoint #3). This is the
    ONLY path that writes a new durable fact — never write solely because an
    LLM generated it in a response (§7.5 Memory safety)."""
    ctx = PolicyContext(consent_state="granted", surface_policy=["continuity", "personalization", "correction"])
    allowed, codes = policy_engine.evaluate_write(req.memory_type, ctx)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={
            "error_code": "policy_denial", "rejection_codes": codes
        })

    now = datetime.now(UTC)
    import hashlib
    memory_id = "mem_" + hashlib.sha256(f"{req.subject_id}|{req.fact_text}|{req.source_event_id}".encode()).hexdigest()[:16]

    memory = Memory(
        memory_id=memory_id, subject_id=req.subject_id, fact_text=req.fact_text,
        memory_type=req.memory_type, entities=req.entities, confidence=req.confidence,
        policy_class="normal", source_event_id=req.source_event_id,
        valid_from=now, recorded_at=now, status="active", surface=req.surface,
    )
    store.write_memory(memory.model_dump(mode="json"))
    return {"memory_id": memory_id, "status": "active", "graph_version": "1"}


@app.patch("/v1/memories/{memory_id}")
def correct_memory(memory_id: str, req: MemoryCorrectionRequest):
    """Correct, expire, or reactivate a memory under optimistic concurrency
    (§7.3 endpoint #6). Corrections SUPERSEDE — they never overwrite history."""
    existing = store.get_memory(memory_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_code": "not_found"})

    # optimistic concurrency: compare against caller-supplied expected_version
    current_version = existing.get("recorded_at", "")
    if req.expected_version and req.expected_version != current_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_code": "conflict", "message": "stale version"})

    now = datetime.now(UTC)
    if req.action == "expire":
        store.expire_memory(memory_id)
        return {"memory_id": memory_id, "status": "expired"}

    if req.action == "correct":
        if not req.new_fact_text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "validation", "message": "new_fact_text required"})
        import hashlib
        new_id = "mem_" + hashlib.sha256(f"{existing['subject_id']}|{req.new_fact_text}|{memory_id}".encode()).hexdigest()[:16]
        new_memory = dict(existing)
        new_memory.update({
            "memory_id": new_id, "fact_text": req.new_fact_text, "memory_type": "correction",
            "confidence": 1.0, "valid_from": now.isoformat(), "recorded_at": now.isoformat(),
            "valid_to": None, "status": "active",
        })
        store.correct_memory(memory_id, new_memory)
        return {"old_memory_id": memory_id, "new_memory_id": new_id, "status": "superseded"}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": "validation", "message": "unsupported action"})

"""
Context Composer — owns two of the ten required APIs (§7.3):
  POST /v1/context/compose   — builds the bounded LLM context package
  POST /v1/feedback          — records relevance/correction/rejection signal

Spec ref: §5.4 "Context Composition and LLM Integration", §6.1 step 7.
"""
import os
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root))
sys.path.insert(0, str(_repo_root / "packages" / "graph-schema"))
sys.path.insert(0, str(_repo_root / "packages" / "policy-engine"))

import uuid
from datetime import UTC, datetime

import httpx
import operational_store
from composer import compose_context
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from packages.contracts import ContextPackage, FeedbackEvent

app = FastAPI(
    title="Spotify Memory System — Context Composer",
    description="Assembles the bounded, policy-filtered context package for the LLM.",
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

RETRIEVAL_API_URL = "http://localhost:8002"

# One pooled client for the process. A per-request client pays TCP setup on
# every call (~550ms measured) and blows the §5.5 budget; a pooled connection
# serves the same call in ~20ms. The timeout below is the fail-open guard for a
# hung dependency, deliberately looser than the 250ms P95 target so a cold
# first connection degrades latency rather than dropping personalization.
_http = httpx.AsyncClient(timeout=2.0)


@app.on_event("shutdown")
async def _close_http_client():
    await _http.aclose()


class ComposeRequest(BaseModel):
    subject_id: str
    surface: str
    intent: str
    locale: str = "en-US"
    token_budget: int = 400


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "context-composer",
            "operational_store": operational_store.get_backend()}


@app.post("/v1/context/compose", response_model=ContextPackage)
async def compose(req: ComposeRequest):
    try:
        resp = await _http.post(f"{RETRIEVAL_API_URL}/v1/memories/search", json={
            "subject_id": req.subject_id, "surface": req.surface,
            "intent": req.intent, "locale": req.locale, "max_results": 5,
        })
        resp.raise_for_status()
        search_data = resp.json()
    except Exception:
        # Fail open — a slow/unavailable retrieval-api never blocks the
        # experience; the composer returns the deterministic no-memory result.
        return ContextPackage(
            subject_id=req.subject_id, surface=req.surface, intent=req.intent,
            items=[], fallback_used=True, fallback_reason="retrieval_api_unavailable_or_timeout",
            token_budget=req.token_budget, token_count=0, trace_id=str(uuid.uuid4()),
        )

    results = [
        {"memory_id": r["memory_id"], "fact": r["fact"], "memory_type": r["memory_type"],
         "confidence": r["confidence"], "relevance_reason": r["relevance_reason"],
         "recorded_at": datetime.now(UTC).isoformat()}
        for r in search_data.get("results", [])
    ]
    trace_id = str(uuid.uuid4())
    return compose_context(req.subject_id, req.surface, req.intent, trace_id, results, req.token_budget)


@app.post("/v1/feedback", status_code=202)
def submit_feedback(feedback: FeedbackEvent):
    """Records feedback WITHOUT self-validating model output (§5.4 Experimentation
    and Quality Review) — this only ever stores what the user or reviewer said."""
    operational_store.save_feedback(feedback.model_dump(mode="json"))
    return {"status": "recorded", "trace_id": feedback.trace_id}

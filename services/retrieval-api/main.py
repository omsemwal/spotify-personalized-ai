"""
Retrieval API — owns two of the ten required APIs (§7.3):
  POST /v1/memories/search   — hybrid ranked retrieval
  GET  /v1/traces/{trace_id} — authorized retrieval/policy trace (redacted)

Spec ref: §5.4 "Embeddings and Retrieval", §6.1 steps 5-6.
"""
import os
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root))
sys.path.insert(0, str(_repo_root / "packages" / "graph-schema"))
sys.path.insert(0, str(_repo_root / "packages" / "policy-engine"))

import operational_store
from embeddings import get_embedder
from engine import PolicyContext, PolicyEngine
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from reranker import rerank
from store_factory import get_graph_store
from vector_store import InMemoryVectorStore

from packages.contracts import SearchMemoryOutput, SearchMemoryResult, Trace
from packages.observability import TraceRecorder

app = FastAPI(
    title="Spotify Memory System — Retrieval API",
    description="Hybrid graph + vector retrieval, reranking, and trace serving.",
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

embedder = get_embedder()
vector_store = InMemoryVectorStore()
graph_store = get_graph_store()
policy_engine = PolicyEngine()

_TRACE_LOG: dict = {}  # trace_id -> Trace dict, in-memory pilot store (production: operational store, §6.2 PostgreSQL)


class SearchRequest(BaseModel):
    subject_id: str
    surface: str
    intent: str
    locale: str = "en-US"
    max_results: int = 5


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "retrieval-api",
            "operational_store": operational_store.get_backend(),
            "vector_index": "neo4j" if hasattr(graph_store, "vector_search") else "in_process"}


def index_memory_for_search(memory_dict: dict):
    """Writes the embedding onto the memory's own graph node, so the vector and
    the fact share one identifier and one lifetime (§5.4). Falls back to the
    in-process index only if the store has no vector support."""
    vec = embedder.embed(memory_dict["fact_text"])
    if hasattr(graph_store, "set_embedding") and not memory_dict.get("embedding"):
        try:
            graph_store.set_embedding(memory_dict["memory_id"], vec)
            return
        except Exception:
            pass
    vector_store.upsert(memory_dict["memory_id"], vec)


@app.post("/v1/memories/search", response_model=SearchMemoryOutput)
def search_memories(req: SearchRequest):
    recorder = TraceRecorder(subject_id=req.subject_id, surface=req.surface)
    ctx = PolicyContext(consent_state="granted", surface_policy=["continuity", "personalization"])

    with recorder.stage("retrieval", detail={"intent": req.intent}):
        # graph candidates: everything the subject has, scoped by subject_id (subject isolation)
        graph_candidates = graph_store.get_all_for_subject(req.subject_id) if hasattr(graph_store, "get_all_for_subject") else []
        graph_hit_ids = {m["memory_id"] for m in graph_candidates}

        # semantic candidates: vector similarity against the same candidate pool.
        # Candidates are embedded on read so the vector index stays aligned with
        # the graph under the same memory_id even for memories written by another
        # service (§5.4 "store vectors under the same stable memory identifier").
        query_vec = embedder.embed(req.intent)
        for mem in graph_candidates:
            index_memory_for_search(mem)

        # Semantic candidates come from the Neo4j vector index when available,
        # which keeps graph and vector state in one store (§6.2). The in-process
        # index remains the fallback for local mode.
        candidate_ids = [m["memory_id"] for m in graph_candidates]
        if hasattr(graph_store, "vector_search"):
            try:
                vector_hits = graph_store.vector_search(req.subject_id, query_vec, top_k=20)
            except Exception:
                vector_hits = vector_store.search(query_vec, candidate_ids, top_k=20)
        else:
            vector_hits = vector_store.search(query_vec, candidate_ids, top_k=20)
        vector_scores = {mid: score for mid, score in vector_hits}

    with recorder.stage("reranking", detail={"candidate_count": len(graph_candidates)}):
        # Memories this subject rejected are demoted, not silently reused.
        negative = operational_store.negative_feedback_memory_ids(req.subject_id)
        reranked = rerank(graph_candidates, vector_scores, graph_hit_ids,
                          max_items=req.max_results, negative_feedback_ids=negative)

    with recorder.stage("policy_filter"):
        filtered = []
        for mem in reranked:
            # TODO(U9): surface these rejection codes in the trace — the
            # console's context preview needs to show why a memory was removed.
            allowed, _codes = policy_engine.evaluate_retrieval(mem, ctx)
            if allowed:
                filtered.append(mem)
                recorder.use_memory(mem["memory_id"])

    fallback_used = len(filtered) == 0
    if fallback_used:
        recorder.mark_fallback()

    _TRACE_LOG[recorder.trace_id] = recorder.to_trace_dict()

    results = [
        SearchMemoryResult(
            memory_id=m["memory_id"], fact=m["fact_text"], memory_type=m["memory_type"],
            confidence=m["confidence"],
            relevance_reason=f"rerank_score={m.get('_rerank_score', 0):.2f}",
        )
        for m in filtered
    ]
    return SearchMemoryOutput(results=results, fallback_used=fallback_used, trace_id=recorder.trace_id)


@app.get("/v1/traces/{trace_id}", response_model=Trace)
def get_trace(trace_id: str):
    trace = _TRACE_LOG.get(trace_id)
    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_code": "not_found"})
    return Trace(**trace)

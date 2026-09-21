"""
Reranking — combines intent fit, explicitness, confidence, recency, repetition,
surface policy, and negative feedback into one score, then applies diversity
and context-budget limits so no single cluster dominates.
Spec ref: §5.4 "Embeddings and Retrieval" / §6.1 step 6 "Rerank and govern."
"""
from datetime import UTC, datetime
from typing import Any

WEIGHTS = {
    "vector_similarity": 0.26,
    "explicitness": 0.22,
    "confidence": 0.17,
    "recency": 0.13,
    "graph_match_bonus": 0.08,
    "repetition": 0.14,
    # Negative feedback subtracts rather than adds: a memory a user rejected
    # should fall, not merely rise less (§5.4 "rerank by ... negative feedback").
    "negative_feedback": -0.30,
}

EXPLICIT_TYPES = {"explicit_preference", "exclusion", "correction"}


def _repetition_score(mem: dict[str, Any], candidates: list[dict[str, Any]]) -> float:
    """How often the subject has repeated this idea. Repeated evidence is what
    §5.4 says should promote a candidate preference toward a durable one, so a
    fact echoed by sibling memories about the same entities scores higher."""
    entities = set(mem.get("entities") or [])
    if not entities:
        return 0.0
    echoes = sum(
        1 for other in candidates
        if other["memory_id"] != mem["memory_id"] and entities & set(other.get("entities") or [])
    )
    return min(echoes / 3.0, 1.0)   # saturates at 3 supporting memories


def _recency_score(recorded_at: str, now: datetime) -> float:
    try:
        recorded_dt = datetime.fromisoformat(recorded_at)
        if recorded_dt.tzinfo is None:
            recorded_dt = recorded_dt.replace(tzinfo=UTC)
        age_days = max((now - recorded_dt).total_seconds() / 86400, 0)
        return max(0.0, 1.0 - age_days / 90.0)  # decays to 0 over ~90 days
    except Exception:
        return 0.0


def rerank(candidates: list[dict[str, Any]], vector_scores: dict[str, float], graph_hit_ids: set,
           max_items: int = 5, max_per_entity_cluster: int = 2,
           negative_feedback_ids: set | None = None) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    negative_feedback_ids = negative_feedback_ids or set()
    scored = []
    for mem in candidates:
        mid = mem["memory_id"]
        explicitness = 1.0 if mem.get("memory_type") in EXPLICIT_TYPES else 0.4
        score = (
            WEIGHTS["vector_similarity"] * vector_scores.get(mid, 0.0)
            + WEIGHTS["explicitness"] * explicitness
            + WEIGHTS["confidence"] * mem.get("confidence", 0.0)
            + WEIGHTS["recency"] * _recency_score(mem.get("recorded_at", ""), now)
            + WEIGHTS["graph_match_bonus"] * (1.0 if mid in graph_hit_ids else 0.0)
            + WEIGHTS["repetition"] * _repetition_score(mem, candidates)
            + WEIGHTS["negative_feedback"] * (1.0 if mid in negative_feedback_ids else 0.0)
        )
        scored.append((score, mem))
    scored.sort(key=lambda x: x[0], reverse=True)

    # Diversity / context-budget limit: cap how many items from the same first
    # entity cluster can appear, so one preference doesn't dominate the pack.
    out = []
    cluster_counts: dict[str, int] = {}
    for score, mem in scored:
        cluster_key = (mem.get("entities") or ["_none_"])[0]
        if cluster_counts.get(cluster_key, 0) >= max_per_entity_cluster:
            continue
        out.append({**mem, "_rerank_score": round(score, 4)})
        cluster_counts[cluster_key] = cluster_counts.get(cluster_key, 0) + 1
        if len(out) >= max_items:
            break
    return out

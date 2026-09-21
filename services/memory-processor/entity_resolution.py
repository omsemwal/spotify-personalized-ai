"""
Canonical entity resolution. Spec ref: §5.4 "Resolve artists, tracks, albums,
playlists, shows, episodes, topics, activities, and contextual concepts to
canonical identifiers." §7.2 step 4: "Map catalog entities to stable
identifiers... maintain alias tables."

Pilot implementation uses a small in-memory alias table standing in for the
real catalog service. Swap `resolve()` for a catalog API call in production.
"""
from typing import List

_ALIAS_TABLE = {
    "lofi": "genre:lofi_focus",
    "lo-fi": "genre:lofi_focus",
    "low-vocal": "attribute:low_vocal",
    "instrumental": "attribute:low_vocal",
    "true crime": "topic:true_crime",
    "true-crime": "topic:true_crime",
    "morning": "context:morning",
    "focus": "activity:focus_work",
    "workout": "activity:workout",
    "sad songs": "mood_context:melancholic",  # allowed as a labeled context tag, NOT a durable emotional-state inference
}


def resolve(raw_terms: List[str]) -> List[str]:
    resolved = []
    for term in raw_terms:
        key = term.strip().lower()
        resolved.append(_ALIAS_TABLE.get(key, f"unresolved:{key}"))
    # Deduplicate while preserving order (dedup semantically equivalent statements, §5.4)
    seen = set()
    out = []
    for r in resolved:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out

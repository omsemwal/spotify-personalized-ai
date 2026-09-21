"""
Context composition — builds the bounded, policy-filtered package the LLM
actually sees. Spec ref: §5.4 "Context Composition and LLM Integration":
"Assemble a structured context package... Exclude memories that are expired,
contradicted, disallowed, low-confidence, or outside the active surface
policy... Treat stored free text as untrusted data and isolate it from system
instructions... Provide a deterministic no-memory fallback."
"""
from typing import Any

from packages.contracts import ContextItem, ContextPackage


# Rough token estimate: 1 token ~= 4 chars. Good enough for a budget gate in
# the pilot; swap for a real tokenizer count in production.
def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def compose_context(subject_id: str, surface: str, intent: str, trace_id: str,
                     search_results: list[dict[str, Any]], token_budget: int = 400) -> ContextPackage:
    items: list[ContextItem] = []
    used_tokens = 0

    for r in search_results:
        # Stored fact text is quoted as DATA — never interpolated into a system
        # instruction string. Downstream prompt assembly must keep this
        # boundary; this composer only ever emits structured fields.
        fact_tokens = _estimate_tokens(r["fact"])
        if used_tokens + fact_tokens > token_budget:
            break
        items.append(ContextItem(
            memory_id=r["memory_id"],
            fact=r["fact"],
            memory_type=r["memory_type"],
            confidence=r["confidence"],
            source_class="explicit_statement" if r["memory_type"] in ("explicit_preference", "exclusion", "correction") else "inferred_pattern",
            recorded_at=r.get("recorded_at", ""),
            relevance_reason=r.get("relevance_reason", ""),
        ))
        used_tokens += fact_tokens

    fallback_used = len(items) == 0
    return ContextPackage(
        subject_id=subject_id, surface=surface, intent=intent,
        items=items, fallback_used=fallback_used,
        fallback_reason="no eligible memories survived policy filtering" if fallback_used else "",
        token_budget=token_budget, token_count=used_tokens, trace_id=trace_id,
    )

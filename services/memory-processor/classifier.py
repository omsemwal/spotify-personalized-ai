"""
Deterministic-rules classifier producing ExtractionCandidate objects.
Spec ref: §5.4 "Classify events into episodes, explicit preferences, candidate
preferences, exclusions, corrections, and non-memory interactions" and §7.5
"Assign confidence and policy class using deterministic rules plus structured
model output." (This pilot uses deterministic rules only — swap in a
structured-output LLM call behind the same ExtractionCandidate contract when
ready; the interface does not change.)
"""
import hashlib
from datetime import datetime, timezone
from typing import List

from packages.contracts import ExtractionCandidate, InteractionEvent

from entity_resolution import resolve


def _deterministic_id(subject_id: str, fact: str, source_event_id: str) -> str:
    h = hashlib.sha256(f"{subject_id}|{fact}|{source_event_id}".encode()).hexdigest()[:16]
    return f"mem_{h}"


def classify(event: InteractionEvent) -> List[ExtractionCandidate]:
    candidates: List[ExtractionCandidate] = []

    if event.event_type == "statement":
        raw_text = str(event.payload.get("text", ""))
        entities = resolve(event.payload.get("entities", []))
        is_explicit = bool(event.payload.get("explicit", True))
        is_exclusion = bool(event.payload.get("is_exclusion", False))
        memory_type = "exclusion" if is_exclusion else ("explicit_preference" if is_explicit else "candidate_preference")
        confidence = 0.95 if is_explicit else 0.55
        fact = raw_text.strip() or f"preference regarding {', '.join(entities) or 'unspecified'}"
        candidates.append(ExtractionCandidate(
            memory_id=_deterministic_id(event.subject_id, fact, event.event_id),
            decision="accept" if fact else "reject",
            normalized_fact=fact,
            entities=entities,
            memory_type=memory_type,
            relevance_score=confidence,
            confidence=confidence,
            temporal_scope="durable" if is_explicit or is_exclusion else "episodic",
            policy_flags=[],
            reason="explicit user statement" if is_explicit else "inferred from single statement — needs repeated evidence to become durable",
            source_event_id=event.event_id,
        ))

    elif event.event_type == "correction":
        raw_text = str(event.payload.get("text", ""))
        entities = resolve(event.payload.get("entities", []))
        candidates.append(ExtractionCandidate(
            memory_id=_deterministic_id(event.subject_id, raw_text, event.event_id),
            decision="accept",
            normalized_fact=raw_text.strip(),
            entities=entities,
            memory_type="correction",
            relevance_score=1.0,
            confidence=1.0,
            temporal_scope="durable",
            policy_flags=[],
            reason="explicit user correction — takes precedence over prior facts",
            source_event_id=event.event_id,
        ))

    elif event.event_type in ("play", "save", "follow", "skip"):
        entities = resolve(event.payload.get("entities", []))
        fact = f"{event.event_type} interaction with {', '.join(entities) or 'unspecified content'}"
        candidates.append(ExtractionCandidate(
            memory_id=_deterministic_id(event.subject_id, fact, event.event_id),
            decision="accept",
            normalized_fact=fact,
            entities=entities,
            memory_type="episode",
            relevance_score=0.3,
            confidence=0.4,
            temporal_scope="episodic",
            policy_flags=[],
            reason="behavioral episode — not promoted to durable preference without repeated evidence",
            source_event_id=event.event_id,
        ))

    # opt_out / delete_request never produce memories — they are handled by
    # deletion-orchestrator, not memory-processor.
    return candidates


def extract_candidates(event: InteractionEvent) -> List[ExtractionCandidate]:
    """The extraction entry point used by both the API and the queue consumer.

    §5.4: "Assign confidence and policy class using deterministic rules PLUS
    structured model output." Both run; this merges them.

    The deterministic result is the floor — it is reproducible and cannot fail.
    Model candidates are added on top, and where both produced the same
    memory_id the deterministic one wins, so a model cannot quietly downgrade
    or reclassify a fact the rules already decided (§7.5 Memory safety).
    """
    deterministic = classify(event)

    try:
        import llm_extractor
        if not llm_extractor.is_enabled():
            return deterministic
        model_candidates = llm_extractor.get_llm_candidates(event)
    except Exception:
        return deterministic

    seen = {c.memory_id for c in deterministic}
    merged = list(deterministic)
    for cand in model_candidates:
        if cand.memory_id not in seen:
            merged.append(cand)
            seen.add(cand.memory_id)
    return merged

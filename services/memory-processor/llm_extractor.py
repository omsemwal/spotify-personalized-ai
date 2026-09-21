"""
Structured-output extraction (§5.4 "Assign confidence and policy class using
deterministic rules PLUS structured model output", §7.5 "Memory extraction
receives an event plus an allowed taxonomy and returns typed candidates").

This never replaces the deterministic classifier — it runs alongside it, and
every field the model returns is validated before it is allowed anywhere near
the graph. Specifically, per §7.5 "Validation":

  * memory_id is NEVER taken from the model. It is recomputed deterministically
    from (subject, fact, event), so an invented ID cannot enter the system.
  * memory_type must be one of the allowed taxonomy values; anything else is
    dropped rather than coerced.
  * confidence and relevance_score are clamped to [0, 1].
  * entities are re-resolved through the canonical alias table, so the model
    cannot introduce unknown entities.

§7.5 "Memory safety": nothing here writes a memory. It returns candidates for
the same policy gate every other path goes through.

With no API key configured, get_llm_candidates() returns [] and the caller
falls back to deterministic rules alone.
"""
import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import Any

from entity_resolution import resolve

from packages.contracts import ExtractionCandidate, InteractionEvent

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL = os.getenv("EXTRACTION_MODEL", "gemini-2.5-flash").strip()
TIMEOUT_SECONDS = float(os.getenv("EXTRACTION_TIMEOUT", "8"))

ALLOWED_TYPES = ["episode", "explicit_preference", "candidate_preference",
                 "exclusion", "correction"]
ALLOWED_SCOPES = ["durable", "episodic"]

# §7.5 System instruction: role, allowed taxonomy, prohibited inferences,
# subject boundary, temporal rules, and the requirement to return no memory
# when evidence is insufficient.
SYSTEM_INSTRUCTION = """You extract durable memory candidates from a single Spotify interaction event.

ALLOWED MEMORY TAXONOMY — use exactly one of these for memory_type:
- explicit_preference: the user directly stated a lasting taste or want.
- exclusion: the user directly stated something they do NOT want.
- correction: the user is correcting or retracting something said earlier.
- candidate_preference: a preference only implied, or explicitly temporary
  ("just this week", "while I'm studying"). Not yet durable.
- episode: a one-off behaviour (played, skipped, saved, followed) with no
  stated preference.

PROHIBITED INFERENCES — never produce a candidate about emotional state, mood,
mental health, medical matters, or political affiliation, even if the text
hints at them. Return no candidate rather than an inferred sensitive attribute.

SUBJECT BOUNDARY — reason only about the single subject in this event. Never
reference or infer anything about other people.

TEMPORAL RULES — wording that bounds something in time ("this week", "today",
"while I'm working", "for now") makes it candidate_preference with
temporal_scope "episodic", never a durable explicit_preference.

INSUFFICIENT EVIDENCE — if the event carries no memory-worthy content, return
an empty candidates array. Returning nothing is the correct answer for small
talk, ambiguity, or pure navigation.

Set decision to "accept" only when you are confident the candidate belongs in
the taxonomy above; otherwise "reject" with a reason.
Keep normalized_fact close to the user's own words. Do not invent detail."""

# §7.5 Structured output fields.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string", "enum": ["accept", "reject"]},
                    "normalized_fact": {"type": "string"},
                    "entities": {"type": "array", "items": {"type": "string"}},
                    "memory_type": {"type": "string", "enum": ALLOWED_TYPES},
                    "relevance_score": {"type": "number"},
                    "confidence": {"type": "number"},
                    "temporal_scope": {"type": "string", "enum": ALLOWED_SCOPES},
                    "policy_flags": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["decision", "normalized_fact", "memory_type",
                             "confidence", "temporal_scope", "reason"],
            },
        }
    },
    "required": ["candidates"],
}


def is_enabled() -> bool:
    return bool(API_KEY)


def _deterministic_id(subject_id: str, fact: str, source_event_id: str) -> str:
    """Same rule the deterministic classifier uses. The model never supplies an
    ID, so it cannot invent one (§7.5 Validation)."""
    h = hashlib.sha256(f"{subject_id}|{fact}|{source_event_id}".encode()).hexdigest()[:16]
    return f"mem_{h}"


def _clamp(value: Any, low: float = 0.0, high: float = 1.0, default: float = 0.5) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


def _call_gemini(event: InteractionEvent) -> dict[str, Any]:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{MODEL}:generateContent?key={API_KEY}")
    # Only the fields the model needs. No other subject's data is ever included.
    user_block = json.dumps({
        "event_type": event.event_type,
        "surface": event.surface,
        "locale": event.locale,
        "text": str(event.payload.get("text", "")),
        "entities": event.payload.get("entities", []),
    }, ensure_ascii=False)

    body = json.dumps({
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [{"role": "user", "parts": [{"text": user_block}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
            "temperature": 0.0,          # extraction must be repeatable
        },
    }).encode()

    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    # The URL is built from a constant https endpoint and a model name, never
    # from user input. Replaced by the Anthropic SDK in U6.
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:  # noqa: S310
        payload = json.load(resp)
    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def get_llm_candidates(event: InteractionEvent) -> list[ExtractionCandidate]:
    """Typed candidates from the model, fully validated. Returns [] when the
    model is unavailable, so extraction degrades to deterministic rules rather
    than failing the request (§5.5 Reliability)."""
    if not API_KEY:
        return []

    try:
        raw = _call_gemini(event)
    except Exception:
        return []

    out: list[ExtractionCandidate] = []
    for item in (raw.get("candidates") or [])[:5]:
        try:
            if item.get("decision") != "accept":
                continue

            memory_type = item.get("memory_type")
            if memory_type not in ALLOWED_TYPES:        # policy-ineligible type
                continue

            fact = (item.get("normalized_fact") or "").strip()
            if not fact:                                # unsupported claim
                continue

            scope = item.get("temporal_scope")
            if scope not in ALLOWED_SCOPES:
                scope = "episodic"

            # Entities go back through the canonical alias table, so the model
            # cannot introduce an unknown entity (§7.5 Validation).
            entities = resolve([str(e) for e in (item.get("entities") or [])])

            out.append(ExtractionCandidate(
                memory_id=_deterministic_id(event.subject_id, fact, event.event_id),
                decision="accept",
                normalized_fact=fact,
                entities=entities,
                memory_type=memory_type,
                relevance_score=_clamp(item.get("relevance_score"), default=0.5),
                confidence=_clamp(item.get("confidence"), default=0.5),
                temporal_scope=scope,
                policy_flags=[str(f) for f in (item.get("policy_flags") or [])],
                reason=f"structured model output: {item.get('reason', '')}".strip(),
                source_event_id=event.event_id,
            ))
        except Exception:
            continue   # one malformed candidate must not lose the rest

    return out

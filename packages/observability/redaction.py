"""
Redaction helper — §5.4 "Redact sensitive payloads from logs while preserving
identifiers needed for investigation."
"""
from typing import Any

SENSITIVE_KEYS = {"fact_text", "payload", "comment", "raw_text", "email", "phone"}


def redact_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Returns a copy with sensitive free-text fields replaced by a length marker,
    keeping identifiers (ids, timestamps, types, scores) intact for debugging."""
    out = {}
    for k, v in data.items():
        if k in SENSITIVE_KEYS and isinstance(v, str):
            out[k] = f"<redacted:{len(v)}chars>"
        elif isinstance(v, dict):
            out[k] = redact_payload(v)
        else:
            out[k] = v
    return out

"""Loads golden evaluation cases from data/golden-sets/ (§5.4 "Experimentation
and Quality Review": stable preferences, temporary contexts, contradictions,
multilingual phrasing, sparse histories, adversarial stored content)."""
import json
from pathlib import Path
from typing import Any


def load_golden_set(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Golden set not found: {path}")
    with open(p) as f:
        data = json.load(f)
    return data["cases"] if isinstance(data, dict) and "cases" in data else data

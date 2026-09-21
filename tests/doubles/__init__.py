"""Explicit test doubles. Nothing outside tests/ may import from here."""

from .graph_store import InMemoryGraphStore

__all__ = ["InMemoryGraphStore"]

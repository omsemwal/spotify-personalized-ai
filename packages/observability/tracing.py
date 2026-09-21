"""
TraceRecorder — accumulates TraceStage entries across the pipeline and produces
a Trace object servable at GET /v1/traces/{trace_id}.
Spec ref: §5.4 "Trace event intake, transformation, graph write, embedding
write, candidate retrieval, reranking, policy filtering, and context injection."
"""
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List

from .redaction import redact_payload


class TraceRecorder:
    def __init__(self, subject_id: str, surface: str, trace_id: str = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.subject_id = subject_id
        self.surface = surface
        self.stages: List[Dict[str, Any]] = []
        self.memory_ids_used: List[str] = []
        self.fallback_used = False
        self._start = time.monotonic()

    @contextmanager
    def stage(self, name: str, detail: Dict[str, Any] = None):
        t0 = time.monotonic()
        outcome = "ok"
        try:
            yield
        except Exception:
            outcome = "error"
            raise
        finally:
            self.stages.append({
                "stage": name,
                "duration_ms": round((time.monotonic() - t0) * 1000, 2),
                "outcome": outcome,
                "detail": redact_payload(detail or {}),
            })

    def mark_fallback(self):
        self.fallback_used = True

    def use_memory(self, memory_id: str):
        if memory_id not in self.memory_ids_used:
            self.memory_ids_used.append(memory_id)

    def to_trace_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "subject_id": self.subject_id,
            "surface": self.surface,
            "stages": self.stages,
            "memory_ids_used": self.memory_ids_used,
            "fallback_used": self.fallback_used,
            "total_latency_ms": round((time.monotonic() - self._start) * 1000, 2),
        }

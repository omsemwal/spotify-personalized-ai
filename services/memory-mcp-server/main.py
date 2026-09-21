"""
Memory MCP Server — exposes exactly 5 typed, authenticated, rate-limited,
audited tools over MCP (§5.4 "MCP and Tool Interface"). Never a generic
graph-query tool.

Uses the official MCP Python SDK (`mcp` package, §8 reference links) when
available; falls back to a plain FastAPI JSON-RPC-shaped surface for local
testing when the `mcp` package isn't installed, so the tool contracts and
authorization/audit logic are exercised identically either way.
"""
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo_root))
sys.path.insert(0, str(_repo_root / "packages" / "graph-schema"))
sys.path.insert(0, str(_repo_root / "packages" / "policy-engine"))

import tools as tool_impl

from packages.contracts import (
    AddExplicitPreferenceInput,
    CorrectMemoryInput,
    DeleteMemoryInput,
    ExplainMemoryUseInput,
    SearchMemoryInput,
)

try:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("spotify-memory")

    @mcp.tool()
    async def search_memory(subject_id: str, surface: str, intent: str, locale: str = "en-US", max_results: int = 5):
        """Hybrid search over a subject's eligible memories for the current intent."""
        return (await tool_impl.search_memory(SearchMemoryInput(
            subject_id=subject_id, surface=surface, intent=intent, locale=locale, max_results=max_results
        ))).model_dump()

    @mcp.tool()
    async def add_explicit_preference(subject_id: str, fact_text: str, surface: str,
                                      entities: list[str] | None = None):
        """Create an explicit, user-stated preference memory."""
        return (await tool_impl.add_explicit_preference(AddExplicitPreferenceInput(
            subject_id=subject_id, fact_text=fact_text, surface=surface, entities=entities or []
        ))).model_dump()

    @mcp.tool()
    async def correct_memory(subject_id: str, memory_id: str, new_fact_text: str, reason: str):
        """Supersede a memory with a corrected fact — never destroys history."""
        return (await tool_impl.correct_memory(CorrectMemoryInput(
            memory_id=memory_id, new_fact_text=new_fact_text, reason=reason
        ), subject_id=subject_id)).model_dump()

    @mcp.tool()
    async def delete_memory(subject_id: str, memory_id: str, reason: str | None = None):
        """Start a cross-store deletion job for one memory."""
        return (await tool_impl.delete_memory(DeleteMemoryInput(
            memory_id=memory_id, reason=reason
        ), subject_id=subject_id)).model_dump()

    @mcp.tool()
    async def explain_memory_use(subject_id: str, memory_id: str, trace_id: str | None = None):
        """Return provenance for why a memory was used in a response."""
        return (await tool_impl.explain_memory_use(ExplainMemoryUseInput(
            memory_id=memory_id, trace_id=trace_id
        ), subject_id=subject_id)).model_dump()

    app = mcp  # entry point: `mcp.run()` or served via the MCP CLI

except ImportError:
    # Fallback surface for environments without the `mcp` package installed —
    # exercises the SAME tool implementations/contracts via plain HTTP.
    import os

    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    app = FastAPI(title="Spotify Memory System — MCP Server (HTTP fallback)", version="1.0.0")

    # Browser product surfaces call this fallback surface directly; without this
    # the browser blocks every request under its same-origin rule. Narrow
    # CORS_ALLOW_ORIGINS before any non-pilot deploy.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv(
            "CORS_ALLOW_ORIGINS", "http://localhost:3000,http://localhost:3001,null"
        ).split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Stable error codes per §7.3 — an authorization or rate-limit refusal must
    # not surface as an opaque 500.
    @app.exception_handler(tool_impl.SubjectMismatchError)
    async def _subject_mismatch(request: Request, exc: tool_impl.SubjectMismatchError):
        return JSONResponse(status_code=403, content={"error_code": "unauthorized_subject", "message": str(exc)})

    @app.exception_handler(tool_impl.RateLimitedError)
    async def _rate_limited(request: Request, exc: tool_impl.RateLimitedError):
        return JSONResponse(status_code=429, content={"error_code": "rate_limited", "message": str(exc)})

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "memory-mcp-server", "mode": "http_fallback_no_mcp_sdk",
                "tool_audit": tool_impl.audit_backend(),
                "rate_limiter": tool_impl.rate_limit_backend()}

    @app.post("/tools/search_memory")
    async def _search_memory(inp: SearchMemoryInput):
        return await tool_impl.search_memory(inp)

    @app.post("/tools/add_explicit_preference")
    async def _add_explicit_preference(inp: AddExplicitPreferenceInput):
        return await tool_impl.add_explicit_preference(inp)

    @app.post("/tools/correct_memory")
    async def _correct_memory(inp: CorrectMemoryInput, subject_id: str):
        return await tool_impl.correct_memory(inp, subject_id)

    @app.post("/tools/delete_memory")
    async def _delete_memory(inp: DeleteMemoryInput, subject_id: str):
        return await tool_impl.delete_memory(inp, subject_id)

    @app.post("/tools/explain_memory_use")
    async def _explain_memory_use(inp: ExplainMemoryUseInput, subject_id: str):
        return await tool_impl.explain_memory_use(inp, subject_id)

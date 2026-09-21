# services/memory-mcp-server

**What this is:** The MCP surface — exactly 5 typed tools, each authenticated
by subject, rate-limited, and audited. Spec ref: §5.4 "MCP and Tool Interface".

## Tools (§4 MCP Platform Lead, §5.4)
| Tool | Backs | Calls |
|---|---|---|
| `search_memory` | `POST /v1/memories/search` | retrieval-api |
| `add_explicit_preference` | `POST /v1/memories` | memory-processor |
| `correct_memory` | `PATCH /v1/memories/{id}` | memory-processor |
| `delete_memory` | `DELETE /v1/memories/{id}` | deletion-orchestrator |
| `explain_memory_use` | `GET /v1/traces/{trace_id}` | retrieval-api |

> "The model should never receive a generic graph query tool." — MCP Platform
> Lead, §4. Every tool here calls one fixed downstream endpoint with a typed,
> validated input — there is no free-form query parameter anywhere in this file.

## Files
- `tools.py` — the 5 tool implementations, each doing: rate-limit check →
  downstream HTTP call → audit record → typed return.
- `rate_limiter.py` — per-`(subject_id, tool_name)` token bucket.
- `audit.py` — append-only audit log (pilot: in-memory; production: PostgreSQL
  `tool_audit` table per §6.2).
- `main.py` — wraps the tools with the official MCP Python SDK (`FastMCP`) when
  available; falls back to a plain HTTP surface exposing the same contracts so
  the logic is testable in environments without the `mcp` package installed.

## Versioning
Tool schemas live in `packages/contracts/mcp_tools.py` and are versioned
alongside the rest of the shared contracts (§5.4 "Version tool contracts and
preserve backward compatibility").

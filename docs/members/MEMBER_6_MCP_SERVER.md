# 👤 Member 6 — MCP Tools Server Task Specification

- **Target Folder**: [`services/memory-mcp-server/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/memory-mcp-server/)
- **Primary Goal**: FastMCP Server exposing standardized Model Context Protocol (MCP) tools for LLM agents.

---

## 📌 Service Overview
Implements a dedicated Model Context Protocol (MCP) server using `FastMCP` (Python SDK). Exposes 5 typed tools allowing AI agents to query, create, correct, delete, and inspect memory provenance safely.

## 🛠️ Required MCP Tools Exposed
1. `search_memory(subject_id: str, query: str)`: Wraps Member 4's Retrieval API.
2. `add_explicit_preference(subject_id: str, fact_text: str)`: Creates explicit user memory via Member 3's `write_memory`.
3. `correct_memory(memory_id: str, new_fact_text: str)`: Invokes Member 3's `correct_memory`.
4. `delete_memory(memory_id: str)`: Triggers full deletion job via Member 7's Deletion Orchestrator.
5. `explain_memory_use(memory_id: str)`: Returns audit details and rationale for past memory inclusions.

## 📋 Implementation Checklist
- [ ] Initialize `FastMCP` server in `services/memory-mcp-server/`.
- [ ] Implement subject authorization check on every tool invocation (`requester == subject_id`).
- [ ] Add audit logging for tool executions (timestamp, caller, tool name, parameters).
- [ ] Add rate-limiting middleware (max 20 calls/min per `subject_id`).
- [ ] Write integration test client verifying tool calling via MCP protocol.
- [ ] Create `README.md` detailing tool schemas and configuration for Claude Desktop / Cursor / Antigravity MCP integration.

## 🚫 Constraints
- **NEVER** permit cross-tenant/cross-subject tool execution.
- **ALWAYS** produce structured JSON output from tool functions.

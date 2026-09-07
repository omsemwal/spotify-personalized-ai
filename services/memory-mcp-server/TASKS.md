# 👤 Member 6 — MCP Tools Server

**Folder**: `services/memory-mcp-server/`  
**Assigned To**: Member 6 (MCP Tool Developer)

---

## 🎯 What is this service for? (Simple Words)
This is an **MCP (Model Context Protocol) Server**. It lets AI agents (like Claude or Cursor) use 5 tools to search, add, edit, or delete user memories directly.

---

## 🛠️ 5 MCP Tools to Build
1. `search_memory(subject_id, query)`: Search stored memories.
2. `add_explicit_preference(subject_id, fact_text)`: Add a new explicit user preference.
3. `correct_memory(memory_id, new_fact_text)`: Update an existing memory.
4. `delete_memory(memory_id)`: Delete a memory.
5. `explain_memory_use(memory_id)`: Explain why a memory was used.

---

## 📝 Simple Steps to Complete
1. Set up python `FastMCP` app.
2. Define each tool with explicit types and parameter descriptions.
3. Add security check: ensure caller can only access their own `subject_id`.
4. Log every tool call for auditing.

---

## 🧪 How to Test
- Connect server to Claude Desktop or Antigravity MCP inspector and call `search_memory` tool!

# 👤 Member 3 — Temporal Graph Layer (Neo4j)

**Folder**: `packages/graph-schema/`  
**Assigned To**: Member 3 (Graph Database Developer)

---

## 🎯 What is this package for? (Simple Words)
This is the **memory database connector** for Neo4j. It saves memories as connected nodes (`User -> Memory -> Song/Artist`). It also handles history updates when users change their mind (without deleting history).

---

## 🛠️ Python Functions to Create
- `write_memory(memory)`: Saves a new memory node into Neo4j.
- `correct_memory(memory_id, new_fact)`: Links old memory to new memory using a `SUPERSEDES` relation.
- `expire_memory(memory_id)`: Marks old memory as expired.
- `traverse_related(subject_id, entities)`: Looks up connected memories in the graph for a user.

---

## 📝 Simple Steps to Complete
1. Connect to Neo4j database using python `neo4j` package.
2. Write Cypher queries for saving nodes: `(:User)-[:HAS_MEMORY]->(:Memory)-[:ABOUT]->(:Entity)`.
3. Make sure every query checks `subject_id` (so users can NEVER see someone else's memory).

---

## 🧪 How to Test
- Run python integration test: write a memory, update it, and ensure the old version is linked as updated!

# 👑 Team Lead — Shared Data Contracts

**Folder**: `packages/contracts/`  
**Assigned To**: Lead / Architecture

---

## 🎯 What is this folder for? (Simple Words)
This folder holds all shared data schemas (Pydantic models) used by everyone on the team. It defines how data looks when passing between services.

---

## 📝 Simple Steps to Complete
1. **Define Event Schema (`schemas.py`)**:
   - `InteractionEvent`: Schema for events sent into the ingestion API (user ID, event type, timestamp, consent).
2. **Define Memory Schema**:
   - `Memory`: Schema for stored memories (memory ID, fact text, confidence score, policy class).
3. **Define Context Schema**:
   - `ContextPackage`: Schema for memories passed to the LLM (list of facts, token count).
4. **Publish Package**:
   - Ensure other python services can `from packages.contracts.schemas import ...`.

---

## 🧪 How to Test
- Run `pytest` to make sure all Pydantic schemas validate correctly.

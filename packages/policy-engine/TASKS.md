# 👤 Member 7 — Policy Engine Package

**Folder**: `packages/policy-engine/`  
**Assigned To**: Member 7 (Privacy & Policy Developer)

---

## 🎯 What is this package for? (Simple Words)
This package holds the **privacy rules** for the whole system. It makes sure user consent is checked and prevents users from accessing anyone else's memory data.

---

## 🛠️ Functions to Build
- `check_consent(subject_id, memory_type)`: Returns `True` if user allows memory storage.
- `check_subject_isolation(requester_id, target_subject_id)`: Returns `True` only if `requester_id == target_subject_id`.

---

## 📝 Simple Steps to Complete
1. Build privacy checks function module.
2. Flag emotional or sensitive memories as `"blocked"` by default.
3. Export functions for Member 1 (Ingestion) and Member 4 (Retrieval) to import.

---

## 🧪 How to Test
- Test `check_subject_isolation("user_A", "user_B")` -> must return `False`!

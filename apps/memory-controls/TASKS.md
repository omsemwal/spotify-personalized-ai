# 👤 Member 8 — User Memory Controls Frontend

**Folder**: `apps/memory-controls/`  
**Assigned To**: Member 8 (Frontend UI Developer)

---

## 🎯 What is this web app for? (Simple Words)
This is the **user interface** where real users can chat with the AI assistant and manage their stored memories ("What we remember about you" sidebar with Edit & Delete buttons).

---

## 📝 Simple Steps to Complete
1. **Next.js / React App Setup**: Create app UI in `apps/memory-controls/`.
2. **Chat Screen**: Build chat box where users type questions.
3. **Memory Sidebar**: Display list of active user memories (fact text, date, confidence).
4. **Edit Button**: Calls `PATCH /v1/memories/{id}` when user edits a memory.
5. **Delete Button**: Calls `DELETE /v1/memories/{id}` when user deletes a memory.

---

## 🧪 How to Test
- Run `npm run dev` and test chatting, editing a memory fact, and clicking delete!

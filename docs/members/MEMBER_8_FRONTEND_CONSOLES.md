# 👤 Member 8 — Frontend User Controls & Admin Console Task Specification

- **Target Folders**: [`apps/memory-controls/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/apps/memory-controls/) & [`apps/memory-console/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/apps/memory-console/)
- **Primary Goal**: Next.js / React web applications for end-user memory controls and internal admin observability.

---

## 📌 Web Applications Overview
1. **User Memory Controls (`apps/memory-controls/`) — USER FACING**:
   - Conversational AI interface (music assistant chat).
   - "What we remember about you" sidebar listing active memories with confidence and creation dates.
   - Inline controls to Edit (`PATCH /v1/memories/{id}`) or Delete (`DELETE /v1/memories/{id}`) memories with live deletion job status polling (`GET /v1/deletions/{job_id}`).

2. **Admin & Observability Console (`apps/memory-console/`) — INTERNAL ADMIN**:
   - Subject timeline explorer (inspecting user memories & provenance).
   - Context preview panel (simulating queries against `POST /v1/context/compose`).
   - Retrieval quality dashboard (golden set metrics, precision/recall, latency).
   - Operations monitor & policy rejection review panel.

## 📋 Implementation Checklist
- [ ] Build User Memory Controls Next.js app in `apps/memory-controls/`.
- [ ] Build Chat UI + Memory Management sidebar.
- [ ] Connect Edit and Delete buttons to backend APIs.
- [ ] Build Admin Memory Console Next.js app in `apps/memory-console/`.
- [ ] Build Timeline explorer and Context Compose Preview panel.
- [ ] Add basic OpenTelemetry tracing / metrics visualization.
- [ ] Create `README.md` with screenshots and setup guides.

## 🚫 Constraints
- **NEVER** expose raw Cypher or database query text to end users.
- **NEVER** allow cross-user memory leakage in user controls interface (derive `subject_id` strictly from auth session).

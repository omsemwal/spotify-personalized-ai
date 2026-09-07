# 👥 8-Member Team Work Allocation & Task Map

This directory contains individual task documentation files for each of the **8 Team Members** building the Spotify Personalized AI Memory System.

---

## 🗺️ Member Assignment Overview

| Member | Focus / Feature Area | Target Folder(s) | Primary Deliverable / API |
| :--- | :--- | :--- | :--- |
| **Member 1** | **Ingestion API** | [`services/ingestion-api/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/ingestion-api/) | `POST /v1/events` (FastAPI + Redis idempotency + Kafka) |
| **Member 2** | **Memory Extraction & Processing** | [`services/memory-processor/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/memory-processor/) | Kafka consumer worker, entity resolution & confidence scoring |
| **Member 3** | **Temporal Graph Layer** | [`packages/graph-schema/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/graph-schema/) | Neo4j storage (`write_memory`, `correct_memory`, `traverse_related`) |
| **Member 4** | **Embeddings & Retrieval API** | [`services/retrieval-api/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/retrieval-api/) | `POST /v1/memories/search` (Hybrid Graph + Qdrant Vector search) |
| **Member 5** | **Context Composer & LLM Integration** | [`services/context-composer/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/context-composer/) | `POST /v1/context/compose` & safe prompt construction |
| **Member 6** | **MCP Tools Server** | [`services/memory-mcp-server/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/memory-mcp-server/) | FastMCP Tool Server (5 core memory tools) |
| **Member 7** | **Privacy & Deletion Orchestrator** | [`services/deletion-orchestrator/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/deletion-orchestrator/) & [`packages/policy-engine/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/policy-engine/) | Multi-store deletion engine & isolation/consent policy checks |
| **Member 8** | **Frontend Controls & Admin Console** | [`apps/memory-controls/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/apps/memory-controls/) & [`apps/memory-console/`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/apps/memory-console/) | Next.js/React User Controls & Admin Console |

---

## 📑 Detailed Task Documentation Files

1. [MEMBER_1_INGESTION_API.md](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/docs/members/MEMBER_1_INGESTION_API.md)
2. [MEMBER_2_MEMORY_PROCESSOR.md](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/docs/members/MEMBER_2_MEMORY_PROCESSOR.md)
3. [MEMBER_3_GRAPH_SCHEMA.md](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/docs/members/MEMBER_3_GRAPH_SCHEMA.md)
4. [MEMBER_4_RETRIEVAL_API.md](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/docs/members/MEMBER_4_RETRIEVAL_API.md)
5. [MEMBER_5_CONTEXT_COMPOSER.md](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/docs/members/MEMBER_5_CONTEXT_COMPOSER.md)
6. [MEMBER_6_MCP_SERVER.md](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/docs/members/MEMBER_6_MCP_SERVER.md)
7. [MEMBER_7_PRIVACY_DELETION.md](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/docs/members/MEMBER_7_PRIVACY_DELETION.md)
8. [MEMBER_8_FRONTEND_CONSOLES.md](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/docs/members/MEMBER_8_FRONTEND_CONSOLES.md)

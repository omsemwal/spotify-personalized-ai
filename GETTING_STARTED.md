# 🚀 Getting Started — Spotify Personalized AI Memory System

Follow these steps exactly in order. Do them **once** as a team (Lead sets up infra first, then each member starts their own service).

---

## ✅ Step 0 — What You Need Installed First

Make sure every team member has these installed before anything else:

| Tool | Why We Need It | Install Link |
| :--- | :--- | :--- |
| **Docker Desktop** | Runs all databases (Neo4j, Redis, Kafka, Qdrant, Postgres) locally | https://www.docker.com/products/docker-desktop |
| **Python 3.10+** | Runs all backend services | https://www.python.org/downloads/ |
| **Node.js 18+** | Runs the two frontend apps (Member 8) | https://nodejs.org/ |
| **Git** | Clone the repo and collaborate | https://git-scm.com/ |

---

## 🏁 Step 1 — Clone the Project (Everyone Does This)

```bash
git clone <your-repo-url>
cd spotify-personalized-ai-memory-system
```

---

## 🔑 Step 2 — Set Up Environment Variables (Everyone Does This)

Copy the example environment file and fill in your API keys:

```bash
# On Mac/Linux:
cp .env.example .env

# On Windows (PowerShell):
Copy-Item .env.example .env
```

Then open `.env` and set your **OpenAI API Key** (or other LLM key):

```
OPENAI_API_KEY=sk-your-key-here
```

> Everything else (database passwords, ports) is already pre-filled and works for local dev — **don't change them unless you know what you're doing.**

---

## 🐳 Step 3 — Start All Databases (Lead Runs This Once)

This single command starts **all 5 databases** in Docker:

```bash
docker-compose up -d
```

This starts:
| Container | What It Does | Port |
| :--- | :--- | :--- |
| **Postgres** | Stores deletion jobs & audit logs | `5432` |
| **Neo4j** | Temporal graph memory store | `7687` (Bolt), `7474` (Browser UI) |
| **Redis** | Idempotency key cache | `6379` |
| **Redpanda** | Kafka-compatible event broker | `9092` |
| **Qdrant** | Vector similarity search database | `6333` |

### ✅ Verify all containers are running:
```bash
docker-compose ps
```
All 5 services should show **"Up"** status.

### 🌐 Check database UIs in your browser:
- **Neo4j Browser**: http://localhost:7474 (login: `neo4j` / `neo4j_password_secure`)
- **Qdrant Dashboard**: http://localhost:6333/dashboard

---

## 📦 Step 4 — Install Shared Python Contracts (Everyone Does This)

The `packages/contracts/` folder has shared Pydantic schemas that ALL services depend on. Install it first:

```bash
cd packages/contracts
pip install -e .
cd ../..
```

> This lets all services do `from packages.contracts.schemas import InteractionEvent, Memory, ...`

---

## 👤 Step 5 — Each Member Starts Their Own Service

Each member goes to **their own folder** and starts their service:

---

### 👤 Member 1 — Ingestion API
```bash
cd services/ingestion-api
pip install fastapi uvicorn aiokafka redis
uvicorn main:app --reload --port 8001
```
**Test it:**
```bash
curl -X POST http://localhost:8001/v1/events \
  -H "Content-Type: application/json" \
  -d '{"subject_id":"user_01","event_type":"play","consent_state":"granted",...}'
```
📖 Task file: [`services/ingestion-api/TASKS.md`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/ingestion-api/TASKS.md)

---

### 👤 Member 2 — Memory Processor
```bash
cd services/memory-processor
pip install aiokafka neo4j
python worker.py
```
**What to expect:** Worker logs show classified memories from Kafka events.

📖 Task file: [`services/memory-processor/TASKS.md`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/memory-processor/TASKS.md)

---

### 👤 Member 3 — Graph Schema (Neo4j)
```bash
cd packages/graph-schema
pip install neo4j
python -c "from graph import TemporalGraphStore; g = TemporalGraphStore(); print('Connected to Neo4j!')"
```
**Test it:** Run the provided test script in the folder.

📖 Task file: [`packages/graph-schema/TASKS.md`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/graph-schema/TASKS.md)

---

### 👤 Member 4 — Retrieval API
```bash
cd services/retrieval-api
pip install fastapi uvicorn sentence-transformers qdrant-client
uvicorn main:app --reload --port 8002
```
**Test it:**
```bash
curl -X POST http://localhost:8002/v1/memories/search \
  -H "Content-Type: application/json" \
  -d '{"subject_id":"user_01","current_intent_text":"play something chill","token_budget":1000}'
```
📖 Task file: [`services/retrieval-api/TASKS.md`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/retrieval-api/TASKS.md)

---

### 👤 Member 5 — Context Composer
```bash
cd services/context-composer
pip install fastapi uvicorn openai httpx
uvicorn main:app --reload --port 8003
```
**Test it:**
```bash
curl -X POST http://localhost:8003/v1/context/compose \
  -H "Content-Type: application/json" \
  -d '{"subject_id":"user_01","current_intent_text":"what music do I like?","surface":"music_chat","locale":"en"}'
```
📖 Task file: [`services/context-composer/TASKS.md`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/context-composer/TASKS.md)

---

### 👤 Member 6 — MCP Tools Server
```bash
cd services/memory-mcp-server
pip install fastmcp httpx
python server.py
```
**Test it:** Connect to MCP Inspector at `http://localhost:8005` or use Claude Desktop MCP config.

📖 Task file: [`services/memory-mcp-server/TASKS.md`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/memory-mcp-server/TASKS.md)

---

### 👤 Member 7 — Deletion Orchestrator
```bash
cd services/deletion-orchestrator
pip install fastapi uvicorn asyncpg neo4j qdrant-client redis
uvicorn main:app --reload --port 8004
```
**Test it:**
```bash
curl -X DELETE http://localhost:8004/v1/memories/mem_001
curl http://localhost:8004/v1/deletions/job_001
```
📖 Task files:
- [`services/deletion-orchestrator/TASKS.md`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/services/deletion-orchestrator/TASKS.md)
- [`packages/policy-engine/TASKS.md`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/packages/policy-engine/TASKS.md)

---

### 👤 Member 8 — Frontend Apps
```bash
# User-facing Memory Controls:
cd apps/memory-controls
npm install
npm run dev
# Opens on: http://localhost:3000

# Internal Admin Console:
cd apps/memory-console
npm install
npm run dev
# Opens on: http://localhost:3001
```
📖 Task files:
- [`apps/memory-controls/TASKS.md`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/apps/memory-controls/TASKS.md)
- [`apps/memory-console/TASKS.md`](file:///c:/Users/omsem/OneDrive/Desktop/spotify-personalized-ai-memory-system/apps/memory-console/TASKS.md)

---

## 🔗 Step 6 — All Service Port Reference

Once everything is running, here is where each service lives:

| Service | URL | Owner |
| :--- | :--- | :--- |
| Ingestion API | http://localhost:8001 | Member 1 |
| Retrieval API | http://localhost:8002 | Member 4 |
| Context Composer | http://localhost:8003 | Member 5 |
| Deletion Orchestrator | http://localhost:8004 | Member 7 |
| MCP Server | http://localhost:8005 | Member 6 |
| Memory Controls (UI) | http://localhost:3000 | Member 8 |
| Admin Console (UI) | http://localhost:3001 | Member 8 |
| Neo4j Browser | http://localhost:7474 | Infra (Lead) |
| Qdrant Dashboard | http://localhost:6333/dashboard | Infra (Lead) |

---

## 🔁 Step 7 — Full End-to-End Flow to Test

Once all services are running, test the whole pipeline in this order:

```
1. POST /v1/events         → (Member 1) Send a user event
2. Kafka consumer picks up → (Member 2) Event classified into memory
3. Memory saved            → (Member 3) Written to Neo4j graph
4. POST /v1/memories/search → (Member 4) Search for memories
5. POST /v1/context/compose → (Member 5) Package for LLM
6. LLM Chat response       → (Member 5) AI gives personalized answer
7. DELETE /v1/memories/{id} → (Member 7) User deletes a memory
8. GET /v1/deletions/{job}  → (Member 7) Confirm deletion complete
```

---

## 🛑 Step 8 — Stop Everything

```bash
docker-compose down
```

To also remove all stored data (fresh start):
```bash
docker-compose down -v
```

---

## ❓ Common Issues & Fixes

| Problem | Fix |
| :--- | :--- |
| `Connection refused` to Neo4j | Wait 30s after `docker-compose up` — Neo4j takes time to boot |
| `ModuleNotFoundError: packages.contracts` | Run `pip install -e .` inside `packages/contracts/` |
| Kafka not receiving events | Check `KAFKA_BOOTSTRAP_SERVERS=localhost:9092` is set in `.env` |
| Port already in use | Another app is using that port — change the port in `.env` |

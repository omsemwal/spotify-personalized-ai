# Spotify Personalized AI Memory System

A governed memory layer for Spotify's AI surfaces. It captures eligible
interaction events, resolves them into a versioned temporal graph, retrieves
only what is relevant to the current intent, and hands a bounded, provenanced
context package to an LLM orchestrator — with full user control over
correction, pause, opt-out and deletion.

This is a **product capability pilot, not a general-purpose behaviour archive.**
Every remembered fact carries a source, a confidence score, a policy class, a
valid-time, and is correctable and deletable.

---

## The frontend is a separate repository

The operator consoles deploy separately from this API, so they live on their own:

### → **https://github.com/omsemwal/spotify-fronted**

Next.js, React and Tailwind (`abc.md:200`). Start this backend first — the
consoles are a window onto it and hold no data of their own.

---

## Running it

Full instructions, including troubleshooting, are in **[RUNNING.md](RUNNING.md)**.

**Setup — four commands:**

```bash
pip install -r requirements.txt
cp .env.example .env                 # then add a Gemini key
docker compose up -d                 # postgres, redis, neo4j, redpanda
python scripts/setup.py              # tables, constraints, vector index
```

**Then two terminals:**

```bash
# 1 - the API
python -m uvicorn memory.api:app --reload --port 8000

# 2 - the worker, which turns events into memories
python scripts/run_processor.py --forever
```

Open **http://127.0.0.1:8000/docs**.

**To check it works:**

```bash
python -m pytest -q                  # 401 tests
python scripts/verify_endpoints.py   # all 10 endpoints against the requirements
```

---

## Deployed application

**Not yet deployed.** Add the link here once it is:

**Deployed link:** _to be added_

**Demo video (Google Drive, "anyone with the link can view"):** _to be added_

---

## Architecture

Two processes and four stores. Nothing else.

```
AI surface
    |
    v
API  (memory/api.py, port 8000)  - all ten endpoints, one app
    |  POST /v1/events replies at once and puts the event on the queue
    v
Redpanda (Kafka)
    |
    v
Worker  (scripts/run_processor.py)  - classify, extract, policy check, write
    |
    v
Neo4j  - the temporal graph and the vector index (same memory id)
PostgreSQL - consent, events, audit log, deletion jobs, feedback, traces
Redis  - idempotency keys and rate limits

MCP server (memory/mcp_server.py) - the five tools a model may use,
                                    calling the same API in-process
```

The user path never waits for a graph write (`abc.md:324`): the API accepts
the event and replies; the worker does the slow work afterwards.

How it works end to end: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

---

## Product surfaces

In the frontend repository, https://github.com/omsemwal/spotify-fronted:

- **Memory console** (http://localhost:3000) - the seven operator screens:
  overview, memory explorer, context preview, correction and deletion,
  schema and policy, quality review, audit trace.
- **Memory controls** (http://localhost:3001) - the listener's review,
  correct, remove, pause and opt-out.

---

## APIs - all 10 required (`abc.md` §7.3)

All on `http://127.0.0.1:8000`. Try them at `/docs`.

| # | Endpoint | Doc |
|---|---|---|
| 1 | `POST /v1/events` | [events.doc.md](docs/events.doc.md) |
| 2 | `POST /v1/memories/extract` | [memories-extract.doc.md](docs/memories-extract.doc.md) |
| 3 | `POST /v1/memories` | [memories.doc.md](docs/memories.doc.md) |
| 4 | `POST /v1/memories/search` | [memories-search.doc.md](docs/memories-search.doc.md) |
| 5 | `POST /v1/context/compose` | [context-compose.doc.md](docs/context-compose.doc.md) |
| 6 | `PATCH /v1/memories/{memory_id}` | [memories-patch.doc.md](docs/memories-patch.doc.md) |
| 7 | `DELETE /v1/memories/{memory_id}` | [memories-delete.doc.md](docs/memories-delete.doc.md) |
| 8 | `GET /v1/deletions/{job_id}` | [deletions.doc.md](docs/deletions.doc.md) |
| 9 | `POST /v1/feedback` | [feedback.doc.md](docs/feedback.doc.md) |
| 10 | `GET /v1/traces/{trace_id}` | [traces.doc.md](docs/traces.doc.md) |

All ten in plain words: [apis-explained.doc.md](docs/apis-explained.doc.md).
A code trace per endpoint: [docs/flow/](docs/flow/).

## MCP tools - all 5 required (`abc.md` §5.4)

`search_memory`, `add_explicit_preference`, `correct_memory`, `delete_memory`,
`explain_memory_use`. The server is started for one subject, so no tool can
name another; each call goes through the same auth, consent, validation and
rate limit as the API, and is audited. No generic graph query tool.

```bash
python -m memory.mcp_server user_001
```

Details: [mcp-tools.doc.md](docs/mcp-tools.doc.md).

---

## Data model

| Thing | Where |
|---|---|
| Event contract | `memory/models.py::Event`, frozen copy `data/schemas/event_v1.json` |
| Memory fact | `memory/graph.py` - `valid_from`, `valid_to`, `recorded_at`, `confidence`, `status`, `source_event_ids` |
| Context package | `memory/models.py::ContextPackage` |
| Policy registry | `data/policy_registry.yaml` |
| Entity catalog | `data/catalog.yaml` |
| Golden evaluation set | `data/golden-sets/pilot_golden_set.json` |
| PostgreSQL tables | `infrastructure/database-migrations/*.sql` |

Graph shape:

```
(Memory)-[:ABOUT]->(Entity)
(Memory)-[:SUPERSEDES]->(Memory)     # a correction, keeping history
```

Every `Memory` node carries its `subject_id`, and every query filters on it.
Corrections supersede; they never overwrite.

---

## Environment variables

All in `.env.example`, already matching what `docker compose` starts.

| Variable | Meaning |
|---|---|
| `MEMORY_JWT_SECRET` | Signs the bearer tokens. Change before any deploy |
| `POSTGRES_*` | Operational store |
| `REDIS_*` | Idempotency keys and rate limits |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | Graph and vector store |
| `KAFKA_BOOTSTRAP` | `localhost:19092`, Redpanda's external listener |
| `GEMINI_API_KEY` | The model for extraction (endpoint 2 and the worker) |

---

## Testing

```bash
python -m pytest -q                    # 401 tests, real stores, model replaced
python scripts/verify_endpoints.py     # 62 checks, each citing its abc.md line
python scripts/run_golden_set.py       # 12 golden cases, feeds the Quality screen
```

Run `verify_endpoints.py` with the worker stopped - it checks exact versions,
and a live worker strengthening the same memory changes them.

---

## Screenshots

_To be added: the console's seven screens and the controls app._

---

## Limitations - stated honestly

1. **No LLM answer is generated.** `POST /v1/context/compose` returns the
   context package an AI orchestrator would consume; the orchestrator is
   outside this repository.
2. **Auth is a pilot token** minted with a shared secret
   (`scripts/make_token.py`), standing in for the gateway that would verify a
   real Spotify session.
3. **Extraction needs a Gemini key.** Without one, endpoint 2 returns a clean
   503 and the other nine work.
4. **Not deployed.** It runs locally with `docker compose`.

---

## Team contribution

Single-contributor pilot build.

---

## Repository layout

```
memory/                        the API, the worker logic and the MCP server
scripts/                       setup, worker, token, checks, housekeeping
tests/                         pytest suites against the real stores
data/                          policy registry, catalog, golden set, event schema
infrastructure/                PostgreSQL migrations
docs/                          one doc per API, flows, requirements
docker-compose.yml             the four stores
```

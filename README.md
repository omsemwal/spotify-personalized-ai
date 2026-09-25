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

## Running it

Full instructions, including troubleshooting, are in **[RUNNING.md](RUNNING.md)**.

The short version:

```bash
pip install -r requirements.txt
cp .env.example .env                 # then fill in the values

docker start memory_system_redis memory_system_neo4j memory_system_redpanda
python scripts/check_stores.py       # are the stores reachable?

python -m uvicorn memory.api:app --reload --port 8000
```

Then open **http://127.0.0.1:8000/docs**.

And in a second terminal — without this, events are captured but never become
memories:

```bash
python scripts/run_processor.py --forever
```

To check everything works:

```bash
python -m pytest -q                  # 388 tests
python scripts/verify_endpoints.py   # all 10 endpoints against the requirements
```

---

## Deployed application

**Not yet deployed.** The system runs locally via `docker-compose` plus the six
services (instructions below). Add the reviewed URL here once a controlled
review environment exists — see §6.4 Deployment Flow and §7.8 Deployment
Approach for the intended canary path.

---

## Architecture

```
AI Surface
    |
    v
Ingestion API (8001)  --publishes-->  Redpanda / Kafka
                                          |
                                          v
                              Memory Processor (8006)
                          classify -> policy gate -> write
                                          |
                                          v
                              Temporal Graph (Neo4j)
                                          |
                                          v
                              Retrieval API (8002)
                       graph traversal + vector rerank + policy
                                          |
                                          v
                            Context Composer (8003)
                        bounded, policy-filtered context package
                                          |
                                          v
                     LLM Orchestrator  (outside this repository)

Deletion Orchestrator (8004)  — cross-store erasure + per-store status
MCP Server (8005)             — 5 typed tools for model-driven agents
PostgreSQL                    — deletion jobs, feedback (operational store)
```

Full narrative: `docs/architecture/overview.md`. Diagram:
`docs/architecture/pipeline.md`.

The capture path is **asynchronous**: `POST /v1/events` returns immediately,
the event travels through Kafka, and `services/memory-processor/consumer.py`
turns it into a graph fact. The user path never waits on a graph write (§5.4).

---

## Product surfaces (§5.2)

Two pages, six surfaces. Open them directly from disk — they are plain HTML and
need no build step.

| Surface | Where |
|---|---|
| Memory Experience Console | `apps/memory-console` → **Memory Explorer** tab |
| Memory Control Experience | `apps/memory-controls` |
| Graph and Schema Console | `apps/memory-console` → **Graph & Schema** tab |
| Retrieval Quality Dashboard | `apps/memory-console` → **Quality** tab |
| Operations Monitor | `apps/memory-console` → **Overview** tab |
| Policy Review Panel | `apps/memory-console` → **Policy & Audit** tab |

The console is **read-only** — it never writes events into the system.
The controls page is where a user reviews, corrects, removes, pauses or opts out.

---

## APIs — all 10 required (§7.3)

**One entry point: `http://localhost:8080`.** An nginx API gateway
(§6.4 step 3, §7.8 step 38) fronts every API and MCP tool, attaches an
`X-Correlation-Id` to each request (§7.3 request flow), and rejects any path
that is not part of the published contract. The six services stay separate
processes behind it, and their direct ports remain open for health checks and
per-service API docs.

| # | Endpoint (via gateway on 8080) | Service behind it | Direct port |
|---|---|---|---|
| 1 | `POST /v1/events` | ingestion-api | 8001 |
| 2 | `POST /v1/memories/extract` | memory-processor | 8006 |
| 3 | `POST /v1/memories` | memory-processor | 8006 |
| 4 | `POST /v1/memories/search` | retrieval-api | 8002 |
| 5 | `POST /v1/context/compose` | context-composer | 8003 |
| 6 | `PATCH /v1/memories/{memory_id}` | memory-processor | 8006 |
| 7 | `DELETE /v1/memories/{memory_id}` | deletion-orchestrator | 8004 |
| 8 | `GET /v1/deletions/{job_id}` | deletion-orchestrator | 8004 |
| 9 | `POST /v1/feedback` | context-composer | 8003 |
| 10 | `GET /v1/traces/{trace_id}` | retrieval-api | 8002 |

No other endpoints exist, by design. Example bodies:
`docs/api/api_reference.md`.

## MCP tools — all 5 required (§5.4, §7.5)

`search_memory`, `add_explicit_preference`, `correct_memory`, `delete_memory`,
`explain_memory_use` — typed, subject-bound, rate-limited and audited. A
cross-subject call is refused with `403 unauthorized_subject`. See
`services/memory-mcp-server/README.md`.

---

## Data model

| Thing | Where |
|---|---|
| Event contract | `packages/contracts/events.py::InteractionEvent` |
| Memory fact | `packages/contracts/memory.py::Memory` (`valid_from`, `valid_to`, `recorded_at`, `confidence`, `policy_class`, `status`) |
| Graph shape | `packages/graph-schema/README.md` |
| Context package | `packages/contracts/context.py::ContextPackage` |
| Policy registry | `packages/policy-engine/registry.py` |
| JSON Schema exports | `data/schemas/` (regenerate: `data/schemas/generate_schemas.py`) |

Graph shape:

```
(User)-[:HAS_MEMORY]->(Memory)-[:ABOUT]->(Entity)
(Memory)-[:SUPERSEDES]->(Memory)     # a correction, keeping history
```

Corrections **supersede**; they never overwrite. Deletion is separate and
irreversible.

---

## Environment variables

Full list in `.env.example`. The ones that matter:

| Variable | Meaning |
|---|---|
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | Graph store |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:19092` from the host; `redpanda:9092` inside compose |
| `POSTGRES_HOST` / `POSTGRES_PORT` | `localhost:5433` from the host; `postgres:5432` inside compose |
| `INGESTION_SERVICE_TOKEN` | Pilot bearer token for `POST /v1/events` |
| `EMBEDDING_BACKEND` | `local_hash` (default, offline) or `sentence_transformers` |
| `CORS_ALLOW_ORIGINS` | Origins allowed to call the APIs from a browser |

**Two ports differ from the defaults on purpose.** Redpanda advertises an
external listener on `19092`, and Postgres is published on `5433` because a
natively installed PostgreSQL commonly owns `5432` and would shadow the
container.

---

## Run locally

There is one way to run this, and it needs the datastores. Every service
connects at startup and refuses to start if a dependency is unreachable — see
`docs/PLAN.md` U4 for why the previous "run without databases" mode was removed.

```bash
# 1. Start the datastores and apply the migrations. Docker Desktop must be running.
./scripts/dev.sh up

# 2. Install dependencies
python -m venv .venv
./scripts/dev.sh install

# 3. Start the six services
export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=neo4j_password_secure
export KAFKA_BOOTSTRAP_SERVERS=localhost:19092
export POSTGRES_HOST=localhost POSTGRES_PORT=5433
PY="$PWD/.venv/Scripts/python.exe"; ROOT="$PWD"

for s in "ingestion-api:8001" "retrieval-api:8002" "context-composer:8003" \
         "deletion-orchestrator:8004" "memory-mcp-server:8005" "memory-processor:8006"; do
  name="${s%%:*}"; port="${s##*:}"
  ( cd "$ROOT/services/$name" && nohup "$PY" -m uvicorn main:app --port "$port" > "/tmp/svc_$port.log" 2>&1 & )
done
```

```bash
# 4. Start the API gateway (single entry point on 8080)
docker compose up -d api-gateway
```

**Wait until all six answer.** The ingestion service takes ~25 seconds longer
than the rest because it connects to Kafka on startup:

```bash
for p in 8001 8002 8003 8004 8005 8006; do echo -n "$p: "; curl -s http://localhost:$p/health; echo; done
```

Each `/health` response lists its dependencies and whether they are reachable
right now, and returns 503 if any are not:

```json
{"status": "ok", "service": "ingestion-api",
 "dependencies": {"queue": {"backend": "kafka", "reachable": true},
                  "idempotency": {"backend": "redis", "reachable": true}}}
```

The check re-runs on every call rather than reporting the state at startup, so
stopping a container turns it red.

Every service falls back to in-process adapters. Useful for unit work, but
services do **not** share data in this mode — each keeps its own store.

### Seed demonstration data

```bash
# feeds the synthetic multi-session histories through the real ingestion path
python - <<'EOF'
import json, glob, urllib.request
for path in sorted(glob.glob("data/synthetic/*.json")):
    for ev in json.load(open(path, encoding="utf-8")).get("events", []):
        req = urllib.request.Request("http://localhost:8001/v1/events",
              data=json.dumps(ev).encode(),
              headers={"Content-Type":"application/json",
                       "Authorization":"Bearer dev-ingestion-token"}, method="POST")
        try: urllib.request.urlopen(req, timeout=10)
        except Exception as e: print(path, ev["event_id"], e)
EOF
```

The opt-out event for `u_synth_004` is refused with `consent_denied` — that is
the correct behaviour, not an error.

### Open the product surfaces

Open `apps/memory-console/index.html` and `apps/memory-controls/index.html`
directly in a browser. Both call the gateway on port 8080 only.

Interactive API docs per service, through the gateway:
`localhost:8080/docs/ingestion/`, `/docs/retrieval/`, `/docs/composer/`,
`/docs/deletion/`, `/docs/mcp/`, `/docs/processor/`.

---

## Inspecting the data

| Store | How |
|---|---|
| Graph | Neo4j Browser at `http://localhost:7474` (`neo4j` / `neo4j_password_secure`), then `MATCH (n) RETURN n` |
| Event queue | `docker exec memory_system_redpanda rpk topic consume interaction-events --num 5` |
| Operational store | `docker exec memory_system_postgres psql -U postgres -d memory_system -c "SELECT * FROM deletion_jobs;"` |

---

## Testing

```bash
.venv/Scripts/python.exe -m pip install pytest
.venv/Scripts/python.exe -m pytest tests/ -q
```

Covers unit, integration, contract, security and end-to-end suites. See each
`tests/*/README.md`, and `docs/privacy-and-security/threat_model.md` for how the
security tests map to mitigations. Measured results:
`docs/release_evidence.md`.

---

## Screenshots

Add screenshots of the console (Overview, Memory Explorer, Context Preview,
Quality) and the controls page (memory cards, correction form, deletion
progress) once the stack is running.

---

## Limitations — stated honestly

1. **No LLM response is generated.** `POST /v1/context/compose` returns the
   context package that §7.3 describes as "consumed by an AI orchestrator". The
   orchestrator is outside this repository, so the end-to-end demo stops at the
   package, not a spoken answer.
2. **Vectors are in-process.** `services/retrieval-api/vector_store.py` holds
   embeddings in memory rather than Qdrant or Neo4j vector indexes. They are
   rebuilt from the graph on each search, so behaviour is correct but not
   durable across a restart.
3. **Embeddings are a deterministic hash**, not SentenceTransformers, so the
   pipeline runs offline. Swap with `EMBEDDING_BACKEND=sentence_transformers`.
4. **Auth is a static pilot token** (`services/ingestion-api/auth.py`), not real
   workload identity. Flagged in the threat model's known-gaps section.
5. **Traces and the MCP tool-audit log are in-process** and not exposed by any
   endpoint, so the console cannot display tool-call history.
6. **Rate limiting is per-process**, not shared — needs a Redis-backed limiter
   before horizontal scaling.
7. **Some dashboard metrics are unavailable, not estimated.** Ingestion lag,
   write failures, retries, experiment status, precision/recall and contradiction
   rate are labelled "not instrumented" because no §7.3 endpoint reports them.
   No number is invented.
8. **Redis and Qdrant containers are defined but unused** by application code.
9. **The frontend is plain HTML**, not the Next.js/React/Tailwind that §6.2
   lists as preferred, chosen so every surface is readable in a single file with
   no build step.

---

## Team contribution

Single-contributor pilot build. Ownership of each area maps to the folder that
contains it: `services/*` for the API and workflow layers, `packages/*` for
shared contracts, graph schema and policy, `apps/*` for the product surfaces,
`infrastructure/*` for deployment, and `tests/*` for quality.

---

## Repository layout

Matches §7.1. Every folder under `apps/`, `services/`, `packages/`,
`infrastructure/`, `data/`, `tests/` and `docs/` carries its own `README.md`
explaining what it holds and why.

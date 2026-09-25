# Running this project

Plain bash commands. No tooling beyond Python and Docker.

---

## Once, the first time

```bash
cd "C:/Users/omsem/OneDrive/Desktop/New folder/spotify-personalized-ai"

pip install -r requirements.txt
```

Then copy the settings template and fill it in:

```bash
cp .env.example .env
```

Open `.env` and set:

| Setting | What to put |
|---|---|
| `MEMORY_JWT_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `POSTGRES_PASSWORD` | your local PostgreSQL password |
| `POSTGRES_DB` | `spotify_personalized_ai` |
| `NEO4J_PASSWORD` | `neo4j_password_secure` |
| `GEMINI_API_KEY` | from aistudio.google.com, free tier |

**`.env` is never committed.** `.env.example` is the template; it holds no real
values.

Then create the database tables:

```bash
python - <<'EOF'
import glob, psycopg
from memory import config
for path in sorted(glob.glob("infrastructure/database-migrations/*.sql")):
    with psycopg.connect(config.postgres_url(), autocommit=True) as c:
        c.execute(open(path, encoding="utf-8").read())
    print("applied", path)
EOF
```

---

## Every time — three steps

### 1. Start the stores

Docker Desktop must be running first.

```bash
docker start memory_system_redis memory_system_neo4j memory_system_redpanda
```

PostgreSQL runs as a Windows service and starts on its own.

### 2. Check they are all reachable

```bash
python scripts/check_stores.py
```

```
postgres : OK - PostgreSQL 18.6
           tables: audit_log, consent, deletion_job, feedback, ...
redis    : OK - redis 7.4.11
all reachable
```

If something is missing, nothing below will work — fix it here first.

### 3. Start the API

```bash
python -m uvicorn memory.api:app --reload --port 8000
```

Open **http://127.0.0.1:8000/docs** — every endpoint, with a Try it out button.

---

## And in a second terminal — the worker

```bash
python scripts/run_processor.py --forever
```

**Without this, events are captured but never become memories.** It reads the
queue and runs extraction and storage on its own.

```
handled 1, failed 0, memories stored 2
```

Leave it running while you use the API.

---

## Trying it by hand

**Get a token** (they last 15 minutes):

```bash
python scripts/make_token.py user_001
```

Copy the whole `Authorization: Bearer ...` line into Postman, or into the
**Authorize** button at the top of `/docs`.

**Send an event:**

```bash
curl -X POST http://127.0.0.1:8000/v1/events \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"schema_version":"1.0","subject_id":"user_001",
       "event_type":"ai_interaction","surface":"chat","locale":"en-US",
       "occurred_at":"2026-09-25T10:00:00Z","consent_state":"granted",
       "source_event_id":"src_1","idempotency_key":"try_1",
       "content":"I do not want country music"}'
```

Watch the worker terminal — a memory appears a moment later.

**Then ask what it remembers:**

```bash
curl -X POST http://127.0.0.1:8000/v1/context/compose \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"subject_id":"user_001","intent":"put some music on",
       "surface":"player","token_budget":400}'
```

---

## Checking it works

```bash
python -m pytest -q                    # 388 tests, about 80 seconds
python scripts/verify_endpoints.py     # all 10 endpoints vs the requirements
```

The second one is the better demo: 62 checks, each naming the `abc.md` line it
comes from.

---

## Housekeeping

```bash
python scripts/cleanup_expired.py      # delete raw events past 30 days
python scripts/expire_memories.py      # mark memories past their retention
```

In production both belong on a schedule.

---

## When something is wrong

| Symptom | Cause | Fix |
|---|---|---|
| `401 UNAUTHENTICATED` | The token expired — they last 15 minutes | `python scripts/make_token.py user_001` |
| `403 CONSENT_DENIED` | No consent row for that subject | Use `user_001`, `user_002` or `user_003` |
| `503 SERVICE_UNAVAILABLE` | Gemini is busy, or the key is missing | Wait a minute, or check `GEMINI_API_KEY` in `.env` |
| `429 RATE_LIMITED` | More than 120 requests in a minute | Wait for the next minute |
| Redis errors | Docker is not running | Start Docker Desktop, then `docker start memory_system_redis` |
| Events captured but no memories appear | The worker is not running | `python scripts/run_processor.py --forever` |
| `KafkaTimeoutError` | Wrong port — 9092 is internal to Docker | `.env` should say `KAFKA_BOOTSTRAP=localhost:19092` |

---

## The test subjects

Seeded by the migration, so there is always something to try:

| Subject | Consent | Use for |
|---|---|---|
| `user_001` | granted | Normal testing |
| `user_002` | granted | Checking one subject cannot see another's memories |
| `user_003` | granted | Spare |
| `user_004` | **denied** | Checking consent is enforced |
| `user_005` | **paused** | Checking the no-memory fallback |

---

## Looking inside

**Neo4j** — http://localhost:7474, log in `neo4j` / `neo4j_password_secure`:

```cypher
MATCH (m:Memory {subject_id: 'user_001'}) RETURN m
MATCH (m:Memory)-[:ABOUT]->(e:Entity) RETURN m, e
```

**PostgreSQL:**

```bash
psql -U postgres -d spotify_personalized_ai -c "SELECT * FROM audit_log ORDER BY id DESC LIMIT 10"
```

**Redpanda:**

```bash
docker exec memory_system_redpanda rpk topic list
```

---

## Where to read more

| | |
|---|---|
| `docs/apis-explained.doc.md` | All ten APIs in plain words |
| `docs/flow/` | A code trace per API — function by function |
| `docs/REQUIREMENTS.md` | What the project has to deliver |

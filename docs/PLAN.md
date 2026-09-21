# Build Plan — Spotify Personalized AI Memory System

**Status:** planning complete, no implementation started
**Source of truth:** `projcet requirements.pdf` (root of this repo). `abc.md` is a
plain-text copy of the same document — use it for searching, use the PDF when the
two ever disagree.
**Last updated:** 2026-09-21

---

## How to read this document

Read sections 1–4 once to understand what we are building and why. Then work
from section 7, which is the actual to-do list. Section 6 lists the decisions
that are still yours to make — some of them block work, and they are marked.

If a word in here is unfamiliar, check section 3 (glossary) before moving on.
Nothing in this plan assumes you already know Neo4j, Kafka or MCP.

---

## 1. What we are building, in plain words

Imagine you talk to a Spotify AI assistant on Monday and say *"I like low-vocal
music when I am working."* On Friday you ask it for something to work to. Today,
Friday's assistant has no idea Monday ever happened — it starts from zero every
time.

We are building the piece that fixes that: a **memory layer**. It sits between
Spotify's AI features and the language model that writes the replies.

Its job is *not* to remember everything. That is the trap the requirements
document warns about repeatedly. Its job is to remember **a few things, well**:

- remember only what is worth remembering (a stated preference, not a random skip),
- know *when* each thing was true, and stop using it when it stops being true,
- be able to explain where every remembered fact came from,
- let the user read, fix, pause or delete any of it, and have that actually
  take effect everywhere,
- and hand the language model a small, checked package of facts — never raw
  database access.

The document's own summary (§12): *"a shared product capability for continuity,
not a general-purpose archive of user behavior."*

### The eight-step loop

Everything in the requirements is a detail of one of these eight steps. Keep
this picture in your head; it is the whole system.

```
1. capture          an AI surface sends us an interaction event
2. extract          we decide what (if anything) is worth remembering
3. write graph      we store it as a fact with a start time and an end time
4. embed            we make a vector of it so we can search by meaning
5. retrieve         at reply time, we fetch candidate memories for this request
6. rank + govern    we score them, and the policy engine throws out what is not allowed
7. compose          we build a small, bounded context package with sources attached
8. generate         the LLM replies; we record what influenced it and collect feedback
```

Steps 1–4 are the **write path** (happens in the background, user never waits).
Steps 5–8 are the **read path** (happens live, must be fast, must never break
the user's experience).

---

## 2. What we are being scored on

The document (§9) allocates 100 marks. This is what decides where the effort goes:

| Area | Marks | What it really means |
|---|---:|---|
| AI workflow | 15 | Extraction, ranking, composition, structured model outputs |
| Graph, embeddings, memory quality | 15 | Temporal integrity, provenance, top-k precision, corrections, expiry |
| Reliability, privacy, safety | 14 | Subject isolation, safe fallback, consent, deletion, prompt-injection defence |
| Backend & API | 12 | Typed contracts, auth, idempotency, queue, stable errors, audit |
| Product experience | 10 | The two web UIs |
| Product understanding | 8 | Can you explain the business framing |
| Deployment readiness | 8 | Reproducible envs, migrations, secrets, health checks, a live URL |
| Documentation | 6 | README, architecture, API/MCP contracts, runbooks |
| Demo | 6 | A credible end-to-end walkthrough video |
| Team collaboration | 6 | Clear ownership and contribution evidence |

**The hard gate.** §9 also says: *"Any critical privacy, security, cross-subject
isolation, or deletion failure blocks release regardless of aggregate score."*

Two consequences for how we build:

1. **AI + graph + safety = 44 marks.** That is where the real work is. Not in
   adding endpoints — the endpoint list is fixed at ten and we already have ten.
2. **Deletion and subject isolation are pass/fail.** If a deleted memory can
   still be retrieved, or user A's memory can reach user B, nothing else
   matters. Those get real tests, not smoke tests.

---

## 3. Glossary

Plain definitions of the terms this plan uses. Skip what you already know.

| Term | What it means here |
|---|---|
| **Subject** | The user a memory belongs to. "Subject-scoped" means a query can only ever see one user's data. |
| **Interaction event** | One thing that happened: a message, a play, a save, a skip, a correction. The input to the whole system. |
| **Memory fact** | Something we decided to remember, e.g. *"prefers low-vocal music while working"*. Has an id, a source, a confidence, a start time and maybe an end time. |
| **Temporal graph** | A database of dots and arrows where every arrow also records *when it was true*. Lets us say "this was true from March to June" instead of overwriting history. |
| **Neo4j** | The graph database we use. Its query language is Cypher. |
| **Valid-from / valid-to** | The window during which a fact was true. Closing `valid_to` retires a fact without deleting it. |
| **Supersession** | When a new fact replaces an old one, we close the old one and link the new one to it. The old one stays readable for audit. |
| **Provenance** | The paper trail: which event produced this fact, when, with what confidence. |
| **Embedding / vector** | A list of numbers representing the *meaning* of a sentence. Two sentences that mean similar things get similar numbers, so we can search by meaning, not by keyword. |
| **Vector index** | The structure that makes "find the most similar vectors" fast. |
| **Hybrid retrieval** | Getting candidates two ways at once — following graph relationships *and* vector similarity — then merging. |
| **Rerank** | Scoring the candidates against the current request and keeping only the best few. |
| **Context package** | The small, structured bundle of facts we hand the LLM. Bounded in size, each item carrying its source and why it was included. |
| **Token budget** | A hard cap on how much text we are allowed to put in that package. |
| **Policy engine** | The gate that decides whether a memory may be written, and later whether it may be used. Returns a reason code when it says no. |
| **Policy class / sensitivity** | A label on each memory type saying how carefully it must be handled. |
| **Consent state** | Whether this user allowed memory at all — granted, partial or denied. |
| **Idempotency key** | A client-supplied id that lets us detect a duplicate request and not write it twice. |
| **Queue (Kafka / Redpanda)** | A durable pipe. The API drops the event in and returns immediately; a worker picks it up later. This is what keeps the user from waiting on a database write. Redpanda is a lighter drop-in replacement for Kafka. |
| **DLQ (dead letter queue)** | Where events go when processing them fails, so they can be inspected and replayed instead of lost. |
| **Fail open (to no-memory)** | If anything in the memory path is slow or broken, we return *"no memory"* and let the AI answer without personalization. We never return half a result. |
| **MCP (Model Context Protocol)** | A standard way to give a model a small set of named, typed tools instead of raw database access. We expose exactly five. |
| **Prompt injection** | An attack where text we stored (because a user typed it) later gets read by the model as an instruction. Defence: always pass stored text as *data*, never glued into the instruction. |
| **Golden set** | Hand-written test cases with the expected answer, used to measure retrieval quality objectively. |
| **p95 latency** | The time under which 95% of requests finish. Our budget is 250 ms. |
| **OpenTelemetry / Prometheus / Grafana** | Tracing (follow one request across services) / metrics (numbers over time) / dashboards. |

---

## 4. Where the project stands today

The repo already has ~6,200 lines, 15 passing tests, and a folder layout that
matches §7.1 of the spec exactly. Here is the honest assessment.

### Good — keep it

| Thing | Why it is good |
|---|---|
| `packages/contracts/` | One shared, versioned set of Pydantic models. No service defines its own event type. This is the correct spine for the whole system. |
| `packages/policy-engine/` | Rules live in a registry separate from the engine, and every rejection returns a **stable reason code** — which §7.3 explicitly asks for. |
| `services/retrieval-api/reranker.py` | Actually implements all seven ranking signals from §5.4, plus the diversity cap so one preference cannot dominate. |
| `packages/graph-schema/graph.py` | Real, correct Cypher, including a subject-filtered vector search. |
| `docker-compose.yml` | All six stores plus the nginx gateway and six services are already declared. |
| Folder layout, 10 endpoints, 5 MCP tools | Match the spec exactly, with nothing extra. |

### Shallow — works, but is not really doing the job

| Thing | Problem |
|---|---|
| `classifier.py` | Decides memory type by reading `payload["explicit"]` and `payload["is_exclusion"]` — flags the *caller* sends. So the client classifies and we copy. The 15-mark AI category is currently a pass-through. |
| `embeddings.py` | A hash-bucket toy embedder. *"low-vocal focus music"* and *"instrumental while studying"* score near zero similarity. Semantic search does not actually work. |
| `entity_resolution.py` | A 10-row alias table. Everything not in it becomes `unresolved:whatever`. |
| `composer.py` | Estimates tokens as `len(text)/4` and does no contradiction handling. |
| `tests/` | 15 tests, all happy-path, all against in-memory doubles. |

### Must fix

| Thing | Problem |
|---|---|
| **Silent fallbacks** | `LOCAL_MODE` defaults to `true` everywhere, and every adapter catches connection errors and quietly falls back to a Python dictionary. **A dead Neo4j looks exactly like a healthy one.** The README describes an architecture the running code is not using. This is the single most dangerous thing in the repo. |
| `llm_extractor.py` | Calls **Gemini**, not Claude, and returns `[]` on any failure — so with no API key, "AI extraction" is pure if-statements and nothing says so. |
| Frontend | Two static HTML files. §6.2 and §7.1 ask for Next.js apps, and §10 wants a deployed URL. |
| Engineering basics | No CI, no linter config, no type checking, no dependency lock file. |
| Evaluation | Golden set is 71 lines, with no thresholds, no CI gate and no memory-on vs memory-off comparison. §9 wants *measured* uplift. |
| Observability | A tracing helper exists but nothing is wired — no OpenTelemetry, no `/metrics`, no dashboards. |
| Housekeeping | Empty stray `fils` file, a deleted `packages/pathutil`, and nine files of uncommitted drift. |

### The verdict

**Keep the skeleton.** The layout is spec-shaped and the contracts and policy
engine are genuinely good. Then do three things: remove the silent fallbacks so
we are running against real infrastructure, build the AI and graph core for
real, and replace the frontend.

---

## 5. Architecture we are building

### Decided

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI + Pydantic v2, six services behind an nginx gateway on `:8080` | §6.2; already scaffolded |
| Queue | Redpanda (speaks the Kafka protocol) | §6.2; lighter than Kafka, same client code |
| Graph | Neo4j 5 | §6.2; the spec names it directly |
| Vectors | Neo4j's built-in vector index | Same node holds the fact *and* its vector, so deleting the fact deletes the vector. Graph and vector state cannot drift apart. |
| Embeddings | SentenceTransformers `all-MiniLM-L6-v2` | §6.2; model version recorded with every vector |
| Operational store | PostgreSQL | Consent, deletion jobs, feedback, audit, experiment cohorts |
| Cache / idempotency | Redis, short TTL, subject-scoped | §6.2 |
| Extraction | **Claude API**, `claude-sonnet-5`, structured output, temperature 0 | Your decision; §7.5 requires structured model output |
| Frontend | **Two Next.js apps** + Tailwind, deployed to Vercel | Your decision; matches §7.1's folder list |
| Observability | OpenTelemetry → Prometheus → Grafana | §6.2 |

### The one rule that replaces silent fallback

> A service reads its dependency configuration at boot and **refuses to start**
> if it cannot reach that dependency. The in-memory stores survive only as
> explicit test doubles that tests inject. They are never a runtime fallback.

The *only* legitimate fallback in this system is the one the spec names: the
retrieval path failing open to an explicit **no-memory** response (§5.5
Reliability). That is a product behaviour, not an error handler.

### Request flow, end to end

```
Browser / AI surface
        |
        v
  nginx gateway :8080  -- authenticates, attaches X-Correlation-Id
        |
        |--> ingestion-api :8001      POST /v1/events
        |        \--> Redis (idempotency) --> Redpanda topic --> DLQ on failure
        |
        |    memory-processor :8006   (queue consumer, background)
        |        \--> Claude extraction --> validators --> policy gate
        |                 \--> Neo4j (fact + vector on one node)
        |
        |--> retrieval-api :8002      POST /v1/memories/search
        |        \--> Neo4j traversal + vector search + Postgres recent signals
        |                 \--> rerank --> policy filter
        |
        |--> context-composer :8003   POST /v1/context/compose
        |        \--> token budget --> provenance --> no-memory fallback
        |
        |--> deletion-orchestrator :8004   DELETE /v1/memories/{id}
        |        \--> Neo4j + vector + Redis + Postgres, per-store status
        |
        \--> memory-mcp-server :8005  five typed tools, subject-bound, audited
```

---

## 6. Decisions still to make

Work through these. The ones marked **blocking** stop a unit from starting.

| # | Decision | Notes | Blocks |
|---|---|---|---|
| D1 | **Python version** — *blocking* | The venv is on Python **3.14**. SentenceTransformers depends on PyTorch, which typically lags new Python releases by months. Verify `pip install torch sentence-transformers` works on 3.14; if it does not, pin the project to **Python 3.12**. Do this first — it is cheap to check and expensive to discover late. | U1, U8 |
| D2 | **Anthropic API key and budget** — *blocking* | Extraction calls `claude-sonnet-5`. Get a key, put it in `.env` (never in git). Plan: record real responses as fixtures the first time, then replay them in tests and the demo, so CI and the video cost nothing and never flake. | U6 |
| D3 | **Where the backend is deployed** | §10 wants a working deployed link. Vercel hosts the two Next.js apps, but it will not host six containers plus five databases. Options: (a) a small VM, or Render / Railway / Fly for the backend; (b) deploy the frontend only and demo the backend locally in the video, being explicit about it in the README. Option (a) scores better on the 8 deployment marks; (b) is free. | U17 |
| D4 | **Auth depth for the pilot** | Today it is static bearer tokens in a dictionary. Options: keep that and document it as a pilot limitation, or issue short-lived signed JWTs. §5.5 says every read and write must bind to an authenticated subject — JWTs make the subject binding in U12 much more convincing. | U5, U12 |
| D5 | **Drop Qdrant?** | `docker-compose.yml` declares Qdrant, but we chose Neo4j's native vector index. §6.2 lists them as alternatives, so using one is correct. Recommend removing Qdrant to cut one moving part — but that is a deletion, so confirm it first. | U4, U8 |
| D6 | **Demo dataset** | `data/synthetic/` has six user histories. Decide which two or three the demo video follows, so the walkthrough is one coherent story rather than a tour of endpoints. | U13, U17 |
| D7 | **Static HTML pages** | When the Next.js apps land, do the old `apps/*/index.html` files get deleted, or kept as a fallback? Recommend deleting — two UIs claiming to be the same surface is confusing to a reviewer. | U15, U16 |

---

## 7. The work: 17 units

Each unit is one branch, one pull request, tests written **in the same PR** as
the code, merged only when CI is green. If a unit does not finish, we iterate on
it before starting the next one — we do not stack unfinished work.

Branch naming: `u01-repo-hygiene`, `u02-contracts`, and so on.
The remote is already set up: `github.com/omsemwal/spotify-personalized-ai`.

---

### Phase A — Foundations

Nothing else is safe to build until these three are done.

#### U1 · Repo hygiene and CI

**Why:** right now nothing stops a broken commit from landing, and the repo has
uncommitted drift and stray files. Every later unit depends on "CI is green"
actually meaning something.

**Do:**
- Resolve D1 (Python version) before anything else.
- Delete the empty `fils` file; commit or revert the nine drifted files.
- Add `ruff` (linter), `mypy` (type checker), a single `pytest.ini`, and
  `requirements-dev.txt`.
- Add a `Makefile` with `make install`, `make test`, `make lint`, `make up`.
- Add a GitHub Actions workflow: lint → type check → tests, on every PR.

**Done when:** a PR shows a green check, and deliberately breaking one test
turns it red.

---

#### U2 · Memory taxonomy and contract freeze

**Why:** §7.2 says define the taxonomy *before* writing code against it.
Everything downstream — the policy registry, the extraction prompt, the UI
labels — has to agree on the same five memory types.

**Do:**
- Write `docs/architecture/memory_taxonomy.md`. For each of the five types
  (`explicit_preference`, `exclusion`, `correction`, `candidate_preference`,
  `episode`) record: a plain-English definition, an example, a
  **counter-example**, sensitivity, retention period, and retrieval eligibility.
  The counter-examples matter most — they are what stops the extractor drifting.
- Complete the contracts in `packages/contracts/`: retrieval candidate, policy
  decision, and vector record are missing.
- Export every contract to JSON Schema into `data/schemas/`.

**Tests:** a backward-compatibility test that fails if a required field is
renamed or removed (§7.7 "Contract").

---

#### U3 · Policy engine v2

**Why:** this is the gate for 14 marks' worth of privacy and safety, and it is
currently missing half its inputs.

**Do:**
- Move the registry out of Python constants into a YAML file, so a policy change
  is a reviewable data change (§7.5 asks for governed policy changes).
- Add what is missing: partial consent, **pause**, **opt-out**, geography,
  age-related handling, and expiry.
- Delete the dead branch at the end of `evaluate_retrieval` — it computes a
  surface check and then does nothing with it.

**Tests:** table-driven over every registry entry × every context combination.
Assert that every denial carries a stable reason code, because the API contract
and the UI both depend on those codes.

---

### Phase B — Write path (steps 1–4 of the loop)

#### U4 · Real infrastructure, no silent fallback

**Why:** the highest-risk fix in the plan. Until this lands, every test result
and every demo is potentially meaningless, because the code may be running
against Python dictionaries while claiming to use Neo4j.

**Do:**
- `docker compose up` brings Postgres, Neo4j, Redis and Redpanda to healthy.
- Run migrations before traffic: Neo4j constraints and indexes, Postgres tables
  (both files already exist in `infrastructure/database-migrations/`).
- Rewrite every adapter (`queue_adapter`, `idempotency_adapter`, the three
  `store_factory` files) to fail loudly on a connection error instead of
  swallowing it.
- Move the in-memory stores into `tests/` as explicit doubles.
- Resolve D5 (Qdrant).

**Done when:** stopping the Neo4j container turns the processor's health check
red, instead of it quietly continuing to "work".

---

#### U5 · Ingestion API for real

Endpoint 1 of 10: `POST /v1/events`.

**Why:** §5.4 requires capture to be asynchronous so the user never waits on a
graph write, and duplicate events must not double-write.

**Do:**
- Idempotency keys in Redis with a 24-hour TTL.
- Publish accepted events to a Redpanda topic; failures go to a DLQ topic.
- Keep raw-event retention separate from memory retention (§5.4 — not every
  event becomes a memory, and they expire on different clocks).
- Reject malformed, unauthenticated, out-of-policy and unsupported-version
  events *before* the queue, each with its stable error code.

**Tests:** a duplicate key produces exactly one message on the topic; a
malformed event returns 400 with a stable code; denied consent never reaches
the queue.

---

#### U6 · Extraction and entity resolution ← *the biggest scoring unit*

**Why:** this is most of the 15 "AI workflow" marks, and it is the weakest part
of the repo today.

**Do:**
- Replace the Gemini call with **Claude** (`claude-sonnet-5`), using a typed
  output schema, temperature 0, and the system instruction §7.5 specifies:
  role, allowed taxonomy, prohibited inferences, subject boundary, temporal
  rules, and the requirement to return *no memory* when evidence is thin.
- Keep deterministic validators on top, and treat the model as untrusted:
  ids are computed by us (never taken from the model), memory types outside the
  taxonomy are dropped rather than coerced, confidence is clamped, entities are
  re-resolved through our own table.
- Rewrite `classifier.py` so it reads the actual language of the event instead
  of trusting `payload["explicit"]` from the caller.
- Build a real synthetic catalog — artists, tracks, albums, playlists, shows,
  episodes, topics, activities — with an alias table and a confidence threshold
  for ambiguous concepts (§7.2 step 4).
- Record real Claude responses as fixtures so tests and the demo replay offline.

**Tests:** golden extraction cases covering multilingual phrasing, temporary
context (*"just this week"* must **not** become durable), adversarial stored
text, and the case where the correct answer is *nothing at all*.

---

#### U7 · Temporal graph for real

**Why:** 15 marks, and the thing that makes this a *memory* system rather than a
key-value store.

**Do:**
- Every relationship carries `valid_from`, `valid_to`, `recorded_at`,
  `source_event_id`, `confidence`, `policy_class`, `status`.
- A contradiction or correction **supersedes**: close the old fact's `valid_to`
  and link the new one to it. Never overwrite, never silently delete.
- Expiry closes valid-time and marks the fact expired — it stays in the graph.
- The subject partition key is enforced in **every single query**, with no
  exceptions, so a traversal physically cannot cross into another user's data.
- Idempotent upserts, so replaying the same event twice changes nothing.

**Tests:** run these against a live Neo4j, not a double — supersession,
contradiction, expiry, idempotent double-write, and cross-subject traversal
returning zero rows.

---

#### U8 · Embeddings and vector alignment

**Why:** §7.2 step 6 — *"updates and erasure remain deterministic"*. If graph
and vector state can drift apart, deletion is not provable.

**Do:**
- Real embeddings via SentenceTransformers, replacing the hash toy.
- Generate a vector **only after** the policy gate approves the fact.
- Store the memory id, embedding model version, text-field version and deletion
  status alongside every vector.

**Tests:** an invariant test — every active fact has exactly one live vector,
and every deleted fact has none. Run it after each of the other lifecycle tests.

---

### Phase C — Read path (steps 5–7 of the loop)

#### U9 · Retrieval and ranking

Endpoints 4 and 10: `POST /v1/memories/search`, `GET /v1/traces/{trace_id}`.

**Do:**
- Classify the current intent.
- Generate **bounded** candidates three ways: graph traversal (relational),
  vector search (semantic), and recent explicit signals from Postgres.
- Feed the existing reranker with real inputs — it is already correct.
- Short-lived, subject-scoped Redis cache.
- Keep p95 under the 250 ms budget from §5.5.
- Record a trace of every decision; serve it redacted via `/v1/traces/{id}`.

**Tests:** precision@k against the golden set; a forced timeout returns
**no-memory**, never a partial or cross-subject result.

---

#### U10 · Context composition

Endpoint 5: `POST /v1/context/compose`.

**Do:**
- Count tokens with a real tokenizer, not `len/4`.
- Suppress contradicted facts at compose time, not just at write time.
- Every item carries its provenance and a relevance reason.
- Stored text is emitted strictly as structured data — never concatenated into
  an instruction string. This is the prompt-injection defence (§5.4).
- Return an explicit no-memory result when confidence or system health is
  insufficient, and say which of the two it was.

**Tests:** the budget is genuinely enforced; an injection payload sitting inside
a stored fact cannot reach an instruction position in the output.

---

### Phase D — User control and governance

These two are the **pass/fail gate** from §9. Less interesting to build, equally
important.

#### U11 · Correction, pause, opt-out and deletion

Endpoints 3, 6, 7, 8, 9.

**Do:**
- A deletion job row in Postgres, propagating to Neo4j, the vector index, the
  Redis cache and the operational store.
- **Per-store status, and no silent partial completion** — if one store fails,
  the job reports `partial`, never `complete`. §5.4 is explicit about this.
- Correction uses optimistic concurrency (the `expected_version` field is
  already in the contract).
- Feedback is recorded without automatically reinforcing model-generated claims
  (§5.4 Experimentation).

**Tests:** after a delete, retrieval returns nothing from *every* store; a
forced single-store failure surfaces as `partial`.

---

#### U12 · MCP server hardening

**Do:**
- Derive the subject from the authenticated token in **all five** tools. Two of
  them currently take `subject_id` as a plain function argument, which means the
  caller gets to assert who they are.
- Authorization check, rate limit, and one audit row per call.
- Version the tool contracts; never expose a generic graph query tool (§5.4).

**Tests:** a cross-subject call returns 403; the rate limit trips; an audit row
exists for every call, including the rejected ones.

---

### Phase E — Proving it works

#### U13 · Golden sets and evaluation gates

**Why:** §9 wants *measured* improvement, not a claim.

**Do:**
- Build the seven scenario families §7.7 names: stable preference, temporal
  change, contradiction, multilingual, sparse history, malicious stored text,
  and opt-out / deletion.
- The scorer reports precision@k, contradiction rate, provenance completeness,
  entity-resolution accuracy and deletion propagation — **and compares
  memory-enabled against memory-disabled**, which is the number leadership asked
  for in §2.
- Thresholds fail CI, so quality cannot silently regress.

---

#### U14 · Observability and operations

**Do:**
- OpenTelemetry spans covering intake → extraction → graph write → retrieval →
  ranking → policy filter → context injection, so one response links to one trace.
- A `/metrics` endpoint per service: ingestion lag, write failures, retrieval
  latency, cache hit rate, fallback rate, deletion backlog, policy rejection rate.
- A Grafana dashboard, and the alerts in `infrastructure/monitoring/alerts.yml`.
- Redact sensitive payloads from logs while keeping the identifiers you need to
  investigate (§5.4).
- A DLQ replay tool that is idempotent, so replaying cannot create duplicates.

---

### Phase F — Product surfaces and release

The frontend is a separate track. It only needs the API shapes, so **it can
start as soon as U2 freezes the contracts** — it does not have to wait for the
backend to be finished.

#### U15 · `apps/memory-controls` — the user-facing app

Next.js + Tailwind. This is what a listener sees.

- Review what was remembered, in plain language — no graph internals
  (§5.5 Usability).
- Correct a memory, remove one, pause memory, opt out entirely.
- Show propagation status honestly, including partial states.

#### U16 · `apps/memory-console` — the internal app

Next.js + Tailwind. The surfaces §7.6 lists:

- **Overview** — service health, ingestion lag, retrieval SLO, fallback rate,
  deletion backlog.
- **Memory explorer** — subject-scoped timeline with source, confidence, status.
- **Context preview** — the one reviewers will care about most: type an intent
  and a surface, and see candidate retrieval → ranking → policy removals → the
  final context pack → token usage.
- **Schema and policy view** — read-only: versions, allowed fields, retention,
  sensitivity.
- **Quality review** — golden-set runs, failure clusters, memory-on vs
  memory-off side by side.
- **Audit trace** — tool calls, decisions, memory ids, timestamps, redacted
  outcomes.

#### U17 · Deployment, documentation and demo

- Both Next.js apps to Vercel; the backend per decision D3.
- `.env.example` with every variable and no secrets.
- README: setup, architecture, screenshots, the deployed URL, API and MCP
  contracts, data model, **limitations**, and contribution ownership (§10).
- The demo video: capture → graph write → retrieval → context injection →
  personalized response → correction → deletion → fallback. One coherent story
  using the users chosen in D6.
- Fill `docs/release_evidence.md` with real measured numbers, not placeholders.

---

## 8. Order of work

The spine is a hard chain — you cannot rank what you have not written, and you
cannot write what you have not extracted:

```
U1 -> U2 -> U3 -> U4 -> U6 -> U7 -> U8 -> U9 -> U10
                   \-- U5 (can run alongside U6 and U7)
```

Once U10 is merged, three tracks open in parallel:

```
U10 --+--> U11 -> U12          (control and governance)
      +--> U13 -> U14          (evaluation and operations)
      +--> U15 / U16 -> U17    (frontend and release)
```

And the frontend track can actually begin right after **U2**, since it only
needs the API contracts to exist.

---

## 9. Progress checklist

- [ ] **U1** Repo hygiene and CI
- [ ] **U2** Memory taxonomy and contract freeze
- [ ] **U3** Policy engine v2
- [ ] **U4** Real infrastructure, no silent fallback
- [ ] **U5** Ingestion API for real
- [ ] **U6** Extraction and entity resolution
- [ ] **U7** Temporal graph for real
- [ ] **U8** Embeddings and vector alignment
- [ ] **U9** Retrieval and ranking
- [ ] **U10** Context composition
- [ ] **U11** Correction, pause, opt-out and deletion
- [ ] **U12** MCP server hardening
- [ ] **U13** Golden sets and evaluation gates
- [ ] **U14** Observability and operations
- [ ] **U15** `memory-controls` app
- [ ] **U16** `memory-console` app
- [ ] **U17** Deployment, documentation and demo

---

## 10. Where to start, concretely

Your first working session, in order:

1. **Check D1.** Try `pip install torch sentence-transformers` on Python 3.14.
   If it fails, rebuild the virtual environment on Python 3.12. Five minutes,
   saves a day.
2. **Start U1.** Create the branch `u01-repo-hygiene`, delete `fils`, deal with
   the nine drifted files, add the lint / type / test configuration and the CI
   workflow.
3. **Open the pull request and watch CI go green.** That green check is what
   every later unit leans on.

Then work down the checklist in section 9, following the order in section 8.

---

## 11. Two risks worth repeating

1. **The silent-fallback pattern is the biggest risk in this repo**, bigger than
   any missing feature. Today a reviewer could run the stack, see everything
   "work", and be looking at Python dictionaries. U4 fixes it, and it should not
   be deferred.
2. **Deletion and subject isolation are pass/fail** under §9, regardless of how
   good everything else is. U11 and U12 are not optional polish.

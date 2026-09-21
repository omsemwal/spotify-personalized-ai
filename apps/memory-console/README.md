# apps/memory-console

**What this is:** The internal Memory Experience Console (§5.3 product
surfaces): context preview, subject-scoped memory search, and trace
inspection — the "Investigate a quality issue" journey.

## Why static HTML/JS instead of Next.js for the pilot
§6.2 recommends Next.js/React/Tailwind for the production frontend. This
pilot ships a single self-contained `index.html` (no build step, no `npm
install`) that calls the same APIs directly, so the console is runnable and
demonstrable with zero additional tooling. **Before wider rollout, port this
to the Next.js app described in §6.2** — the API contracts it calls
(`POST /v1/context/compose`, `POST /v1/memories/search`, `GET /v1/traces/{id}`)
do not change either way.

## Run
Open `index.html` directly in a browser once `context-composer` (`:8003`),
`retrieval-api` (`:8002`), and friends are running (`docker-compose up`), or
serve it with any static file server:
```bash
python3 -m http.server 3000
```

## Panels
- **Context Preview** — calls `POST /v1/context/compose`; shows the composed
  items, provenance, token budget, and fallback state.
- **Subject-Scoped Memory Timeline** — calls `POST /v1/memories/search`.
- **Trace Inspector** — calls `GET /v1/traces/{trace_id}` with the id returned
  by a prior Compose Context call.

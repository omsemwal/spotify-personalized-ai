# apps/memory-controls

**What this is:** The user-facing Memory Control Experience (§5.3): "Spotify
remembered this preference," with correction, deletion, and inspection —
mirrors the "Correct a memory" and "Remove or pause memory" journeys in §5.3.

## Why static HTML/JS for the pilot
Same reasoning as `apps/memory-console` — no build tooling required to run
and demo it. Production should port this to Next.js/React per §6.2, keeping
the same three calls: `POST /v1/memories/search` (view), `PATCH
/v1/memories/{id}` (correct), `DELETE /v1/memories/{id}` (remove).

## What it shows the user
- Their eligible memories in plain language, never a raw graph view (§5.4
  Product Design Lead: "Users should not see a technical graph").
- A one-click **Remove this memory** button that calls the deletion
  orchestrator and reports back the job id/status — never a silent action.
- A correction form that calls `PATCH /v1/memories/{id}` — the new fact
  supersedes the old one immediately.

## Run
```bash
python3 -m http.server 3001   # serve this folder, or just open index.html directly
```
Requires `retrieval-api` (:8002), `memory-processor` (:8006), and
`deletion-orchestrator` (:8004) running.

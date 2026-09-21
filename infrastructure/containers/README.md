# infrastructure/containers

**What this is:** Build tooling for the 6 service container images. Each
Dockerfile actually lives next to its service (`services/<name>/Dockerfile`)
because it needs to COPY both `packages/` and its own service directory into
the image — this folder holds the cross-service build orchestration instead.

## Files
- `build_all.sh` — builds all 6 images (`ingestion-api`, `memory-processor`,
  `retrieval-api`, `context-composer`, `memory-mcp-server`,
  `deletion-orchestrator`) from the repo root as build context.

## Why repo-root build context
Every Dockerfile does `COPY packages /app/packages` — packages/contracts is
the shared dependency every service needs, so the build context must be the
repo root, not the individual service folder. See any `services/*/Dockerfile`
for the exact COPY layout.

## Run
```bash
./infrastructure/containers/build_all.sh
docker-compose up -d   # brings up infra (postgres/neo4j/redis/redpanda/qdrant) + built service images
```

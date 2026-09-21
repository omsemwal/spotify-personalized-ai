#!/usr/bin/env bash
# Builds every service's container image from the repo root build context,
# since each Dockerfile COPYs packages/ alongside its own service/ directory.
set -euo pipefail
cd "$(dirname "$0")/../.."

SERVICES=(ingestion-api memory-processor retrieval-api context-composer memory-mcp-server deletion-orchestrator)
for svc in "${SERVICES[@]}"; do
  echo "Building $svc..."
  docker build -f "services/$svc/Dockerfile" -t "spotify-memory/$svc:latest" .
done
echo "All service images built."

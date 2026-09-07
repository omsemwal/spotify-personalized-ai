# 🐳 Infrastructure Containers Guide & Tasks

**Folder**: `infrastructure/containers/`  
**Purpose**: Multi-stage Dockerfiles and container configurations for local development and cloud production deployments.

---

## 📋 What We Do Inside
1. **Service Dockerfiles**:
   - `Dockerfile.ingestion`: Container setup for `services/ingestion-api`.
   - `Dockerfile.processor`: Container setup for `services/memory-processor`.
   - `Dockerfile.retrieval`: Container setup for `services/retrieval-api`.
   - `Dockerfile.composer`: Container setup for `services/context-composer`.
   - `Dockerfile.mcp`: Container setup for `services/memory-mcp-server`.
   - `Dockerfile.deletion`: Container setup for `services/deletion-orchestrator`.
   - `Dockerfile.frontend`: Container setup for `apps/memory-controls` & `apps/memory-console`.

2. **Compose Configurations**:
   - `docker-compose.yml`: Spins up local infrastructure stack (Postgres, Neo4j, Redis, Kafka/Redpanda, Qdrant).

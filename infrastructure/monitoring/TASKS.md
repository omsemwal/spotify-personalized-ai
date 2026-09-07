# 📈 Monitoring & Observability Configurations

**Folder**: `infrastructure/monitoring/`  
**Purpose**: System telemetry monitoring, metrics scraping configs, and Grafana dashboard visualizers.

---

## 📋 What We Do Inside
1. **Prometheus (`/prometheus`)**:
   - `prometheus.yml` configuration scraping metrics endpoints (`/metrics`) across all FastAPI microservices.
2. **Grafana Dashboards (`/grafana`)**:
   - JSON dashboard definitions displaying:
     - Event Ingestion Rate & Latency
     - Kafka Queue Lag
     - Neo4j / Qdrant Query Latency
     - Deletion Job Backlog & Status
3. **OpenTelemetry (`/opentelemetry`)**:
   - Jaeger / OpenTelemetry Collector configurations for distributed request tracing.

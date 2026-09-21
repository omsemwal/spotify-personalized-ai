# infrastructure/monitoring

**What this is:** Prometheus scrape config and SLO alert rules for the
operations console (§5.4 "Operations Lead" requirement: "ingestion lag,
graph-write failures, retrieval latency, top policy rejections, deletion queue
status, and experiment cohort allocation").

## Files
- `prometheus.yml` — scrape targets for all 6 services' `/metrics` endpoints
  (instrument each FastAPI app with `prometheus-fastapi-instrumentator` or
  OpenTelemetry's Prometheus exporter — not wired by default in the pilot
  code, this file assumes that instrumentation is added before shipping).
- `alerts.yml` — 5 SLO-tied alerts:
  - `RetrievalLatencyP95Breach` — ties directly to §5.5's 250ms P95 budget.
  - `HighFallbackRate` — surfaces when memory is silently degrading to
    no-memory too often.
  - `DeletionBacklogGrowing`, `GraphWriteFailureSpike`, `PolicyRejectionSpike`
    — the exact metrics the Operations Lead and Site Reliability Lead named
    in the leadership transcript (§4).

## Wire into Grafana
Point a Grafana Prometheus data source at this Prometheus instance; import
dashboards keyed on the same metric names used in `alerts.yml`.

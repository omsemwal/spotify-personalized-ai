# tests/integration

Multi-component tests that cross service boundaries logically (not over HTTP)
using the in-memory adapters, so they run without docker-compose.

| File | Covers |
|---|---|
| `test_ingestion_to_graph.py` | An `InteractionEvent` → classification → graph write, end to end |

For full HTTP-level integration (real services talking over the network),
see `tests/end-to-end/`.

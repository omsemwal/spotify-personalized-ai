# tests/contract

Backward-compatibility tests for the shared contracts (§5.5 Maintainability).
These exist so a contract change is a **visible, deliberate** decision, not an
accidental break discovered by a downstream service in production.

| File | Covers |
|---|---|
| `test_schema_backward_compatibility.py` | Pins `SCHEMA_VERSION` and the required `InteractionEvent` fields |

When you intentionally change a contract: bump `SCHEMA_VERSION` in
`packages/contracts/events.py`, update this test's pinned value in the same
change, and update `services/ingestion-api/main.py`'s version check.

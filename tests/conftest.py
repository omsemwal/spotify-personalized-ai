"""Shared test setup.

Two jobs:

1. Put the repository root on `sys.path` once, so `packages.*` and
   `tests.doubles` import the same way from every test file.
2. Provide `requires_live_datastores`, the skip condition for tests that need
   `./scripts/dev.sh up` to have been run.

Note what is *not* here: there is no environment variable that switches the
services into a fake-backend mode. That was removed in U4. Tests that need a
store inject one explicitly with `set_graph_store()`.
"""

import socket
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _port_open(host: str, port: int, timeout: float = 0.4) -> bool:
    """True if something is listening. Deliberately cheap — this runs at
    collection time and must not slow the suite down when infra is absent."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# The ports `./scripts/dev.sh up` exposes on the host. Postgres is on 5433
# because a natively installed PostgreSQL commonly owns 5432.
LIVE_PORTS = {
    "neo4j": ("localhost", 7687),
    "postgres": ("localhost", 5433),
    "redis": ("localhost", 6379),
    "redpanda": ("localhost", 19092),
}


def live_datastores() -> dict[str, bool]:
    return {name: _port_open(host, port) for name, (host, port) in LIVE_PORTS.items()}


def requires_live_datastores(*names: str):
    """Skip marker for tests that need real infrastructure.

    Used rather than a fallback to in-memory doubles: a test that quietly
    changes what it is testing when infrastructure is missing is the same
    failure this unit removed from the services.
    """
    live = live_datastores()
    missing = [n for n in (names or LIVE_PORTS) if not live.get(n)]
    return pytest.mark.skipif(
        bool(missing),
        reason=f"needs {', '.join(missing)} — run `./scripts/dev.sh up`",
    )

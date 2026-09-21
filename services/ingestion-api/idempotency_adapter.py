"""
Idempotency-key store.

§5.4: "Attach ... an idempotency key to every event"; §4, Backend Engineering
Lead: "idempotency keys can prevent duplicate writes."

This used to fall back to an in-process dictionary when Redis was unreachable.
That is a particularly bad place for a silent fallback: ingestion runs as more
than one replica, and a per-process dictionary means each replica has its own
idea of what it has already seen. Duplicate detection appears to work in
testing, then quietly stops working the moment a second replica exists — and
duplicate memories are exactly what §5.4 says must not happen.

So: Redis or nothing.
"""

import os

TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))  # 24 hours
_KEY_PREFIX = "idempotency:"


def _timeout() -> float:
    """Socket timeout in seconds. Configurable so tests can fail fast."""
    return float(os.getenv("REDIS_CONNECT_TIMEOUT", "2"))


class IdempotencyStoreUnavailable(RuntimeError):
    """Redis could not be reached."""


class IdempotencyAdapter:
    """Redis-backed seen-key set. Constructing it connects, so an unreachable
    Redis stops the service at startup rather than at the first request."""

    def __init__(self, ttl_seconds: int = TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))

        try:
            import redis
        except ImportError as exc:
            raise IdempotencyStoreUnavailable(
                "the redis client is not installed. Run `./scripts/dev.sh install`."
            ) from exc

        try:
            self._redis = redis.Redis(
                host=host,
                port=port,
                db=int(os.getenv("REDIS_DB", "0")),
                decode_responses=True,
                # Bounded and retry-free. redis-py's own retry loop turns an
                # unreachable host into a ~25 second hang, which is far too slow for
                # a health check and hides an outage behind an apparent stall.
                socket_connect_timeout=_timeout(),
                socket_timeout=_timeout(),
                retry=None,
            )
            self._redis.ping()
        except Exception as exc:
            raise IdempotencyStoreUnavailable(
                f"cannot reach Redis at {host}:{port}: {exc}\n"
                "Start it with `./scripts/dev.sh up`. Ingestion will not start without it, "
                "because a per-process fallback would stop detecting duplicates as soon as "
                "a second replica exists."
            ) from exc

    def claim(self, key: str) -> bool:
        """Atomically claim a key. True if this caller got it, False if it was
        already taken.

        One round trip, using SET NX, rather than the previous check-then-set.
        Two concurrent requests carrying the same idempotency key could both
        pass a separate `seen()` check before either called `mark_seen()`, and
        both would be accepted — which is the exact duplicate this is meant to
        prevent.
        """
        try:
            return bool(self._redis.set(f"{_KEY_PREFIX}{key}", "1", nx=True, ex=self.ttl_seconds))
        except Exception as exc:
            raise IdempotencyStoreUnavailable(f"idempotency check failed for {key!r}: {exc}") from exc

    def seen(self, key: str) -> bool:
        """Read-only check. Prefer `claim()` on the write path — this cannot
        prevent a race on its own."""
        try:
            return bool(self._redis.exists(f"{_KEY_PREFIX}{key}"))
        except Exception as exc:
            raise IdempotencyStoreUnavailable(f"idempotency lookup failed for {key!r}: {exc}") from exc

    def status(self) -> dict:
        try:
            self._redis.ping()
        except Exception as exc:
            return {"backend": "redis", "reachable": False, "error": str(exc)}
        return {"backend": "redis", "reachable": True}

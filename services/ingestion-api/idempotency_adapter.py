"""
Idempotency-key store. Production path uses Redis with a 24h TTL. Local fallback
is an in-process dict so tests/local dev do not require a running Redis.
"""
import os
import time

LOCAL_MODE = os.getenv("LOCAL_MODE", "true").lower() == "true"
TTL_SECONDS = 86400

_LOCAL_STORE: dict[str, float] = {}


class IdempotencyAdapter:
    def __init__(self):
        self.local_mode = LOCAL_MODE
        self._redis = None
        if not self.local_mode:
            try:
                import redis
                self._redis = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    db=0, decode_responses=True,
                )
                self._redis.ping()
            except Exception:
                self.local_mode = True

    def seen(self, key: str) -> bool:
        if self.local_mode:
            self._evict_expired()
            return key in _LOCAL_STORE
        return bool(self._redis.exists(f"idempotency:{key}"))

    def mark_seen(self, key: str) -> None:
        if self.local_mode:
            _LOCAL_STORE[key] = time.time() + TTL_SECONDS
        else:
            self._redis.setex(f"idempotency:{key}", TTL_SECONDS, "1")

    @staticmethod
    def _evict_expired():
        now = time.time()
        for k in [k for k, exp in _LOCAL_STORE.items() if exp < now]:
            _LOCAL_STORE.pop(k, None)

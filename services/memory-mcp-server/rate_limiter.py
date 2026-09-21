"""Per-subject token-bucket rate limiter for MCP tool calls (§5.4 "Each tool
needs ... rate limits").

Backed by Redis (§6.2 Cache: "Short-lived subject-scoped caching, rate limiting,
and idempotency support") so the limit is shared across every instance of this
service. A per-process bucket would let N replicas serve N times the intended
rate. Falls back to an in-process bucket when Redis is unreachable, so a tool
call is never failed by the limiter itself.
"""
import os
import time
from collections import defaultdict

RATE_PER_SEC = 2.0
CAPACITY = 10.0
TTL_SECONDS = 3600

_BUCKETS = defaultdict(lambda: {"tokens": CAPACITY, "last": time.monotonic()})
_REDIS = None
_BACKEND = "memory"

# Refill and consume in one round trip. Doing this in Lua keeps it atomic, so
# two concurrent calls cannot both spend the same token.
_TOKEN_BUCKET_LUA = """
local key      = KEYS[1]
local rate     = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now      = tonumber(ARGV[3])
local ttl      = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(bucket[1])
local last   = tonumber(bucket[2])

if tokens == nil then
  tokens = capacity
  last = now
end

local elapsed = math.max(0, now - last)
tokens = math.min(capacity, tokens + elapsed * rate)

local allowed = 0
if tokens >= 1.0 then
  tokens = tokens - 1.0
  allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'last', now)
redis.call('EXPIRE', key, ttl)
return allowed
"""

_script = None


def _timeout() -> float:
    """Socket timeout in seconds. Configurable so tests can fail fast."""
    return float(os.getenv("REDIS_CONNECT_TIMEOUT", "2"))


class RateLimiterUnavailable(RuntimeError):
    """Redis could not be reached, so the rate limit cannot be enforced."""


def _redis():
    global _REDIS, _script
    if _REDIS is not None:
        return _REDIS
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    try:
        import redis
    except ImportError as exc:
        raise RateLimiterUnavailable(
            "the redis client is not installed. Run `./scripts/dev.sh install`."
        ) from exc
    try:
        client = redis.Redis(
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
        client.ping()
        _script = client.register_script(_TOKEN_BUCKET_LUA)
    except Exception as exc:
        raise RateLimiterUnavailable(
            f"cannot reach Redis at {host}:{port}: {exc}. "
            "MCP tools refuse to run without a shared rate limiter."
        ) from exc
    _REDIS = client
    return _REDIS


def status() -> dict:
    try:
        _redis().ping()
    except Exception as exc:
        return {"backend": "redis", "reachable": False, "error": str(exc).splitlines()[0]}
    return {"backend": "redis", "reachable": True}


def allow(subject_id: str, tool_name: str) -> bool:
    """One token from this subject's bucket for this tool. False means refuse.

    The per-process bucket that used to back this up has been removed. A local
    bucket does not limit anything once more than one replica is running — each
    replica hands out a full allowance — so it produced a rate limit that
    reported success while enforcing nothing. §5.4 requires rate limits on every
    tool, and §7.7 tests tool abuse, so this now fails closed: if the shared
    limiter is unreachable the call is refused rather than silently unlimited.
    """
    key = f"ratelimit:{subject_id}:{tool_name}"
    try:
        return bool(_script(keys=[key], args=[RATE_PER_SEC, CAPACITY, time.time(), TTL_SECONDS]))
    except RateLimiterUnavailable:
        raise
    except Exception as exc:
        raise RateLimiterUnavailable(f"rate-limit check failed for {tool_name!r}: {exc}") from exc

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


def _redis():
    global _REDIS, _BACKEND, _script
    if _REDIS is not None:
        return _REDIS
    if os.getenv("LOCAL_MODE", "true").lower() == "true":
        return None
    try:
        import redis
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=0, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
        client.ping()
        _script = client.register_script(_TOKEN_BUCKET_LUA)
        _REDIS, _BACKEND = client, "redis"
        return _REDIS
    except Exception:
        return None


def get_backend() -> str:
    _redis()
    return _BACKEND


def allow(subject_id: str, tool_name: str) -> bool:
    key = f"ratelimit:{subject_id}:{tool_name}"
    client = _redis()

    if client is not None:
        try:
            return bool(_script(keys=[key], args=[RATE_PER_SEC, CAPACITY, time.time(), TTL_SECONDS]))
        except Exception:
            pass  # fall through to the local bucket rather than refuse the call

    bucket = _BUCKETS[key]
    now = time.monotonic()
    bucket["tokens"] = min(CAPACITY, bucket["tokens"] + (now - bucket["last"]) * RATE_PER_SEC)
    bucket["last"] = now
    if bucket["tokens"] >= 1.0:
        bucket["tokens"] -= 1.0
        return True
    return False

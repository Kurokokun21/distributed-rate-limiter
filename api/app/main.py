import os
import time
from pathlib import Path

import redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="distributed-rate-limiter")

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)

WORKER_HEARTBEAT_KEY = "worker:heartbeat"
WORKER_STALE_AFTER_SECONDS = 15


# --- Phase 2: token bucket rate limiter (atomic Redis Lua script) ---

RATE_LIMIT_CAPACITY = 5        # max burst: bucket holds up to 5 tokens
RATE_LIMIT_REFILL_RATE = 1.0   # sustained rate: 1 token back per second

# Load the Lua script once at startup and register it with Redis.
# register_script() returns a callable we invoke per request; Redis caches
# the script by hash so it isn't re-sent every time.
_lua_path = Path(__file__).parent / "ratelimit.lua"
rate_limit_script = redis_client.register_script(_lua_path.read_text())

# Endpoints that should never be rate limited (health checks must always answer).
RATE_LIMIT_EXEMPT_PATHS = {"/health"}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in RATE_LIMIT_EXEMPT_PATHS:
        return await call_next(request)

    # Identify the client. For now, by IP address.
    client_id = request.client.host if request.client else "unknown"
    key = f"ratelimit:{client_id}"

    try:
        allowed, tokens_left = rate_limit_script(
            keys=[key],
            args=[RATE_LIMIT_CAPACITY, RATE_LIMIT_REFILL_RATE, time.time(), 1],
        )
    except redis.RedisError:
        # Fail open: if Redis is unreachable, don't wall off all traffic.
        return await call_next(request)

    if allowed == 0:
        return JSONResponse(
            status_code=429,
            content={"detail": "rate limit exceeded"},
            headers={
                "X-RateLimit-Remaining": str(int(tokens_left)),
                "Retry-After": "1",
            },
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(int(tokens_left))
    return response


@app.get("/health")
def health():
    status = {"api": "ok", "redis": "unknown", "worker": "unknown"}

    try:
        redis_client.ping()
        status["redis"] = "ok"
    except redis.RedisError:
        status["redis"] = "unreachable"

    heartbeat = redis_client.get(WORKER_HEARTBEAT_KEY) if status["redis"] == "ok" else None
    if heartbeat is None:
        status["worker"] = "unreachable"
    elif time.time() - float(heartbeat) <= WORKER_STALE_AFTER_SECONDS:
        status["worker"] = "ok"
    else:
        status["worker"] = "stale"

    status["all_ok"] = all(v == "ok" for k, v in status.items() if k != "all_ok")
    return status


# --- Phase 1: cache-aside layer over a pretend slow database ---

CACHE_TTL_SECONDS = 30
SLOW_DB_DELAY_SECONDS = 2

FAKE_DB = {
    "1": "espresso",
    "2": "matcha latte",
    "3": "cold brew",
}


class ItemUpdate(BaseModel):
    value: str


@app.get("/items/{item_id}")
def get_item(item_id: str):
    cache_key = f"item:{item_id}"

    cached_value = redis_client.get(cache_key)
    if cached_value is not None:
        return {"item_id": item_id, "value": cached_value, "source": "cache"}

    if item_id not in FAKE_DB:
        raise HTTPException(status_code=404, detail="item not found")

    time.sleep(SLOW_DB_DELAY_SECONDS)  # pretend this is a slow database call
    value = FAKE_DB[item_id]
    redis_client.set(cache_key, value, ex=CACHE_TTL_SECONDS)
    return {"item_id": item_id, "value": value, "source": "database (slow)"}


@app.put("/items/{item_id}")
def update_item(item_id: str, body: ItemUpdate):
    FAKE_DB[item_id] = body.value
    redis_client.delete(f"item:{item_id}")  # invalidate: don't serve the old cached value
    return {"item_id": item_id, "value": body.value, "cache": "invalidated"}

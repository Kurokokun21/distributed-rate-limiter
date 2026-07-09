import os
import time

import redis

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True,
)

HEARTBEAT_KEY = "worker:heartbeat"
HEARTBEAT_INTERVAL_SECONDS = 5

if __name__ == "__main__":
    while True:
        redis_client.set(HEARTBEAT_KEY, time.time())
        time.sleep(HEARTBEAT_INTERVAL_SECONDS)

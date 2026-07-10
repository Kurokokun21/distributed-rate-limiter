import json
import os
import time

import redis
from celery import Celery

# Build the Redis URL both broker and result-backend will use.
# e.g. "redis://redis:6379/0"  (host "redis" is the compose service name)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# The Celery application.
#   broker  = where jobs are queued  (API pushes here, worker pulls)
#   backend = where results are stored (worker writes, API reads by job id)
celery_app = Celery(
    "rate_limiter",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Run the heartbeat task every 5 seconds (Celery Beat = the scheduler / cron).
celery_app.conf.beat_schedule = {
    "worker-heartbeat": {
        "task": "tasks.heartbeat",
        "schedule": 5.0,
    }
}

# A plain redis client, only for writing the heartbeat the /health endpoint reads.
_redis = redis.Redis(host=REDIS_HOST, port=int(REDIS_PORT), decode_responses=True)


@celery_app.task(bind=True, name="tasks.slow_job")
def slow_job(self, n: int) -> dict:
    """Pretend to do heavy work for `n` seconds, then return a result."""
    time.sleep(n)
    result = {"squared": n * n, "slept_for": n}

    # Phase 4: announce completion on this job's Redis Pub/Sub channel.
    # self.request.id is this task's id == the job_id the API handed the client.
    _redis.publish(
        f"jobs:{self.request.id}",
        json.dumps({"job_id": self.request.id, "status": "SUCCESS", "result": result}),
    )
    return result


@celery_app.task(name="tasks.heartbeat")
def heartbeat() -> None:
    """Prove the worker is alive; /health checks this timestamp."""
    _redis.set("worker:heartbeat", time.time())

import random

from locust import HttpUser, between, task


class RealisticUser(HttpUser):
    """A typical client: mostly reads items, sometimes starts a job.

    This exercises every phase at once — the cache (repeated item reads),
    the rate limiter (bursts of traffic from one source), and background
    jobs (POST /jobs).
    """

    wait_time = between(0.5, 2.0)  # pause 0.5-2s between actions, like a real person

    @task(10)  # weight 10: happens ~10x as often as a weight-1 task
    def read_item(self):
        item_id = random.choice(["1", "2", "3"])
        # catch_response lets us judge the outcome ourselves and re-label the
        # stat line by status code, so allowed vs rate-limited show separately.
        with self.client.get(
            f"/items/{item_id}", name="/items [200 allowed]", catch_response=True
        ) as resp:
            if resp.status_code == 429:
                resp.request_meta["name"] = "/items [429 limited]"
                resp.success()  # expected under load — not a real failure
            elif resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"unexpected {resp.status_code}")

    @task(2)
    def start_job(self):
        with self.client.post(
            "/jobs", json={"seconds": 3}, name="/jobs [200 allowed]", catch_response=True
        ) as resp:
            if resp.status_code == 429:
                resp.request_meta["name"] = "/jobs [429 limited]"
                resp.success()
            elif resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"unexpected {resp.status_code}")

    @task(1)
    def health(self):
        self.client.get("/health")


class ThroughputUser(HttpUser):
    """Raw-speed hammer: hits /health (rate-limit exempt) with no think-time,
    to measure the maximum requests/second the API can push."""

    wait_time = between(0, 0)  # no pause — maximum pressure

    @task
    def health(self):
        self.client.get("/health")

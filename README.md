# Distributed Rate Limiter

A small distributed system built to answer one question: **how do services stay fast and standing when the requests pile up?** Each phase adds one defense — caching, rate limiting, background jobs, live push — and every one of them leans on the same piece of glue: **Redis**.

Built phase by phase as a learning project, then load-tested to prove it works.

## What it demonstrates

| Concern | Defense | Phase |
|---------|---------|-------|
| Too many reads of the same data | Cache-aside layer (Redis, 30s TTL) | 1 |
| One client flooding the API | Token-bucket rate limiter (atomic Redis Lua) | 2 |
| Slow work blocking the user | Background jobs (Celery + Redis broker) | 3 |
| "Is my job done yet?" polling | Live push over WebSocket (Redis Pub/Sub) | 4 |
| Does any of it actually hold up? | Load test (Locust) | 5 |

**Redis wears five hats:** cache shelf · rate-limit counters · job queue · result store · Pub/Sub channel.

## Architecture

```
                 ┌─────────────┐
   HTTP :8000 ──▶│     api     │  FastAPI — the only public door
                 │  (FastAPI)  │  rate-limit middleware, cache, job routes, WebSocket
                 └──────┬──────┘
                        │  Redis protocol
                 ┌──────▼──────┐
                 │    redis    │  in-memory store — the shared brain
                 └──────┬──────┘
                        │  queue + results + pub/sub
                 ┌──────▼──────┐
                 │   worker    │  Celery — runs slow jobs, heartbeats
                 │  (Celery)   │
                 └─────────────┘

   locust :8089 ──▶ api          load-test swarm (separate container)
```

## Quick start

```bash
docker compose up --build -d
```

Then:

- **API** — http://localhost:8000
- **Live-push demo page** — http://localhost:8000/ (start a job, watch the result get pushed)
- **Load-test dashboard** — http://localhost:8089 (Locust)

Health check:

```bash
curl http://localhost:8000/health
# {"api":"ok","redis":"ok","worker":"ok","all_ok":true}
```

(If `worker` shows `stale` on first boot, wait ~5s for the first heartbeat.)

## Endpoints

| Method | Path | What it does |
|--------|------|--------------|
| `GET`  | `/health` | Liveness of api, redis, worker (rate-limit exempt) |
| `GET`  | `/items/{id}` | Cached read over a fake slow "database" (Phase 1) |
| `PUT`  | `/items/{id}` | Update a value and invalidate its cache key |
| `POST` | `/jobs` | Enqueue a background job, returns a ticket id instantly (Phase 3) |
| `GET`  | `/jobs/{id}` | Poll a job's status/result |
| `WS`   | `/ws/jobs/{id}` | Live push — result arrives the instant the job finishes (Phase 4) |
| `GET`  | `/` | Browser demo page for the live push |

Every request except `/health` passes through the token-bucket rate limiter first (default: burst 5, refill 1 token/sec, per client IP). Over the limit → `429 Too Many Requests`.

## Load-test results

Measured with Locust, two user profiles:

**Realistic users (rate limiter ON, 50 concurrent)**
- Allowed traffic held to **~0.9 req/sec** — exactly the configured 1 token/sec refill rate
- **97%** of the flood shed as fast `429`s (protecting the cache and DB)
- Cache hits served at **~6ms median** (vs. a 2.3s cold read)
- One shared bucket per IP across all endpoints

**Throughput hammer (rate-limit-exempt `/health`, 100 concurrent)**
- **~900 req/sec** sustained
- Median **47ms**, p95 **74ms**
- **0 failures** across 23,169 requests

> The system can push ~900 req/sec, while the limiter throttles any single abuser to the configured trickle and leaves that headroom free for everyone else.

## Tech stack

- **Docker Compose** — orchestrates all four containers on one private network
- **FastAPI** + **Uvicorn** — the API server (with WebSocket support)
- **Redis** — cache, rate-limit state, Celery broker/backend, Pub/Sub
- **Lua** — the atomic token-bucket script run inside Redis
- **Celery** (+ Beat) — background jobs and the scheduled heartbeat
- **Locust** — load testing

## Project layout

```
api/
  app/main.py        endpoints + rate-limit middleware + WebSocket + demo page
  app/ratelimit.lua  atomic token-bucket script
worker/
  celery_app.py      Celery app, slow_job + heartbeat tasks
loadtest/
  locustfile.py      two simulated user classes
docker-compose.yml   the four services
```

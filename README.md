# Distributed Rate Limiter

Learning project, built phase by phase. Full roadmap: `roadmap.html`.

## Phase 0 — Skeleton & Plumbing

Three containers, one health check. `api` (FastAPI), `redis`, `worker` (heartbeats into Redis).

```
docker compose up --build
```

Then check:

```
curl http://localhost:8000/health
```

Expect:

```json
{"api": "ok", "redis": "ok", "worker": "ok", "all_ok": true}
```

If `worker` shows `stale` or `unreachable`, give it a few seconds — first heartbeat lands ~5s after boot.

## Phases

| # | Name | New tech |
|---|------|----------|
| 0 | Skeleton & Plumbing | Docker Compose |
| 1 | Cache Layer | Redis |
| 2 | The Rate Limiter | Token bucket / Lua |
| 3 | Background Jobs | Celery |
| 4 | Live Updates | WebSockets |
| 5 | Prove It | Locust |

# 08_recommendation_feedback

Full rebuild of this module — runs for real via Docker Compose: FastAPI +
PostgreSQL + Redis, no more in-memory mocks for storage.

## Structure

```
08_recommendation_feedback/
├── app/
│   ├── config.py        # env-driven settings (pydantic-settings)
│   ├── schema.py         # RecommendationResponse / FeedbackSubmission (the contract)
│   ├── mock_data.py       # 5 fixtures, one per action_code, now with waypoints for maps
│   ├── db.py              # async SQLAlchemy + asyncpg — real Postgres reads/writes
│   ├── feedback.py         # classification + safety-review escalation (DB-backed)
│   ├── live_update.py      # Redis-backed consent/dedup/cooldown for alerts
│   ├── monitoring.py       # structlog + Prometheus, safety vs UX metrics kept separate
│   └── main.py             # FastAPI app / routes
├── tests/
│   ├── test_recommendation.py    # unit tests — no DB/Redis needed
│   └── test_db_integration.py    # integration tests — needs `docker compose up`
├── db_schema.sql           # Postgres DDL, auto-run on first container start
├── Dockerfile
├── docker-compose.yml       # app + postgres + redis, with healthchecks
├── .env.example             # copy to .env before running
├── Makefile                 # make up / down / logs / rebuild / test
└── requirements.txt
```

## Run it

```bash
cp .env.example .env          # edit if you want different credentials
docker compose up -d --build  # or: make rebuild
docker compose ps             # all 3 services should show "healthy" / "running"
```

Try it:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/recommendation/mock/avoid_travel
curl http://localhost:8080/recommendation/mock-req-004      # re-fetch from Postgres

curl -X POST http://localhost:8080/feedback -H "Content-Type: application/json" -d '{
  "request_id": "mock-req-004",
  "pseudonymous_user_id": "anon-42",
  "category": "UNSAFE",
  "comment": "This was wrong",
  "submitted_at": "2026-09-19T12:00:00Z"
}'

curl http://localhost:8080/feedback/safety-queue

curl -X POST http://localhost:8080/feedback/mock-req-004/review -H "Content-Type: application/json" -d '{
  "reviewer": "ops-alice",
  "approve_for_training": true
}'
```

Run tests:

```bash
make test              # unit tests only, no DB needed
make test-integration  # against the real containers (run `make up` first)
```

Stop everything:

```bash
docker compose down          # keeps the pgdata volume (recommendation history survives)
docker compose down -v       # also wipes the volume — fresh DB next time
```

## What changed from the earlier version

- **Real persistence.** `feedback.py` and the new `db.py` now write to actual
  PostgreSQL tables (`recommendation_log`, `user_feedback`) instead of
  Python lists that vanished when the process restarted.
- **Real Redis.** `live_update.py` connects to the Redis container by
  default; `FakeRedis` is kept only for the unit tests that shouldn't
  need a running container.
- **Waypoints added to `RouteOption`** so the Web App can render a map —
  this was the gap identified against the architecture diagram earlier.
- **Package layout** (`app/` + `tests/`) instead of flat files, so it
  matches how the Dockerfile copies and runs it (`uvicorn app.main:app`).
- **`db.wait_for_db()`** retries on startup — Postgres can take a couple
  of seconds to accept connections right after `docker compose up`, so
  the app waits instead of crash-looping.

## Still mocked / still to connect

- `/recommendation/mock/{scenario}` still serves the 5 canned fixtures
  standing in for module 07's real decision output. Swap in a
  `/recommendation/live` endpoint once module 07 exists — the schema and
  the DB-write path (`db.save_recommendation`) don't need to change.
- Notification delivery (email/SMS/push) is not implemented —
  `NOTIFICATION_PROVIDER_KEYS` is read into config but unused until a
  provider is chosen (per 01_env.txt: "install a provider SDK only
  after a provider is selected").
- OpenTelemetry tracing is imported but not wired to a collector —
  `monitoring.py` only sets up structlog + Prometheus counters for now.

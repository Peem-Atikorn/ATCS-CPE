# 02 — API & Backend

FastAPI backend for the Real-Time Travel Safety & Advisory Assistant. It is the trust
boundary between the Web App and the Travel AI Agent.

Design documents:
[Requirements](docs/01_requirements.md) ·
[API Spec](docs/02_api_spec.md) ·
[Data Design](docs/03_data_design.md) ·
[Project Structure](docs/04_project_structure.md)

## Status

| Step | Scope | State |
|---|---|---|
| 5.1 | Skeleton: config, logging, errors, `/health`, Docker | done |
| 5.2 | DB models, Alembic 0001–0007, reference seed data | done |
| 5.3 | Auth (JWT/JWKS, scopes), rate limits, idempotency, body guard, security headers | done |
| 5.4 | Mock Agent (7 scenarios) and AgentClient: deadline, retry, circuit breaker, cancel, NDJSON | done |
| 5.5 | Domain: normalization, freshness (R-07), Safety Gate (R-01..R-05), sanitizer (R-06) | done |
| 5.6 | Recommendation flow: `POST/GET /v1/travel/recommendations`, Celery worker, job state and SSE in Redis, stream tickets, cache | done |
| 5.7 | Conversations and follow-up questions (`/v1/conversations`), recommendation history with cursor pagination | done |
| 5.8–5.12 | See [Project Structure §14](docs/04_project_structure.md#14-phase-5--ลำดับการ-implement-ที่เสนอ) | planned |

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Docker Desktop (for the compose stack)

## Quick start

```bash
uv sync
uv run pytest
```

Integration tests start a PostGIS container with Testcontainers, so Docker must be running.
Use `uv run pytest -m "not integration"` for a quick run without Docker.

Run the full stack (API, Celery worker, mock Agent, PostGIS, Redis core, Redis cache). The
`migrate` service applies migrations and seeds reference data before the API starts:

```bash
docker compose up -d --build --wait
curl http://localhost:8000/health
```

API docs: <http://localhost:8000/docs>

Run the API without Docker (needs a `.env`, see `.env.example`):

```bash
uv run python -m app.serve --reload
```

## Authentication in development

The dev stack signs tokens with `DEV_JWT_SIGNING_KEY` (HS256). Get a token and call the API:

```bash
docker compose exec api python -m scripts.dev_token --sub alice --scope travel:read
```

Outside dev/test the key is refused at startup and tokens are verified against the
issuer's JWKS (`JWKS_URL`, or discovery from `JWT_ISSUER`).

## Recommendation flow

`POST /v1/travel/recommendations` stores the request, queues a Celery job and waits up to
`SYNC_AGENT_TIMEOUT_SECONDS` (8 s) for the result. The worker is the only component that
calls the Agent; it applies the Safety Gate before anything is stored or shown.

| `mode` | Result |
|---|---|
| `auto` (default) | `200` with the recommendation, or `202` + job when it takes longer |
| `sync` | `200`, or `504 AGENT_TIMEOUT` when it takes longer (the job keeps running) |
| `async` | always `202` + job |

Follow a job with `GET /v1/jobs/{id}` or Server-Sent Events on `GET /v1/jobs/{id}/events`.
Browsers using `EventSource` cannot send the `Authorization` header: get a single-use ticket
from `POST /v1/jobs/{id}/stream-ticket` and open `.../events?ticket=...`.

```bash
TOKEN=$(docker compose exec -T api python -m scripts.dev_token --sub alice \
  --scope travel:read --scope travel:write)
curl -s -X POST "http://localhost:8000/v1/travel/recommendations?mode=async" \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: demo-$(date +%s)" \
  -H "content-type: application/json" \
  -d '{"origin":{"lat":13.7563,"lon":100.5018},"destination":{"lat":18.7883,"lon":98.9853},
       "departure_time":"2026-09-20T01:00:00Z","timezone":"Asia/Bangkok"}'
curl -N -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/jobs/<job_id>/events
```

## Conversations

A conversation keeps the context for follow-up questions. The first message carries the
trip in `overrides`; later messages only send what changes, and the backend re-assesses
the last trip with those changes:

```bash
CONV=$(curl -s -X POST http://localhost:8000/v1/conversations \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: conv-$(date +%s)" \
  -H "content-type: application/json" -d '{"language":"th"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['conversation_id'])")
# First message: the whole trip
curl -s -X POST http://localhost:8000/v1/conversations/$CONV/messages \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: msg1-$(date +%s)" \
  -H "content-type: application/json" \
  -d '{"content":"ปลอดภัยไหม","overrides":{"origin":{"lat":13.7563,"lon":100.5018},
       "destination":{"lat":18.7883,"lon":98.9853},
       "departure_time":"2026-09-20T01:00:00Z","timezone":"Asia/Bangkok"}}'
# Follow-up: only what changes
curl -s -X POST http://localhost:8000/v1/conversations/$CONV/messages \
  -H "Authorization: Bearer $TOKEN" -H "Idempotency-Key: msg2-$(date +%s)" \
  -H "content-type: application/json" \
  -d '{"content":"ถ้าออกช้ากว่าเดิม 3 ชั่วโมงล่ะ","overrides":{"departure_time":"2026-09-20T04:00:00Z"}}'
```

`GET /v1/conversations/{id}/messages` and `GET /v1/travel/recommendations` return pages
(`items`, `next_cursor`); pass `?cursor=` to get the next page.

## Mock Travel AI Agent

Until Module 03 is ready, the `mock-agent` service (port 8010) implements the Agent
contract with canned scenarios from `mock_agent/scenarios/`:

| Scenario | What it returns |
|---|---|
| `low_risk` | fresh data, `TRAVEL_NORMALLY` |
| `high_risk` | flood warning, `AVOID_TRAVEL`, emergency instructions |
| `partial_disaster_down` | disaster service unavailable but still `TRAVEL_NORMALLY` (the safety gate must catch it) |
| `needs_clarification` | asks for the travel date |
| `bad_schema` | a body that breaks the contract |
| `slow_20s` | answers after 20 s (beyond the sync budget) |
| `unavailable_503` | 503 with `Retry-After: 2` |

Switch scenario at runtime:

```bash
curl -X PUT -H "content-type: application/json" -d '{"name":"high_risk"}' http://localhost:8010/_mock/scenario
```

To use the real Agent, set `AGENT_SERVICE_URL` and its credentials
(`AGENT_TOKEN_URL` + `AGENT_CLIENT_ID` + `AGENT_CLIENT_SECRET`, or `AGENT_SERVICE_TOKEN`).
`tests/contract/` holds the contract tests both teams can run.

## Commands

`make` targets are listed below. On Windows without `make`, run the command on the right.

| make | Command |
|---|---|
| `make install` | `uv sync` |
| `make up` | `docker compose up -d --build --wait` |
| `make down` | `docker compose down` |
| `make logs` | `docker compose logs -f api worker` |
| `make migrate` | `docker compose run --rm migrate` |
| `make downgrade` | `docker compose run --rm migrate alembic downgrade -1` |
| `make revision m="..."` | `uv run alembic revision -m "..."` |
| `make token` | `docker compose exec api python -m scripts.dev_token` |
| `make scenario s=high_risk` | switch the mock agent scenario (curl above) |
| `make seed` | `docker compose run --rm migrate python -m scripts.seed_reference_data` |
| `make test` | `uv run pytest` |
| `make test-e2e` | stack running, then `E2E_BASE_URL=http://localhost:8000 E2E_MOCK_AGENT_URL=http://localhost:8010 uv run pytest -m e2e tests/e2e` |
| `make test-fast` | `uv run pytest -m "not integration"` |
| `make test-integration` | `uv run pytest tests/integration` |
| `make cov` | `uv run pytest --cov --cov-report=term-missing` |
| `make lint` | `uv run ruff format --check .` and `uv run ruff check .` |
| `make format` | `uv run ruff format .` and `uv run ruff check --fix .` |
| `make typecheck` | `uv run mypy app tests migrations scripts` |
| `make check` | lint + typecheck + test |

## Configuration

All settings are read from environment variables by `app/core/config.py`.
Required: `DATABASE_URL`, `REDIS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE`,
`AGENT_SERVICE_URL`, `CORS_ALLOWED_ORIGINS`. Tunable values (P-xx in the API spec)
have proposed defaults and can be overridden the same way.
The app refuses to start when a value is missing or invalid.

## Database migrations

- Every schema change goes through a new Alembic revision; never edit an applied one.
- Wrap CHECK constraint names in `op.f(...)`. Without it the naming convention adds the
  `ck_<table>_` prefix a second time.
- `tests/integration/test_migrations.py` fails when the models and migrations drift apart,
  including constraint and index names.

## Layout

```text
app/
  main.py              application factory
  serve.py             entrypoint: validates config, then starts uvicorn
  core/                config, logging, errors, ids, geo
  api/                 routers (/v1), deps, auth dependencies, idempotency, middleware, error handlers
  schemas/v1/          request and response contracts
  services/            use cases: recommendations, jobs, users, worker run, payload (assess)
  domain/              enums, normalization, freshness, safety gate, sanitizer, cache policy
  infrastructure/db/   SQLAlchemy models, session, reference data, repositories
  infrastructure/redis/ rate limiter, idempotency, job state, slots, tickets, cache, key names
  infrastructure/agent/ Agent contract, client, circuit breaker, service auth, factory
  workers/             Celery app, per-process runtime, tasks
mock_agent/            Mock Travel AI Agent (dev and contract tests)
migrations/            Alembic revisions 0001-0007
scripts/               seed_reference_data, dev_token
tests/
  unit/                pure tests, no I/O
  api/                 HTTP tests through httpx ASGITransport
  contract/            AgentClient against the mock agent (the Agent contract)
  integration/         PostGIS and Redis (Testcontainers), whole flow with the mock Agent
  e2e/                 against the running compose stack (skipped unless E2E_BASE_URL is set)
```

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
| 5.2–5.12 | See [Project Structure §14](docs/04_project_structure.md#14-phase-5--ลำดับการ-implement-ที่เสนอ) | planned |

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Docker Desktop (for the compose stack)

## Quick start

```bash
uv sync
uv run pytest
```

Run the full stack (API, PostGIS, Redis core, Redis cache):

```bash
docker compose up -d --build --wait
curl http://localhost:8000/health
```

API docs: <http://localhost:8000/docs>

Run the API without Docker (needs a `.env`, see `.env.example`):

```bash
uv run python -m app.serve --reload
```

## Commands

`make` targets are listed below. On Windows without `make`, run the command on the right.

| make | Command |
|---|---|
| `make install` | `uv sync` |
| `make up` | `docker compose up -d --build --wait` |
| `make down` | `docker compose down` |
| `make logs` | `docker compose logs -f api` |
| `make test` | `uv run pytest` |
| `make cov` | `uv run pytest --cov --cov-report=term-missing` |
| `make lint` | `uv run ruff format --check .` and `uv run ruff check .` |
| `make format` | `uv run ruff format .` and `uv run ruff check --fix .` |
| `make typecheck` | `uv run mypy app tests` |
| `make check` | lint + typecheck + test |

## Configuration

All settings are read from environment variables by `app/core/config.py`.
Required: `DATABASE_URL`, `REDIS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE`,
`AGENT_SERVICE_URL`, `CORS_ALLOWED_ORIGINS`. Tunable values (P-xx in the API spec)
have proposed defaults and can be overridden the same way.
The app refuses to start when a value is missing or invalid.

## Layout

```text
app/
  main.py              application factory
  core/                config, logging, errors, ids
  api/                 routers, middleware, error handlers
tests/
  unit/                pure tests, no I/O
  api/                 HTTP tests through httpx ASGITransport
```

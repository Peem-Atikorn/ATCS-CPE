UV ?= uv
COMPOSE ?= docker compose

.PHONY: install up down logs ps migrate downgrade revision seed token test test-unit test-api \
	test-integration test-fast cov lint format typecheck check

install:
	$(UV) sync

up:
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) run --rm migrate

downgrade:
	$(COMPOSE) run --rm migrate alembic downgrade -1

revision:
	$(UV) run alembic revision -m "$(m)"

token:
	$(COMPOSE) exec api python -m scripts.dev_token

seed:
	$(COMPOSE) run --rm migrate python -m scripts.seed_reference_data

test:
	$(UV) run pytest

test-unit:
	$(UV) run pytest tests/unit

test-api:
	$(UV) run pytest tests/api

test-integration:
	$(UV) run pytest tests/integration

test-fast:
	$(UV) run pytest -m "not integration"

cov:
	$(UV) run pytest --cov --cov-report=term-missing

lint:
	$(UV) run ruff format --check .
	$(UV) run ruff check .

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

typecheck:
	$(UV) run mypy app tests migrations scripts

check: lint typecheck test

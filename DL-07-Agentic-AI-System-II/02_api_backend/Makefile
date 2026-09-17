UV ?= uv
COMPOSE ?= docker compose

.PHONY: install up down logs ps test test-unit test-api cov lint format typecheck check

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

test:
	$(UV) run pytest

test-unit:
	$(UV) run pytest tests/unit

test-api:
	$(UV) run pytest tests/api

cov:
	$(UV) run pytest --cov --cov-report=term-missing

lint:
	$(UV) run ruff format --check .
	$(UV) run ruff check .

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

typecheck:
	$(UV) run mypy app tests

check: lint typecheck test

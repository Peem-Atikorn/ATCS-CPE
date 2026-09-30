COMPOSE = docker compose --env-file .env -f docker-compose.yml

.PHONY: up down logs smoke warmup config preflight monitor eval eval-live

up: preflight
	$(COMPOSE) up --build -d --wait

preflight:
	python3 deploy/preflight.py

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

smoke:
	$(COMPOSE) run --rm --no-deps checks python /tools/smoke.py

warmup:
	$(COMPOSE) run --rm --no-deps checks python /tools/warmup.py

config:
	$(COMPOSE) config --quiet

monitor:
	python3 deploy/monitor.py

eval:
	python3 eval/build_report.py

eval-live:
	python3 eval/run_live.py

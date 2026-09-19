# 08_recommendation_feedback

Full rebuild of this module — runs for real via Docker Compose: FastAPI +
PostgreSQL + Redis, no more in-memory mocks for storage.

## Structure

```
08_recommendation_feedback/
├── app/
│   ├── config.py        # env-driven settings (pydantic-settings)
│   ├── schema.py         # RecommendationResponse / FeedbackSubmission (the contract)
│   ├── mock_data.py       # 5 fixtures (4 action codes + an emergency scenario), with waypoints for maps
│   ├── emergency.py       # validates official_contacts (region / effective_date / phone) before serving
│   ├── db.py              # async SQLAlchemy + asyncpg — real Postgres reads/writes
│   ├── feedback.py         # classification + safety-review escalation (DB-backed)
│   ├── live_update.py      # Redis-backed consent/dedup/cooldown for alerts
│   ├── monitoring.py       # structlog + Prometheus, safety vs UX metrics kept separate
│   └── main.py             # FastAPI app / routes
├── tests/
│   ├── test_recommendation.py    # unit tests — no DB/Redis needed
│   ├── test_emergency_validation.py  # emergency-contact rules + endpoint wiring (db patched)
│   └── test_db_integration.py    # integration tests — needs `docker compose up`
├── db_schema.sql           # Postgres DDL, auto-run on first container start
├── migrations/             # one-off SQL for volumes created by an older schema
├── pytest.ini              # shared event loop for async DB tests
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

## Contract alignment (Contract Register v3)

Shared values now match 02 / 06 / 07:

- `risk_level` is `LOW | MEDIUM | HIGH` (no `MODERATE`, no `CRITICAL`).
- `action_code` is `TRAVEL_NORMALLY | CHANGE_ROUTE | DELAY_TRAVEL | AVOID_TRAVEL`.
  Emergency guidance is **not** a fifth action; it is carried by
  `emergency_instructions` / `official_contacts` on top of one of the four
  (the `emergency_instructions` mock scenario is `AVOID_TRAVEL` + `HIGH`).
- `emergency_instructions` / `official_contacts` accept `null` (03 sends
  `null` today) and treat it as empty.
- `db_schema.sql` now has CHECK constraints for both columns.

**Existing database?** `db_schema.sql` only runs on first start, so an old
`pgdata` volume still holds `MODERATE` / `CRITICAL` rows (and Redis may hold old
`live_update:last_risk:*` values — those are mapped automatically). Either
`docker compose down -v` (dev), or run
`docker compose exec -T postgres psql -U reco_user -d reco_db < migrations/001_three_risk_levels_four_actions.sql`.
Un-migrated rows make `GET /recommendation/{id}` return 500 on purpose rather
than serve data that no longer matches the schema.

## Emergency contact validation

Both `GET /recommendation/...` endpoints accept `?region=TH` (the traveler's
region) and run `emergency.validate_emergency_content` on every response:

- a contact whose `effective_date` is in the future, whose phone is malformed,
  or whose `region` differs from the traveler's is **withheld** (never edited);
- the response then gets a `limitations` note and a `DEGRADED`
  `emergency_contacts` entry in `degraded_services`;
- if the region is unknown the contact is kept but a limitation says it is
  unverified (`strict_region=True` in code withholds instead);
- if emergency instructions remain but no verified contact does, the response
  says so explicitly.

Contacts are stored as produced and re-validated each time they are served.

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

## Resolved decisions (tracked here for history)

- **Emergency instructions are 07's responsibility, not 08's.** ✅ Team
  decided: 07 generates the full `emergency_instructions` text and
  `official_contacts` list; 08 only receives, validates, and displays them.
  No schema change was needed — `RecommendationResponse` already modeled
  it this way. 08's job (per 01_env.txt: "Emergency text and contact
  numbers must match the user's location and have a valid effective date")
  is to validate what 07 sends before showing it — implemented in
  `app/emergency.py`; see "Emergency contact validation" above.

## Open questions with upstream (03 / 07) — tracked, not yet fully resolved

- **`confidence` is now nullable.** 03_travel_ai_agent's README confirms 07
  emits confidence as `LOW`/`MEDIUM`/`HIGH`, not a 0-1 number, and 03
  currently forwards `null` for the numeric field because of that mismatch
  with 02's expected float. `RecommendationResponse.confidence` is now
  `Optional[float]`, and a new `confidence_level: Optional[ConfidenceLevel]`
  carries the categorical value that's actually available today. See
  `mock_data.DELAY_TRAVEL` for a fixture that mirrors this real case
  (`confidence=None`, `confidence_level=MEDIUM`).
  **Still open:** if 07/02 later settle on a numeric scale, decide whether
  08 converts LOW/MEDIUM/HIGH → a number itself, or waits for 07 to send both.
- **`SourceCitation` is simpler than 05_data_integration's canonical
  records.** 05 tracks `observed_at`/`valid_at`/`issued_at`/`event_time`
  separately and a per-record `missing`/`stale`/`unavailable` status; our
  `SourceCitation` only has `published_at`. Not a problem yet since none of
  that richer data has reached 07→08 in practice — worth revisiting once
  06/07 pass real evidence through.

## Still mocked / still to connect

- `/recommendation/mock/{scenario}` still serves the 5 canned fixtures
  standing in for module 07's real decision output. Swap in a
  `/recommendation/live` endpoint once module 07 exists — the schema and
  the DB-write path (`db.save_recommendation`) don't need to change.
- **Emergency contact validation is partly done.** Region, effective date and
  phone format are enforced (see above). Still open, both need the team:
  1. `EMERGENCY_CONTACT_DIRECTORY_VERSION` is read into config but not enforced —
     contacts carry no directory version, so 07 would have to send one.
  2. Where the traveler's region comes from (today: the `region` query param,
     supplied by the caller). Ties into the coverage question (TH only vs abroad).
- Notification delivery (email/SMS/push) is not implemented —
  `NOTIFICATION_PROVIDER_KEYS` is read into config but unused until a
  provider is chosen (per 01_env.txt: "install a provider SDK only
  after a provider is selected").
- OpenTelemetry tracing is imported but not wired to a collector —
  `monitoring.py` only sets up structlog + Prometheus counters for now.

# Deploy & Monitoring (Peem)

Root `docker-compose.yml` connects the real services: Postgres, Redis, API, worker,
beat, retrieval, engines, generation, football data, router, and web. Only API
(`127.0.0.1:8000`) and web (`127.0.0.1:3000`) expose host ports. `checks` is a
one-off tools profile, so it is not expected to remain running.

## Runbook

1. Copy `.env.example` to `.env` and replace the four local passwords/secrets.
   `JWT_SECRET_KEY` needs at least 32 characters. Set provider keys needed for the
   desired demo. `FOOTBALL_DATA_API_KEY` is required for warmup. Use a Postgres
   password safe for a URL because Compose inserts it in `DATABASE_URL`.
2. Run `make preflight` then `make up`. On Windows PowerShell, run
   `./deploy/tasks.ps1 preflight` and `./deploy/tasks.ps1 up`.
3. Run `make monitor` for status of every long-running container, including
   `worker` and `beat`; `python3 deploy/monitor.py --watch 30` repeats. Run
   `make smoke` for HTTP readiness, authentication, admin permissions, and all
   five chat routes. A smoke pass checks connectivity and response shape, not
   factual correctness.
4. Run `make warmup` only against the intended demo database. It ingests
   fixtures/teams/standings/scorers, waits for indexing, generates the latest
   complete weekly report, publishes it, and checks public visibility. It
   needs a completed matchweek and working generation provider. The action is
   attributed to `admin`, not to the scheduled beat.
5. Run `make eval` to build `eval/report.html` from available measured results.
   For a live trivia check, start the stack, export `SEED_DEMO_PASSWORD` and
   run `make eval-live`, then `make eval` again. The live check uses exact answer
   substring matching, which is a limited measure of answer quality. The
   retrieval results currently use synthetic match fixtures and in-process
   timing; the report labels them accordingly.
6. Check `make logs` when a service fails; `make down` stops the stack without
   deleting persistent volumes.

The Web integration suite in `services/01_web_app/INTEGRATION.md` remains the
end-to-end gate for seeded data, chat, admin pipeline, and weekly reports.
Record the service commits, input data snapshot, and measured results when
running it. `make monitor` checks container health, while `make smoke` and the
Web suite check behavior.

## Current checkout and prerequisites

As of 2026-09-30, this checkout includes all seven service directories from
`origin/develop` (`688024a`). The local `.env` has generated passwords and
configured provider keys. On this Windows host Docker Desktop is installed in
the user's LocalAppData directory, even though `docker` is absent from PATH;
the PowerShell runner and Python checks locate its CLI there. Ubuntu WSL does
not have Docker Desktop integration enabled. Compose syntax alone does not
prove that images build or the stack runs: use `up`, `monitor`, and `smoke` on
the same checkout.

On 2026-09-30, the above checkout built and started successfully on Docker
Desktop 4.91.0. `monitor` found 11/11 containers running (all services with
health checks were healthy); `smoke` passed 15/15 checks. `warmup` ingested
fixtures, drained the index queue, and published the 2026 matchweek 5 report.
Live trivia eval routed 20/20 cases to `football_rag` and matched the expected
answer substring in 17/20. Two mismatches were a Thai translation or Unicode
space variant; one answer abstained despite the golden document being present.
This is a contract and operational pass, with one answer quality issue still
requiring review.

The optional Prometheus/Grafana stack in `docs/SCHEDULE.md` is not included.
The existing Admin dashboard (`/api/admin/stats`) supplies response metrics;
`monitor.py` supplies an operational snapshot of all Compose containers.

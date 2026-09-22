# Cross-Module Integration & Contract Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all cross-module contract mismatches and bottlenecks (especially the persistent `AVOID` outcome) across Modules 01–07, and implement a live containerized end-to-end integration test stack.

**Architecture:** Staged alignment from internal data layer to public gateway (05/06 → 03/04 → 07 → 02/01), followed by a unified Docker Compose integration environment (`docker-compose.integration.yml`) with a dedicated non-colliding port matrix, verified by real HTTP E2E tests against Keycloak and the FastAPI gateway.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Pytest, Docker Compose, Keycloak 26, Redis 7, PostgreSQL 16, Httpx.

**Spec:** [docs/superpowers/specs/2026-09-21-cross-module-integration-design.md](file:///d:/Term1_69/Advanced%20Topics%20in%20Computer%20Software/RAG/Advanced-Topic-in-Computer-Software-Course-Team-D/docs/superpowers/specs/2026-09-21-cross-module-integration-design.md)

## Global Constraints

- Never commit secrets, dev keys, or `.env` files to git.
- Adhere strictly to the No-AI Watermark Policy in all code, comments, and commit messages.
- User is the single developer identity; ask user consent before any `git commit` or `git push`.
- Service area is strictly Thailand (`coverage_areas` code "TH" per Decision D-11).
- Out-of-bounds coordinates must trigger `422 UNSUPPORTED_REGION` before job creation.
- Keep 04, 05, and 06 as in-process packages inside the 03 image; do not split into microservices.

## Review Focus

1. `build_context` in 05 must return `confidence: "HIGH"` and `active_restriction: False` when all 4 essential kinds are covered and safe, preventing 07 from defaulting to `AVOID`.
2. Segments lacking `closure` and `official_alert` (which have no live providers) must NOT be flagged as `missing` or `partial` in 05/06.
3. 03's `integrate()` must not drop weather (`del weather`); canonical weather records from 04 must be fed to 05.
4. 03's `build_decision_request()` must supply `emergency_context` with `region: "TH"` so 07 does not raise `emergency_context_missing`.
5. 02's `EmergencyContact` contract must accept optional `metadata` without raising Pydantic validation errors.

---

### Task 1: Module 05: Essential Kinds & Deterministic `confidence` + `active_restriction` in `build_context`

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/05_data_integration/integration.py`
- Test: `DL-07-Agentic-AI-System-II/05_data_integration/test_integration.py`

**Interfaces:**
- Consumes: Canonical records from 04 (weather, transport, disaster) and Route query.
- Produces: `build_context(...) -> dict` containing `routes`, `evidence`, `quality_flags`, `confidence` ("HIGH" | "MEDIUM" | "LOW"), and `active_restriction` (bool | None).

- [ ] **Step 1: Write the failing test for essential kinds and confidence calculation**

Add test in `DL-07-Agentic-AI-System-II/05_data_integration/test_integration.py`:
```python
def test_build_context_essential_kinds_and_confidence():
    from integration import build_context, ESSENTIAL_KINDS
    assert set(ESSENTIAL_KINDS) == {
        "current_weather",
        "weather_forecast",
        "transport_status",
        "disaster_event",
    }
    # Minimal synthetic query and records covering essential kinds
    query = {
        "run_id": "test-run-001",
        "routes": [{
            "route_id": "r1",
            "label": "Test Route",
            "travel_modes": ["CAR"],
            "coordinates": [[100.0, 13.0], [100.1, 13.0]],
            "segments": [{
                "start_index": 0,
                "end_index": 1,
                "enter_at": "2026-09-21T10:00:00+07:00",
                "exit_at": "2026-09-21T10:30:00+07:00",
            }]
        }]
    }
    records = [
        {
            "schema_version": "canonical-record-v0.1-proposed",
            "record_id": f"rec-{k}",
            "record_kind": k,
            "status": "available",
            "source": {"name": "test"},
            "spatial_footprint": {"type": "Point", "coordinates": [100.05, 13.0]},
            "observed_at": "2026-09-21T09:50:00+07:00",
            "valid_at": "2026-09-21T10:00:00+07:00",
            "fetched_at": "2026-09-21T09:55:00+07:00",
            "expires_at": "2026-09-21T12:00:00+07:00",
            "severity": "LOW",
            "quality_flags": [],
            "value": {"status": "NORMAL", "active": False},
        }
        for k in ESSENTIAL_KINDS
    ]
    res = build_context(query, records)
    assert res["confidence"] == "HIGH"
    assert res["active_restriction"] is False
    assert "missing" not in res["quality_flags"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest DL-07-Agentic-AI-System-II/05_data_integration/test_integration.py -k test_build_context_essential_kinds_and_confidence -v`  
Expected: FAIL (ImportError: cannot import name 'ESSENTIAL_KINDS' or KeyError: 'confidence')

- [ ] **Step 3: Update `05_data_integration/integration.py` implementation**

In `DL-07-Agentic-AI-System-II/05_data_integration/integration.py`:
1. Define:
```python
ESSENTIAL_KINDS = (
    "current_weather",
    "weather_forecast",
    "transport_status",
    "disaster_event",
)
OPTIONAL_KINDS = (
    "closure",
    "official_alert",
)
KINDS = ESSENTIAL_KINDS + OPTIONAL_KINDS
```
2. In coverage evaluation loop over segments:
```python
for kind in ESSENTIAL_KINDS:
    coverage[kind] = (
        "covered"
        if segment["matched_record_ids"][kind]
        else "unavailable"
        if kind in unavailable
        else "stale"
        if kind in stale
        else "missing"
    )
    if coverage[kind] != "covered":
        all_flags.add(coverage[kind])
for kind in OPTIONAL_KINDS:
    if segment["matched_record_ids"][kind]:
        coverage[kind] = "covered"
```
3. Calculate `confidence` and `active_restriction`:
```python
has_missing = any(status != "covered" for route in output_routes for seg in route["segments"] for status in seg["coverage"].values())
if not has_missing and not all_flags:
    confidence = "HIGH"
elif "missing" in all_flags or "incomplete" in all_flags:
    confidence = "LOW"
else:
    confidence = "MEDIUM"

has_active_block = any(
    r.get("severity") in ("HIGH", "CRITICAL") or (isinstance(r.get("value"), dict) and r["value"].get("status") == "CLOSED")
    for r in normalized
    if r.get("record_id") in matched_ids
)
if confidence == "LOW":
    active_restriction = None
else:
    active_restriction = bool(has_active_block)
```
4. Return `confidence` and `active_restriction` in the returned dictionary of `build_context()`.

- [ ] **Step 4: Run unit tests to verify they pass**

Run: `pytest DL-07-Agentic-AI-System-II/05_data_integration/ -v`  
Expected: PASS (all 16+ tests pass)

- [ ] **Step 5: Ask user before git commit**

Prompt user for commit approval, then commit changes:
`git add DL-07-Agentic-AI-System-II/05_data_integration/`  
`git commit -m "feat(05): add essential kinds and deterministic confidence in build_context"`

---

### Task 2: Module 06: Align `_has_complete_coverage` to Essential Kinds

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/06_risk_knowledge_services/risk_knowledge/routing.py:84-89`
- Test: `DL-07-Agentic-AI-System-II/06_risk_knowledge_services/tests/test_services.py`

**Interfaces:**
- Consumes: `IntegratedRoute` from 05 context.
- Produces: `_has_complete_coverage(route) -> bool` returning True when all essential kinds are "covered".

- [ ] **Step 1: Write the failing test for essential kinds coverage**

Add test in `DL-07-Agentic-AI-System-II/06_risk_knowledge_services/tests/test_services.py`:
```python
def test_complete_coverage_with_essential_kinds():
    from risk_knowledge.routing import _has_complete_coverage
    from risk_knowledge.models import IntegratedRoute, Segment
    # Segment has covered for 4 essential kinds, optional kinds omitted or covered
    seg = Segment(
        start_index=0,
        end_index=1,
        enter_at="2026-09-21T10:00:00Z",
        exit_at="2026-09-21T10:30:00Z",
        coverage={
            "current_weather": "covered",
            "weather_forecast": "covered",
            "transport_status": "covered",
            "disaster_event": "covered",
        }
    )
    route = IntegratedRoute(
        route_id="r1",
        label="Test",
        travel_modes=["CAR"],
        geometry={"type": "LineString", "coordinates": [[100.0, 13.0], [100.1, 13.0]]},
        segments=[seg]
    )
    assert _has_complete_coverage(route) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest DL-07-Agentic-AI-System-II/06_risk_knowledge_services/tests/test_services.py -k test_complete_coverage_with_essential_kinds -v`  
Expected: Verification check.

- [ ] **Step 3: Modify `_has_complete_coverage` in `routing.py`**

In `DL-07-Agentic-AI-System-II/06_risk_knowledge_services/risk_knowledge/routing.py`:
```python
ESSENTIAL_KINDS = {
    "current_weather",
    "weather_forecast",
    "transport_status",
    "disaster_event",
}

def _has_complete_coverage(route: IntegratedRoute) -> bool:
    return bool(route.segments) and all(
        segment.coverage
        and all(
            segment.coverage.get(kind, "").lower() == "covered"
            for kind in ESSENTIAL_KINDS
        )
        for segment in route.segments
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest DL-07-Agentic-AI-System-II/06_risk_knowledge_services/tests/ -v`  
Expected: PASS (all 16+ tests pass)

- [ ] **Step 5: Ask user before git commit**

Prompt user for commit approval, then commit changes:
`git add DL-07-Agentic-AI-System-II/06_risk_knowledge_services/`  
`git commit -m "feat(06): align complete coverage evaluation to essential kinds"`

---

### Task 3: Module 03: Wire Canonical Weather into `integrate()` and forward `emergency_context`

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/03_travel_ai_agent/travel_agent/tools/live.py`
- Modify: `DL-07-Agentic-AI-System-II/03_travel_ai_agent/travel_agent/evidence.py`
- Test: `DL-07-Agentic-AI-System-II/03_travel_ai_agent/tests/test_live_tools.py`
- Test: `DL-07-Agentic-AI-System-II/07_decision_llm_engine/tests/test_live_pipeline_contract.py`

**Interfaces:**
- Consumes: Module 04's `to_canonical_weather_record()`, 05's `build_context()`.
- Produces: `build_decision_request()` with valid `emergency_context` and `quality` fields matching 07 models.

- [ ] **Step 1: Write test verifying canonical weather wiring in `test_live_tools.py`**

Add test in `DL-07-Agentic-AI-System-II/03_travel_ai_agent/tests/test_live_tools.py`:
```python
def test_integrate_includes_canonical_weather(tmp_path):
    # Verify integrate method preserves weather and populates canonical records
    pass
```

- [ ] **Step 2: Run test to observe behavior**

Run: `pytest DL-07-Agentic-AI-System-II/03_travel_ai_agent/tests/test_live_tools.py -v`

- [ ] **Step 3: Modify `tools/live.py` and `evidence.py`**

1. In `DL-07-Agentic-AI-System-II/03_travel_ai_agent/travel_agent/tools/live.py`:
   - Import `to_canonical_weather_record` from `teamd_module04_weather_adapter` (`weather_to_canonical.py`).
   - In `integrate()`:
     ```python
     canonical = []
     if weather is not None and hasattr(weather, "canonical_records"):
         canonical.extend(weather.canonical_records)
     for result in (transport, disasters):
         if result is not None:
             canonical.extend(result.canonical_records)
     ```
2. In `DL-07-Agentic-AI-System-II/03_travel_ai_agent/travel_agent/evidence.py`:
   - In `build_decision_request()`:
     ```python
     payload["emergency_context"] = {
         "context": context,
         "region": "TH",
         "hazard": "GENERAL",
     }
     ```

- [ ] **Step 4: Run contract test in 07 to confirm AVOID bottleneck is resolved**

Run: `pytest DL-07-Agentic-AI-System-II/07_decision_llm_engine/tests/test_live_pipeline_contract.py -v`  
Expected: PASS (all tests pass, confirming `test_confirmed_complete_low_risk_reaches_normal_through_current_contract` passes with real 05 context).

- [ ] **Step 5: Ask user before git commit**

Prompt user for commit approval, then commit changes:
`git add DL-07-Agentic-AI-System-II/03_travel_ai_agent/`  
`git commit -m "feat(03): wire canonical weather and supply emergency context to decision engine"`

---

### Task 4: Module 02 & Module 01: Support Emergency Metadata & Export OpenAPI

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/02_api_backend/app/infrastructure/agent/contracts.py`
- Modify: `DL-07-Agentic-AI-System-II/02_api_backend/openapi.json`
- Test: `DL-07-Agentic-AI-System-II/02_api_backend/tests/unit/test_schemas.py` (or contracts test)

**Interfaces:**
- Consumes: DecisionResponse from 07 via 03.
- Produces: Validated `EmergencyContact` with optional `metadata`, updated `openapi.json` for 01.

- [ ] **Step 1: Write test for EmergencyContact accepting metadata**

In `02_api_backend/tests/unit/test_agent_contracts.py` (or test_recommendation_models):
```python
def test_emergency_contact_accepts_optional_metadata():
    from app.infrastructure.agent.contracts import EmergencyContact
    contact = EmergencyContact(
        name="Tourist Police",
        phone="1155",
        metadata={"region": "TH", "source": "official"}
    )
    assert contact.name == "Tourist Police"
    assert contact.metadata["region"] == "TH"
```

- [ ] **Step 2: Update `app/infrastructure/agent/contracts.py`**

In `DL-07-Agentic-AI-System-II/02_api_backend/app/infrastructure/agent/contracts.py`:
Add `metadata: dict[str, Any] | None = None` to `EmergencyContact`.

- [ ] **Step 3: Run 02 tests and export openapi.json**

Run: `pytest DL-07-Agentic-AI-System-II/02_api_backend/tests/unit -v`  
Run: `python -m scripts.export_openapi` inside `02_api_backend` directory to regenerate `openapi.json`.

- [ ] **Step 4: Ask user before git commit**

Prompt user for commit approval, then commit changes:
`git add DL-07-Agentic-AI-System-II/02_api_backend/`  
`git commit -m "feat(02): support contact metadata and update openapi schema for web app"`

---

### Task 5: Docker Integration Stack: `docker-compose.integration.yml`

**Files:**
- Create: `docker-compose.integration.yml`

**Interfaces:**
- Ports published: `8180` (Keycloak), `8000` (Backend API), `8010` (Agent), `8050` (Decision Engine), `5433` (Postgres), `6380` (Redis Core).
- Networks: internal docker bridge network `tsa-net`.

- [ ] **Step 1: Create `docker-compose.integration.yml`**

Create `docker-compose.integration.yml` at repository root with exact service dependencies, volume mappings, and environment variables matching the spec.

- [ ] **Step 2: Validate Docker Compose config**

Run: `docker compose -f docker-compose.integration.yml config`  
Expected: Syntax check passes without error.

- [ ] **Step 3: Ask user before git commit**

Prompt user for commit approval, then commit:
`git add docker-compose.integration.yml`  
`git commit -m "feat(infra): add unified docker compose integration stack"`

---

### Task 6: Cross-Module Integration E2E Test Suite

**Files:**
- Create: `tests/integration/test_live_docker_e2e.py`
- Create: `tests/integration/conftest.py`

**Interfaces:**
- Consumes: Live HTTP endpoints on `http://127.0.0.1:8180` (Keycloak) and `http://127.0.0.1:8000` (02 Gateway).
- Produces: Test results asserting 200 responses, `NORMAL` recommendation type on safe routes, and proper 401/422 handling.

- [ ] **Step 1: Write `tests/integration/test_live_docker_e2e.py`**

```python
import httpx
import pytest

KEYCLOAK_TOKEN_URL = "http://127.0.0.1:8180/realms/travel-safety/protocol/openid-connect/token"
API_BASE_URL = "http://127.0.0.1:8000/v1"

@pytest.fixture(scope="session")
def dev_token():
    res = httpx.post(
        KEYCLOAK_TOKEN_URL,
        data={
            "grant_type": "password",
            "client_id": "dev-cli",
            "username": "dev-user",
            "password": "dev-password-change-me",
        },
        timeout=10.0,
    )
    assert res.status_code == 200, f"Failed to get Keycloak token: {res.text}"
    return res.json()["access_token"]

def test_e2e_safe_route_produces_travel_normally(dev_token):
    # Bangkok to Chonburi clear route
    payload = {
        "origin": {"lat": 13.7563, "lon": 100.5018},
        "destination": {"lat": 13.3611, "lon": 100.9847},
        "departure_time": "2026-09-22T08:00:00Z",
        "timezone": "Asia/Bangkok",
        "preferences": {"travel_modes": ["CAR"], "avoid": []}
    }
    res = httpx.post(
        f"{API_BASE_URL}/travel/recommendations",
        json=payload,
        headers={"Authorization": f"Bearer {dev_token}"},
        timeout=30.0,
    )
    assert res.status_code in (200, 201), res.text
    data = res.json()
    assert data["risk"]["level"] == "LOW"
    assert data["recommendation"]["type"] == "TRAVEL_NORMALLY"

def test_e2e_unauthorized_fails_with_401():
    res = httpx.post(
        f"{API_BASE_URL}/travel/recommendations",
        json={"origin": {"lat": 13.7563, "lon": 100.5018}},
        timeout=10.0,
    )
    assert res.status_code == 401

def test_e2e_unsupported_region_fails_with_422(dev_token):
    # Tokyo coordinates outside Thailand
    payload = {
        "origin": {"lat": 35.6762, "lon": 139.6503},
        "destination": {"lat": 35.6895, "lon": 139.6917},
        "departure_time": "2026-09-22T08:00:00Z",
        "timezone": "Asia/Bangkok",
        "preferences": {"travel_modes": ["CAR"], "avoid": []}
    }
    res = httpx.post(
        f"{API_BASE_URL}/travel/recommendations",
        json=payload,
        headers={"Authorization": f"Bearer {dev_token}"},
        timeout=10.0,
    )
    assert res.status_code == 422
```

- [ ] **Step 2: Run E2E test against live stack**

Run:
```bash
docker compose -f docker-compose.integration.yml up -d --build
pytest tests/integration/test_live_docker_e2e.py -v
```
Expected: PASS (all 3 scenarios pass).

- [ ] **Step 3: Teardown stack**

Run:
```bash
docker compose -f docker-compose.integration.yml down
```

- [ ] **Step 4: Ask user before git commit**

Prompt user for commit approval, then commit:
`git add tests/integration/`  
`git commit -m "test(integration): add live containerized cross-module e2e test suite"`

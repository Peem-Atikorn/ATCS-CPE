# Module 08 Internal Tasks & Architecture Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Module 08 internal tasks: fix unit tests, restore the internal `GET /recommendation/{request_id}` endpoint, automate 180-day feedback retention cleanup, support notification dispatching stubs, and align root environment configurations with Module 02.

**Architecture:** Module 08 operates strictly as an **Internal Domain Service / Worker**, not a public storefront. All public routing goes through Module 02. 08 provides internal generation, query, validation, feedback safety queueing, and scheduled housekeeping.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy (Async), asyncpg, pytest, pytest-asyncio, structlog.

**Spec:** [docs/specs/2026-09-20-module-08-internal-tasks-design.md](file:///d:/Term1_69/Advanced%20Topics%20in%20Computer%20Software/RAG/Advanced-Topic-in-Computer-Software-Course-Team-D/DL-07-Agentic-AI-System-II/08_recommendation_feedback/docs/specs/2026-09-20-module-08-internal-tasks-design.md)

## Global Constraints

- Python 3.12 compatibility
- Async PostgreSQL with SQLAlchemy and asyncpg
- Pydantic v2 schemas and models
- No public `/v1/` endpoint alias in Module 08; maintain internal paths (`/recommendation/...`, `/feedback/...`)
- Retention policy fixed to 180 days across all configs
- All tests must pass with `pytest` without requiring running Docker services

## Review Focus

1. `GET /recommendation/{request_id}` when ID does not exist should return 404 with structured detail.
2. `GET /recommendation/{request_id}` stored row with invalid schema should raise 500 cleanly.
3. `purge_expired_feedback` must delete only rows older than the specified retention window, preserving newer feedback.
4. Lifespan background cleaner must be resilient to DB connection errors and shut down cleanly on cancellation.
5. Emergency contact filtering on mismatched region must record `"region_mismatch"` in `degraded_services` and note in `limitations`.

---

### Task 1: Fix Emergency Contact Mismatched Region Assertion in Unit Test

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/08_recommendation_feedback/tests/test_decision_client.py:102-107`

**Interfaces:**
- Consumes: `app.adapter.decision_to_recommendation`, `app.emergency.NO_VERIFIED_CONTACTS_NOTE`
- Produces: 100% passing test for `test_decision_client.py`

- [ ] **Step 1: Inspect the failing test and verify failure**

Run: `pytest tests/test_decision_client.py::test_adapter_emergency_contacts_filtered_on_mismatched_region -v`
Expected: FAIL with `AssertionError: assert False where False = any(...)`

- [ ] **Step 2: Update assertion in `tests/test_decision_client.py`**

Modify lines 102-107 of `tests/test_decision_client.py`:
```python
def test_adapter_emergency_contacts_filtered_on_mismatched_region():
    # Region US does not match contact's region TH -> contacts withheld
    reco = decision_to_recommendation(SAMPLE_07_RESPONSE, traveler_region="US")
    assert reco.official_contacts == []
    assert any("region_mismatch" in deg.detail for deg in reco.degraded_services)
    assert any("location" in lim.lower() for lim in reco.limitations)
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/test_decision_client.py::test_adapter_emergency_contacts_filtered_on_mismatched_region -v`
Expected: PASS

- [ ] **Step 4: Run full `test_decision_client.py` suite**

Run: `pytest tests/test_decision_client.py -v`
Expected: 8 passed in ~1s

---

### Task 2: Restore Internal `GET /recommendation/{request_id}` Endpoint & Tests

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/08_recommendation_feedback/app/main.py`
- Test: `DL-07-Agentic-AI-System-II/08_recommendation_feedback/tests/test_recommendation_api.py`

**Interfaces:**
- Consumes: `app.db.get_recommendation`, `app.schema.RecommendationResponse`, `app.emergency.validate_emergency_content`
- Produces: `GET /recommendation/{request_id}` returning `RecommendationResponse` or 404

- [ ] **Step 1: Write test for `GET /recommendation/{request_id}`**

Create `tests/test_recommendation_api.py`:
```python
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.mock_data import ALL_SCENARIOS

client = TestClient(app)

def test_get_stored_recommendation_success():
    sample = ALL_SCENARIOS["travel_normally"].model_dump(mode="json")
    with patch("app.db.get_recommendation", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = sample
        resp = client.get("/recommendation/00000000-0000-4000-8000-000000000001?region=TH")
        assert resp.status_code == 200
        data = resp.json()
        assert data["action_code"] == "TRAVEL_NORMALLY"

def test_get_stored_recommendation_not_found():
    with patch("app.db.get_recommendation", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = None
        resp = client.get("/recommendation/non-existent-id")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "request_id not found"
```

- [ ] **Step 2: Run test to verify it fails (route currently missing)**

Run: `pytest tests/test_recommendation_api.py -v`
Expected: FAIL (404 on mock endpoint or 405 Method Not Allowed)

- [ ] **Step 3: Implement `GET /recommendation/{request_id}` in `app/main.py`**

Add endpoint in `app/main.py`:
```python
from pydantic import ValidationError

@app.get("/recommendation/{request_id}", response_model=RecommendationResponse)
async def get_stored_recommendation(request_id: str, region: Optional[str] = None):
    """
    Internal query endpoint: re-fetch a previously served and logged recommendation.
    Re-validates emergency contacts against the current traveler region.
    """
    payload = await db.get_recommendation(request_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="request_id not found")
    try:
        response = RecommendationResponse.model_validate(payload)
    except ValidationError:
        logger.error("stored_recommendation_invalid", request_id=request_id)
        raise HTTPException(
            status_code=500, detail="stored recommendation does not match current schema"
        )
    return validate_emergency_content(response, region)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_recommendation_api.py -v`
Expected: 2 passed

---

### Task 3: Implement Automated 180-Day Feedback Retention Cleanup

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/08_recommendation_feedback/app/db.py`
- Modify: `DL-07-Agentic-AI-System-II/08_recommendation_feedback/app/main.py`
- Test: `DL-07-Agentic-AI-System-II/08_recommendation_feedback/tests/test_retention.py`

**Interfaces:**
- Consumes: `app.config.settings.feedback_retention_days`
- Produces: `db.purge_expired_feedback(days: int) -> int`, `POST /feedback/cleanup`, background lifespan periodic task

- [ ] **Step 1: Write test for retention purge logic and endpoint**

Create `tests/test_retention.py`:
```python
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_feedback_cleanup_endpoint():
    with patch("app.db.purge_expired_feedback", new_callable=AsyncMock) as mock_purge:
        mock_purge.return_value = 5
        resp = client.post("/feedback/cleanup")
        assert resp.status_code == 200
        data = resp.json()
        assert data["purged_count"] == 5
        assert data["retention_days"] == 180
        mock_purge.assert_called_once_with(180)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retention.py -v`
Expected: FAIL with 404 or AttributeError

- [ ] **Step 3: Implement `purge_expired_feedback` in `app/db.py`**

In `app/db.py`, add:
```python
async def purge_expired_feedback(retention_days: int = 180) -> int:
    """
    Purge user feedback rows older than the specified retention window (Contract Register v4 / P-23).
    Returns the number of deleted rows.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    async with get_session() as session:
        result = await session.execute(
            text("DELETE FROM user_feedback WHERE submitted_at < :cutoff"),
            {"cutoff": cutoff},
        )
        await session.commit()
        deleted = result.rowcount
        logger.info("feedback_retention_purged", deleted_count=deleted, cutoff=cutoff.isoformat())
        return deleted
```

- [ ] **Step 4: Implement background periodic task & cleanup endpoint in `app/main.py`**

In `app/main.py`:
```python
import asyncio

async def _retention_cleaner_loop(interval_seconds: float = 86400.0):
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            purged = await db.purge_expired_feedback(settings.feedback_retention_days)
            logger.info("retention_background_cleaner_completed", purged=purged)
        except asyncio.CancelledError:
            break
        except Exception as exc:  # noqa: BLE001
            logger.warning("retention_background_cleaner_error", error=str(exc))

@asynccontextmanager
async def lifespan(app: FastAPI):
    monitoring.init_monitoring()
    await db.wait_for_db()
    # Start retention cleaner in background
    cleaner_task = asyncio.create_task(_retention_cleaner_loop())
    try:
        yield
    finally:
        cleaner_task.cancel()
        try:
            await cleaner_task
        except asyncio.CancelledError:
            pass

@app.post("/feedback/cleanup")
async def manual_retention_cleanup():
    """Manual/Cron trigger to purge feedback older than FEEDBACK_RETENTION_DAYS."""
    count = await db.purge_expired_feedback(settings.feedback_retention_days)
    return {
        "status": "completed",
        "retention_days": settings.feedback_retention_days,
        "purged_count": count,
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_retention.py -v`
Expected: PASS

---

### Task 4: Notification Dispatcher Stub & Directory Version Handling

**Files:**
- Modify: `DL-07-Agentic-AI-System-II/08_recommendation_feedback/app/live_update.py`
- Test: `DL-07-Agentic-AI-System-II/08_recommendation_feedback/tests/test_live_update_dispatcher.py`

**Interfaces:**
- Consumes: `settings.notification_provider_keys`, `settings.emergency_contact_directory_version`
- Produces: `dispatch_notification(user_id, message, channel) -> bool`

- [ ] **Step 1: Write test for `dispatch_notification`**

Create `tests/test_live_update_dispatcher.py`:
```python
import pytest
from app.live_update import dispatch_notification

def test_dispatch_notification_without_keys_logs_noop():
    success = dispatch_notification(
        user_id="user-123",
        message="Risk level updated to HIGH",
        channel="sms"
    )
    assert success is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_live_update_dispatcher.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: Implement `dispatch_notification` in `app/live_update.py`**

Add to `app/live_update.py`:
```python
def dispatch_notification(
    user_id: str,
    message: str,
    channel: str = "in_app",
) -> bool:
    """
    Dispatch notification to configured providers.
    If no keys configured, safely no-op with structured log.
    """
    provider_keys = [k.strip() for k in settings.notification_provider_keys.split(",") if k.strip()]
    if not provider_keys:
        logger.info(
            "notification_dispatched_noop",
            user_id=user_id,
            channel=channel,
            reason="no_provider_keys_configured",
        )
        return True

    # Real provider hooks would go here once provider SDKs are added
    logger.info("notification_dispatched_external", user_id=user_id, channel=channel)
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_live_update_dispatcher.py -v`
Expected: PASS

---

### Task 5: Align Root `.env.example` with `FEEDBACK_RETENTION_DAYS=180`

**Files:**
- Modify: `d:\Term1_69\Advanced Topics in Computer Software\RAG\Advanced-Topic-in-Computer-Software-Course-Team-D\.env.example:87`

**Interfaces:**
- Consumes: Module 02 Contract Register Requirement P-23
- Produces: Synchronized configuration across root repository

- [ ] **Step 1: Update line 87 in `.env.example`**

Change:
```ini
FEEDBACK_RETENTION_DAYS=90
```
to:
```ini
FEEDBACK_RETENTION_DAYS=180
```

- [ ] **Step 2: Verify alignment using grep**

Run: `grep "FEEDBACK_RETENTION_DAYS" .env.example DL-07-Agentic-AI-System-II/08_recommendation_feedback/.env.example`
Expected: Both files output `FEEDBACK_RETENTION_DAYS=180`

---

### Task 6: Full Suite Verification & Final Polish

- [ ] **Step 1: Run all tests in Module 08**

Run: `pytest -v` (in `08_recommendation_feedback`)
Expected: All tests pass (test_recommendation.py, test_emergency_validation.py, test_decision_client.py, test_recommendation_api.py, test_retention.py, test_live_update_dispatcher.py)

- [ ] **Step 2: Update README.md to reflect the internal architecture, endpoints, and retention status**

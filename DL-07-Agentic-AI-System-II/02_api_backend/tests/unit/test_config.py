from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import AppEnv, Settings, get_settings


def test_loads_required_env_and_proposed_defaults() -> None:
    settings = Settings()

    assert settings.app.app_env is AppEnv.TEST
    assert settings.app.cors_allowed_origins == ["http://localhost:3000"]
    assert settings.auth.jwt_audience == "travel-safety-api"
    # A few proposed values from the Tunable Parameters table.
    assert settings.agent.sync_agent_timeout_seconds == 8.0  # P-02
    assert settings.limits.rate_limit_recommend == 10  # P-32
    assert settings.retention.retention_feedback_days == 180  # P-23
    assert settings.jobs.idempotency_ttl_seconds == 86400  # P-25


def test_tunable_value_can_be_overridden_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNC_AGENT_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("RETENTION_FEEDBACK_DAYS", "90")

    settings = Settings()

    assert settings.agent.sync_agent_timeout_seconds == 5.0
    assert settings.retention.retention_feedback_days == 90


def test_cors_origins_are_split_and_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", " http://a.test , https://b.test ,")

    assert Settings().app.cors_allowed_origins == ["http://a.test", "https://b.test"]


def test_wildcard_cors_origin_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    with pytest.raises(ValidationError, match="wildcard"):
        Settings()


@pytest.mark.parametrize(
    "missing",
    ["DATABASE_URL", "REDIS_URL", "JWT_ISSUER", "JWT_AUDIENCE", "AGENT_SERVICE_URL"],
)
def test_missing_required_env_fails_fast(monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
    monkeypatch.delenv(missing)

    with pytest.raises(ValidationError):
        Settings()


def test_invalid_number_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_USER", "0")

    with pytest.raises(ValidationError):
        Settings()


def test_log_level_is_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "debug")

    assert Settings().observability.log_level == "DEBUG"


def test_empty_otel_endpoint_disables_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

    assert Settings().observability.otel_exporter_otlp_endpoint is None


def test_dev_signing_key_is_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("DEV_JWT_SIGNING_KEY", "local-only")

    with pytest.raises(ValidationError, match="DEV_JWT_SIGNING_KEY"):
        Settings()


def test_secrets_are_not_exposed_in_repr() -> None:
    settings = Settings()

    assert "tsa:tsa" not in repr(settings)
    assert "tsa:tsa" in settings.db.database_url.get_secret_value()


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()

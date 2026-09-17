"""Application settings.

Every tunable value from docs/02_api_spec.md section 2 (P-xx) lives here with its
proposed default, so it can be changed through environment variables only.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ENV_CONFIG = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


class AppEnv(StrEnum):
    DEV = "dev"
    TEST = "test"
    STAGING = "staging"
    PROD = "prod"


class AppSettings(BaseSettings):
    model_config = _ENV_CONFIG

    app_env: AppEnv = AppEnv.DEV
    api_version: str = "1.0.0"
    enable_docs: bool = True
    cors_allowed_origins: Annotated[list[str], NoDecode]
    max_body_bytes: int = Field(default=64 * 1024, gt=0)  # P-44
    error_type_base_url: str = "https://errors.travel-safety.example/"

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def _no_wildcard(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("wildcard origin is not allowed; list origins explicitly")
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env in {AppEnv.STAGING, AppEnv.PROD}


class DatabaseSettings(BaseSettings):
    model_config = _ENV_CONFIG

    database_url: SecretStr
    db_pool_size: int = Field(default=10, gt=0)
    db_max_overflow: int = Field(default=10, ge=0)


class RedisSettings(BaseSettings):
    model_config = _ENV_CONFIG

    redis_url: SecretStr
    redis_cache_url: SecretStr | None = None  # empty -> REDIS_URL database /1 (D-14)
    celery_broker_url: SecretStr | None = None  # empty -> REDIS_URL database /2


class AuthSettings(BaseSettings):
    model_config = _ENV_CONFIG

    jwt_issuer: str = Field(min_length=1)
    jwt_audience: str = Field(min_length=1)
    jwks_url: str | None = None
    jwks_cache_seconds: int = Field(default=600, gt=0)  # P-11
    dev_jwt_signing_key: SecretStr | None = None


class AgentSettings(BaseSettings):
    model_config = _ENV_CONFIG

    agent_service_url: str = Field(min_length=1)
    agent_client_id: str | None = None
    agent_client_secret: SecretStr | None = None
    agent_connect_timeout_seconds: float = Field(default=2.0, gt=0)  # P-06
    sync_agent_timeout_seconds: float = Field(default=8.0, gt=0)  # P-02
    job_agent_timeout_seconds: float = Field(default=60.0, gt=0)  # P-04
    agent_max_retries: int = Field(default=2, ge=0)  # P-07
    agent_cb_failure_threshold: int = Field(default=5, gt=0)  # P-08
    agent_cb_window_seconds: int = Field(default=30, gt=0)  # P-08
    agent_cb_reset_seconds: int = Field(default=30, gt=0)  # P-08
    agent_context_messages: int = Field(default=10, ge=0)  # P-45


class LimitSettings(BaseSettings):
    model_config = _ENV_CONFIG

    rate_limit_user: int = Field(default=60, gt=0)  # P-30, per minute
    rate_limit_ip: int = Field(default=120, gt=0)  # P-31, per minute
    rate_limit_recommend: int = Field(default=10, gt=0)  # P-32, per minute
    max_active_jobs_per_user: int = Field(default=3, gt=0)  # P-33
    max_streams_per_user: int = Field(default=3, gt=0)  # P-34
    sse_heartbeat_seconds: int = Field(default=15, gt=0)  # P-35
    max_page_size: int = Field(default=50, gt=0)  # P-40
    max_question_chars: int = Field(default=1000, gt=0)  # P-41
    max_waypoints: int = Field(default=5, ge=0)  # P-42
    max_days_ahead: int = Field(default=14, gt=0)  # P-43


class JobSettings(BaseSettings):
    model_config = _ENV_CONFIG

    job_result_ttl_seconds: int = Field(default=24 * 3600, gt=0)  # P-05
    idempotency_ttl_seconds: int = Field(default=24 * 3600, gt=0)  # P-25


class CacheSettings(BaseSettings):
    model_config = _ENV_CONFIG

    recommendation_cache_seconds: int = Field(default=300, ge=0)  # P-26
    cache_time_bucket_minutes: int = Field(default=15, gt=0)  # P-27
    stale_weather_minutes: int = Field(default=60, gt=0)  # P-28
    stale_disaster_minutes: int = Field(default=15, gt=0)  # P-28
    stale_transport_minutes: int = Field(default=10, gt=0)  # P-28


class RetentionSettings(BaseSettings):
    model_config = _ENV_CONFIG

    retention_recommendation_days: int = Field(default=30, gt=0)  # P-21
    retention_conversation_days: int = Field(default=30, gt=0)  # P-22
    retention_feedback_days: int = Field(default=180, gt=0)  # P-23
    retention_audit_days: int = Field(default=365, gt=0)  # P-24
    retention_prediction_days: int = Field(default=365, gt=0)  # P-46
    retention_trip_days_after_departure: int = Field(default=30, gt=0)  # P-47
    data_export_ttl_days: int = Field(default=7, gt=0)  # P-49
    purge_cron: str = "0 3 * * *"  # P-50
    purge_timezone: str = "Asia/Bangkok"  # P-50


class PrivacySettings(BaseSettings):
    model_config = _ENV_CONFIG

    log_geohash_precision: int = Field(default=5, ge=1, le=12)  # P-20
    prediction_geohash_precision: int = Field(default=5, ge=1, le=12)  # P-48


class ObservabilitySettings(BaseSettings):
    model_config = _ENV_CONFIG

    log_level: str = "INFO"
    log_json: bool = True
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "travel-safety-api"

    @field_validator("log_level")
    @classmethod
    def _valid_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"unsupported log level: {value}")
        return level

    @field_validator("otel_exporter_otlp_endpoint", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        return value or None


class Settings(BaseModel):
    app: AppSettings = Field(default_factory=AppSettings)
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    limits: LimitSettings = Field(default_factory=LimitSettings)
    jobs: JobSettings = Field(default_factory=JobSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.app.is_production and self.auth.dev_jwt_signing_key is not None:
            raise ValueError("DEV_JWT_SIGNING_KEY must not be set outside dev/test")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

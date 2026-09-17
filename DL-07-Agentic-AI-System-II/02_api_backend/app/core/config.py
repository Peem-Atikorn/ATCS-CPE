"""Application settings.

Every tunable value from docs/02_api_spec.md section 2 (P-xx) lives here with its
proposed default, so it can be changed through environment variables only.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated
from urllib.parse import urlsplit, urlunsplit

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
    # Proxies whose X-Forwarded-For is trusted for the client IP (rate limits use it).
    forwarded_allow_ips: str = "127.0.0.1"

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
    redis_socket_timeout_seconds: float = Field(default=2.0, gt=0)

    @field_validator("redis_cache_url", "celery_broker_url", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        return value or None

    def core_url(self) -> str:
        return self.redis_url.get_secret_value()

    def cache_url(self) -> str:
        if self.redis_cache_url is not None:
            return self.redis_cache_url.get_secret_value()
        return _with_redis_db(self.core_url(), 1)

    def broker_url(self) -> str:
        if self.celery_broker_url is not None:
            return self.celery_broker_url.get_secret_value()
        return _with_redis_db(self.core_url(), 2)


def _with_redis_db(url: str, db: int) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{db}"))


class AuthSettings(BaseSettings):
    model_config = _ENV_CONFIG

    jwt_issuer: str = Field(min_length=1)
    jwt_audience: str = Field(min_length=1)
    jwks_url: str | None = None
    jwks_cache_seconds: int = Field(default=600, gt=0)  # P-11
    jwks_min_refresh_seconds: int = Field(default=60, gt=0)
    jwt_algorithms: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["RS256", "ES256"]
    )
    jwt_leeway_seconds: int = Field(default=30, ge=0)
    dev_jwt_signing_key: SecretStr | None = None

    @field_validator("jwks_url", "dev_jwt_signing_key", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        return value or None

    @field_validator("jwt_algorithms", mode="before")
    @classmethod
    def _split_algorithms(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("jwt_algorithms")
    @classmethod
    def _asymmetric_only(cls, value: list[str]) -> list[str]:
        # Shared-secret algorithms are only allowed through DEV_JWT_SIGNING_KEY.
        allowed = {"RS256", "RS384", "RS512", "PS256", "ES256", "ES384", "EdDSA"}
        unsupported = [alg for alg in value if alg not in allowed]
        if unsupported or not value:
            raise ValueError(f"unsupported JWT algorithms: {unsupported or value}")
        return value

    @field_validator("dev_jwt_signing_key")
    @classmethod
    def _dev_key_length(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < 32:
            raise ValueError("DEV_JWT_SIGNING_KEY must be at least 32 characters")
        return value


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
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    # Rate limiting protects capacity; an unavailable Redis should not take the API down.
    rate_limit_fail_open: bool = True


class JobSettings(BaseSettings):
    model_config = _ENV_CONFIG

    job_result_ttl_seconds: int = Field(default=24 * 3600, gt=0)  # P-05
    idempotency_ttl_seconds: int = Field(default=24 * 3600, gt=0)  # P-25
    # A key stays locked this long if a worker dies before storing the response.
    idempotency_lock_seconds: int = Field(default=120, gt=0)


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


class SecretSettings(BaseSettings):
    model_config = _ENV_CONFIG

    pseudonym_secret: SecretStr | None = None
    ip_hash_secret: SecretStr | None = None

    @field_validator("pseudonym_secret", "ip_hash_secret", mode="before")
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
    secrets: SecretSettings = Field(default_factory=SecretSettings)

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.app.is_production and self.auth.dev_jwt_signing_key is not None:
            raise ValueError("DEV_JWT_SIGNING_KEY must not be set outside dev/test")
        if self.app.is_production:
            missing = [
                name.upper()
                for name in ("pseudonym_secret", "ip_hash_secret")
                if getattr(self.secrets, name) is None
            ]
            if missing:
                raise ValueError(f"required outside dev/test: {', '.join(missing)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

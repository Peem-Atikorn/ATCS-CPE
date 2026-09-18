from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    decision_policy_version: str = "prototype-v1"
    prompt_version: str = "v1"
    policy_approved: bool = False
    llm_api_key: SecretStr = SecretStr("")
    llm_model_explainer: str = "disabled"
    temperature: float = Field(default=0, ge=0, le=0)
    max_input_tokens: int = Field(default=8000, ge=256, le=32000)
    max_output_tokens: int = Field(default=1500, ge=64, le=8000)
    llm_timeout: float = Field(default=5, gt=0, le=60)
    llm_max_attempts: int = Field(default=2, ge=1, le=3)
    supported_locales: str = "th-TH,en-US"
    escalation_rules: str = "missing,stale,conflicting,incomplete,low_confidence,unverified_warning"
    audit_log_path: Path = Path("data/audit.jsonl")

    @field_validator("decision_policy_version")
    @classmethod
    def bundled_policy_only(cls, value: str) -> str:
        if value != "prototype-v1":
            raise ValueError("Only the bundled prototype-v1 policy is implemented")
        return value

    @field_validator("prompt_version")
    @classmethod
    def bundled_prompt_only(cls, value: str) -> str:
        if value != "v1":
            raise ValueError("Only prompt v1 is implemented")
        return value

    @field_validator("policy_approved")
    @classmethod
    def no_self_approval(cls, value: bool) -> bool:
        if value:
            raise ValueError("Bundled policy is provisional; an environment flag cannot approve it")
        return value

    @field_validator("supported_locales")
    @classmethod
    def supported_languages(cls, value: str) -> str:
        locales = {part.strip() for part in value.split(",")}
        if not locales or not locales <= {"th-TH", "en-US"}:
            raise ValueError("Supported locales are th-TH and en-US")
        return value

    @field_validator("escalation_rules")
    @classmethod
    def mandatory_escalations(cls, value: str) -> str:
        required = {
            "missing",
            "stale",
            "conflicting",
            "incomplete",
            "low_confidence",
            "unverified_warning",
        }
        if {v.strip() for v in value.split(",")} != required:
            raise ValueError("Changing escalation rules requires a new reviewed policy")
        return value

    @property
    def locales(self) -> set[str]:
        return {part.strip() for part in self.supported_locales.split(",")}

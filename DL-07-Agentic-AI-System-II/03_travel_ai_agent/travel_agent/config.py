from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    agent_version: str = "0.1.0"
    # No LLM planner yet: intent and planning are rule-based in this version.
    prompt_version: str = "rules-v1"

    # Bearer token Module 02 must send (its AGENT_SERVICE_TOKEN). Empty disables the check,
    # which is only acceptable for local development.
    agent_service_token: SecretStr = SecretStr("")

    decision_service_url: HttpUrl = HttpUrl("http://localhost:8050")
    # Modules 04/05/06 have no services yet; true keeps the pipeline on MockToolSet.
    use_mock_tools: bool = True

    # Hard limits on one run (03_process.txt: the agent must not run forever).
    max_agent_steps: int = Field(default=12, ge=1, le=50)
    max_tool_calls: int = Field(default=20, ge=1, le=100)
    agent_total_timeout: float = Field(default=30, gt=0, le=300)
    tool_timeout_seconds: float = Field(default=5, gt=0, le=60)
    decision_max_attempts: int = Field(default=2, ge=1, le=5)

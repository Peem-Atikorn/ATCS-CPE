"""What the agent expects back from Modules 04, 05 and 06.

These are DRAFT contracts proposed by Module 03 so the pipeline can run on mocks. They
must be agreed with the owners of 04/05/06 before the real adapters replace the mocks.
Tool output is untrusted: it is validated here, and free text (`excerpt`, `summary`)
is only ever passed along as data, never used as instructions.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from travel_agent.contracts import RiskLevel

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")]
RecordKind = Literal["weather", "transport", "risk", "knowledge", "route", "official", "time"]


class ToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Record(ToolModel):
    """One piece of evidence with provenance, as Module 04 step 9 requires."""

    # Assigned by the agent when the tool returns, so IDs are unique within a run.
    id: Identifier | None = None
    kind: RecordKind
    source_name: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    official_source: bool = False
    observed_at: AwareDatetime
    fetched_at: AwareDatetime
    expires_at: AwareDatetime
    excerpt: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def provenance_is_usable(self):
        # Module 07 rejects the whole package if one record breaks these rules,
        # so a bad record fails its own tool instead.
        if self.url.scheme != "https" or self.url.username or self.url.password:
            raise ValueError("Record URL must be HTTPS without credentials")
        if not self.observed_at <= self.fetched_at < self.expires_at:
            raise ValueError("Require observed_at <= fetched_at < expires_at")
        return self


class TravelQuery(ToolModel):
    """The only input tools receive: no user identity and no free-text question."""

    run_id: str
    origin: tuple[float, float]
    destination: tuple[float, float]
    departure_time: AwareDatetime
    travel_modes: list[str] = Field(default_factory=list)
    # Selects a canned scenario in the mock tools; ignored by real services.
    mock_scenario: str | None = None


# ------------------------------------------------------------------ Module 04


class WeatherResult(ToolModel):
    summary: str = Field(min_length=1, max_length=2000)
    records: list[Record] = Field(min_length=1)


class TransportResult(ToolModel):
    summary: str = Field(min_length=1, max_length=2000)
    records: list[Record] = Field(min_length=1)


class Alert(ToolModel):
    hazard_id: Identifier
    hazard_type: str
    severity: RiskLevel
    title: str = Field(max_length=300)
    # Same scale as Module 07's OfficialAlert.level.
    level: Literal["CAUTION", "AVOID", "CLOSURE"]
    active: bool
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    record: Record


class DisasterResult(ToolModel):
    alerts: list[Alert] = Field(default_factory=list, max_length=20)
    # Proof that the check ran even when there are no alerts.
    records: list[Record] = Field(min_length=1)


# ------------------------------------------------------------------ Module 05


class IntegratedContext(ToolModel):
    data_version: Identifier
    primary_route_id: Identifier
    confidence: RiskLevel
    flags: list[Literal["missing", "stale", "conflicting", "incomplete", "inferred"]] = Field(
        default_factory=list
    )
    # None means unknown, never "no restriction".
    active_restriction: bool | None


# ------------------------------------------------------------------ Module 06


class RiskFactorResult(ToolModel):
    type: str
    level: RiskLevel
    description: str = Field(max_length=500)


class RiskResult(ToolModel):
    level: RiskLevel
    # Model output probability, if the model is calibrated; shown to the backend as score.
    score: float | None = Field(default=None, ge=0, le=1)
    confidence: RiskLevel
    model_version: Identifier
    factors: list[RiskFactorResult] = Field(default_factory=list)
    records: list[Record] = Field(min_length=1)


class KnowledgeResult(ToolModel):
    records: list[Record] = Field(default_factory=list)


class RouteInfo(ToolModel):
    route_id: Identifier
    label: str | None = None
    travel_modes: list[str] = Field(default_factory=list)
    distance_km: float | None = Field(default=None, ge=0)
    duration_minutes: float | None = Field(default=None, ge=0)
    risk_level: RiskLevel
    usable: bool = True
    clearly_safer: bool = False


class RouteResult(ToolModel):
    primary: RouteInfo
    alternatives: list[RouteInfo] = Field(default_factory=list, max_length=10)
    no_safe_route: bool = False
    safer_later: bool = False
    suggested_departure_time: AwareDatetime | None = None
    records: list[Record] = Field(min_length=1)

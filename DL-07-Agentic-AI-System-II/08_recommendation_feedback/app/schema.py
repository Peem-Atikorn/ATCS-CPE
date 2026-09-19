"""
Response schema — the contract this module exposes to 07_decision_llm_engine
(producer) and 01_web_app (consumer).

RECOMMENDATION_SCHEMA_VERSION must be bumped on any breaking field change.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.config import settings

RECOMMENDATION_SCHEMA_VERSION = settings.recommendation_schema_version


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ActionCode(str, Enum):
    TRAVEL_NORMALLY = "TRAVEL_NORMALLY"
    CHANGE_ROUTE = "CHANGE_ROUTE"
    DELAY_TRAVEL = "DELAY_TRAVEL"
    AVOID_TRAVEL = "AVOID_TRAVEL"
    EMERGENCY_INSTRUCTIONS = "EMERGENCY_INSTRUCTIONS"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SourceType(str, Enum):
    OFFICIAL = "OFFICIAL"
    WEATHER = "WEATHER"
    TRANSPORT = "TRANSPORT"
    DISASTER_RAG = "DISASTER_RAG"
    ROUTE_MODEL = "ROUTE_MODEL"


class ServiceStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class FeedbackCategory(str, Enum):
    HELPFUL = "HELPFUL"
    INCORRECT = "INCORRECT"
    STALE = "STALE"
    UNSAFE = "UNSAFE"
    ROUTE_ISSUE = "ROUTE_ISSUE"
    SOURCE_ISSUE = "SOURCE_ISSUE"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class Waypoint(BaseModel):
    """A single point for map rendering on the Web App."""
    lat: float
    lng: float
    label: Optional[str] = None


class RouteOption(BaseModel):
    route_id: str
    description: str
    mode: str = Field(description="e.g. car, walk, transit, flight")
    estimated_duration_min: Optional[int] = None
    risk_level: RiskLevel
    trade_offs: List[str] = Field(default_factory=list)
    waypoints: List[Waypoint] = Field(default_factory=list)


class EmergencyContact(BaseModel):
    name: str
    phone: str
    contact_type: str = Field(description="e.g. police, embassy, hospital, hotline")
    region: str
    effective_date: datetime


class SourceCitation(BaseModel):
    name: str
    source_type: SourceType
    url: Optional[str] = None
    published_at: Optional[datetime] = None


class DegradedService(BaseModel):
    service_name: str
    status: ServiceStatus
    detail: Optional[str] = None


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

class RecommendationResponse(BaseModel):
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION
    request_id: str

    action_code: ActionCode
    risk_level: RiskLevel
    confidence: float = Field(ge=0.0, le=1.0)

    short_summary: str
    immediate_actions: List[str] = Field(default_factory=list)

    primary_route: Optional[RouteOption] = None
    alternative_routes: List[RouteOption] = Field(default_factory=list)

    emergency_instructions: List[str] = Field(default_factory=list)
    official_contacts: List[EmergencyContact] = Field(default_factory=list)

    reasons: List[str] = Field(default_factory=list)
    sources: List[SourceCitation] = Field(default_factory=list)

    observed_at: datetime
    fetched_at: datetime
    expires_at: datetime

    limitations: List[str] = Field(default_factory=list)
    degraded_services: List[DegradedService] = Field(default_factory=list)

    @field_validator("expires_at")
    @classmethod
    def expires_after_fetched(cls, v: datetime, info):
        fetched = info.data.get("fetched_at")
        if fetched and v <= fetched:
            raise ValueError("expires_at must be after fetched_at")
        return v


class FeedbackSubmission(BaseModel):
    """Explicit, user-submitted feedback — stored separately from telemetry."""

    request_id: str
    pseudonymous_user_id: str
    category: FeedbackCategory
    comment: Optional[str] = None
    submitted_at: datetime

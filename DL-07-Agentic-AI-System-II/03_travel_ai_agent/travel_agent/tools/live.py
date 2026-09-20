"""In-process adapters for the real Module 04, Module 05, and Module 06 implementations.

These modules currently expose Python functions/classes rather than HTTP services. This
adapter runs their blocking provider calls in worker threads, validates the evidence
that Module 03 sends onward, and leaves weather/routing-provider tools on MockToolSet.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

from travel_agent.contracts import RiskLevel
from travel_agent.tools.base import ToolError
from travel_agent.tools.mocks import MockToolSet
from travel_agent.tools.schemas import (
    Alert,
    DisasterResult,
    IntegratedContext,
    KnowledgeResult,
    Record,
    RiskResult,
    RouteResult,
    TransportResult,
    TravelQuery,
)

CanonicalRecord = dict[str, Any]
TransportFetcher = Callable[..., list[CanonicalRecord]]
DisasterFetcher = Callable[..., list[CanonicalRecord]]
ContextBuilder = Callable[..., dict[str, Any]]
RiskKnowledgeFactory = Callable[..., Any]

_SOURCE_ROOT = Path(__file__).resolve().parents[3]
_IMAGE_ROOT = Path(__file__).resolve().parents[2]


def _dependency_path(directory: str, filename: str) -> Path:
    for root in (_SOURCE_ROOT, _IMAGE_ROOT):
        candidate = root / directory / filename
        if candidate.is_file():
            return candidate
    raise RuntimeError(f"cannot find {directory}/{filename}")


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_package(name: str, directory: Path) -> ModuleType:
    """Load an adjacent package without requiring the monorepo to be installed."""
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    init_path = directory / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        name,
        init_path,
        submodule_search_locations=[str(directory)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load package {directory}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def _dependencies() -> tuple[
    TransportFetcher,
    DisasterFetcher,
    ContextBuilder,
    RiskKnowledgeFactory,
]:
    transport = _load_module(
        "teamd_module04_transport",
        _dependency_path("04_external_data_services", "tomtom_transport.py"),
    )
    disaster = _load_module(
        "teamd_module04_disaster",
        _dependency_path("04_external_data_services", "gdacs_adapter.py"),
    )
    integration = _load_module(
        "teamd_module05_integration",
        _dependency_path("05_data_integration", "integration.py"),
    )
    risk_knowledge = _load_package(
        "teamd_module06_risk_knowledge",
        _dependency_path("06_risk_knowledge_services", "risk_knowledge/__init__.py").parent,
    )
    return (
        transport.fetch_canonical_transport,
        disaster.fetch_canonical_disasters,
        integration.build_context,
        risk_knowledge.RiskKnowledgeService,
    )


def _aware(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _source_url(record: CanonicalRecord) -> str:
    value = record.get("source_lineage")
    if not isinstance(value, str) or not value.startswith("https://"):
        raise ValueError("available canonical record needs HTTPS source_lineage")
    return value


def _evidence_record(record: CanonicalRecord, *, kind: str) -> Record:
    fetched_at = _aware(record.get("fetched_at"))
    expires_at = _aware(record.get("expires_at"))
    if fetched_at is None or expires_at is None:
        raise ValueError("canonical record needs fetched_at and expires_at")
    # This is the time Module 03 actually observed the provider record. Prefer the
    # source event/report time when it is usable, but never invent a future observation.
    observed_at = next(
        (
            value
            for field in ("observed_at", "event_time", "issued_at")
            if (value := _aware(record.get(field))) is not None and value <= fetched_at
        ),
        fetched_at,
    )
    source = record.get("source")
    source_name = source.get("name") if isinstance(source, dict) else None
    if not isinstance(source_name, str) or not source_name:
        raise ValueError("canonical record needs source.name")
    value = record.get("value")
    description = value.get("description") if isinstance(value, dict) else None
    excerpt = description if isinstance(description, str) and description else str(
        record.get("record_kind", "external data")
    )
    return Record(
        kind=kind,
        source_name=source_name,
        url=_source_url(record),
        official_source=False,
        observed_at=observed_at,
        fetched_at=fetched_at,
        expires_at=expires_at,
        excerpt=excerpt[:4000],
    )


def _check_record(*, kind: str, source_name: str, url: str, now: datetime) -> Record:
    return Record(
        kind=kind,
        source_name=source_name,
        url=url,
        official_source=False,
        observed_at=now,
        fetched_at=now,
        expires_at=now + timedelta(minutes=5),
        excerpt="Provider check completed and returned no matching active records.",
    )


def _bbox(query: TravelQuery) -> tuple[float, float, float, float]:
    origin_lat, origin_lon = query.origin
    destination_lat, destination_lon = query.destination
    west, east = sorted((origin_lon, destination_lon))
    south, north = sorted((origin_lat, destination_lat))
    # TomTom requires a non-zero rectangle. Padding only defines the query area; it
    # does not fabricate evidence or change the requested endpoints.
    if west == east:
        west, east = max(-180.0, west - 0.005), min(180.0, east + 0.005)
    if south == north:
        south, north = max(-90.0, south - 0.005), min(90.0, north + 0.005)
    return west, south, east, north


def _available(records: list[CanonicalRecord], tool: str) -> list[CanonicalRecord]:
    available = [record for record in records if record.get("status") == "available"]
    if available:
        return available
    unavailable = next(
        (record for record in records if record.get("status") == "unavailable"), None
    )
    if unavailable is not None:
        raise ToolError(tool, str(unavailable.get("error_code") or "provider unavailable"))
    return []


class LiveToolSet(MockToolSet):
    """Use real 04 transport/disaster, 05 integration, and 06 risk services.

    Weather and route candidates continue to use clearly-labelled mock methods until
    those teams expose compatible services.
    """

    def __init__(
        self,
        *,
        tomtom_api_key: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        transport_fetcher: TransportFetcher | None = None,
        disaster_fetcher: DisasterFetcher | None = None,
        context_builder: ContextBuilder | None = None,
        risk_knowledge_service: Any | None = None,
    ) -> None:
        super().__init__(clock)
        if (
            transport_fetcher is None
            or disaster_fetcher is None
            or context_builder is None
            or risk_knowledge_service is None
        ):
            (
                default_transport,
                default_disaster,
                default_context,
                service_factory,
            ) = _dependencies()
            transport_fetcher = transport_fetcher or default_transport
            disaster_fetcher = disaster_fetcher or default_disaster
            context_builder = context_builder or default_context
            risk_knowledge_service = risk_knowledge_service or service_factory(clock=clock)
        self._tomtom_api_key = tomtom_api_key
        self._fetch_transport = transport_fetcher
        self._fetch_disasters = disaster_fetcher
        self._build_context = context_builder
        self._risk_knowledge = risk_knowledge_service

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(UTC)

    async def transport(self, query: TravelQuery) -> TransportResult:
        now = self._now()
        try:
            canonical = await asyncio.to_thread(
                self._fetch_transport,
                _bbox(query),
                now=now,
                api_key=self._tomtom_api_key,
            )
            available = _available(canonical, "transport")
            evidence = [
                _evidence_record(record, kind="transport") for record in available
            ] or [
                _check_record(
                    kind="transport",
                    source_name="TomTom Orbis Traffic",
                    url="https://api.tomtom.com/maps/orbis/traffic/incidents/details",
                    now=now,
                )
            ]
        except ToolError:
            raise
        except Exception as error:
            raise ToolError("transport", f"invalid Module 04 result: {error}") from error
        count = len(available)
        return TransportResult(
            summary=f"TomTom returned {count} active transport incident(s).",
            records=evidence,
            canonical_records=canonical,
        )

    async def disasters(self, query: TravelQuery) -> DisasterResult:
        del query  # GDACS is fetched nationally; Module 04 already filters to Thailand.
        now = self._now()
        try:
            canonical = await asyncio.to_thread(self._fetch_disasters, now=now)
            available = _available(canonical, "disasters")
            evidence = [
                _evidence_record(record, kind="official") for record in available
            ] or [
                _check_record(
                    kind="official",
                    source_name="Global Disaster Alert and Coordination System, GDACS",
                    url="https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH",
                    now=now,
                )
            ]
            alerts = (
                [
                    self._alert(record, proof, now)
                    for record, proof in zip(available, evidence, strict=True)
                ]
                if available
                else []
            )
        except ToolError:
            raise
        except Exception as error:
            raise ToolError("disasters", f"invalid Module 04 result: {error}") from error
        return DisasterResult(
            alerts=alerts[:20],
            records=evidence,
            canonical_records=canonical,
        )

    @staticmethod
    def _alert(record: CanonicalRecord, proof: Record, now: datetime) -> Alert:
        value = record.get("value") if isinstance(record.get("value"), dict) else {}
        starts_at = _aware(value.get("starts_at"))
        ends_at = _aware(value.get("ends_at"))
        active = starts_at is not None and starts_at <= now and (ends_at is None or now <= ends_at)
        severity = {
            "LOW": RiskLevel.LOW,
            "MEDIUM": RiskLevel.MEDIUM,
            "HIGH": RiskLevel.HIGH,
        }.get(record.get("severity"), RiskLevel.MEDIUM)
        title = value.get("name")
        if not isinstance(title, str) or not title:
            title = f"GDACS {value.get('event_type') or 'disaster'} event"
        return Alert(
            hazard_id=str(record["record_id"]),
            hazard_type=str(value.get("event_type") or "DISASTER"),
            severity=severity,
            # GDACS is hazard evidence, not a Thai closure order. Module 07 decides.
            level="CAUTION",
            active=active,
            starts_at=starts_at,
            ends_at=ends_at,
            title=title[:300],
            record=proof,
        )

    async def integrate(
        self,
        query: TravelQuery,
        routes: list[dict],
        weather,
        transport: TransportResult | None,
        disasters: DisasterResult | None,
    ) -> IntegratedContext:
        del weather  # Real weather canonical records are not wired in this change.
        canonical = [
            record
            for result in (transport, disasters)
            if result is not None
            for record in result.canonical_records
        ]
        try:
            context = await asyncio.to_thread(
                self._build_context,
                {"run_id": query.run_id, "routes": routes},
                canonical,
                now=self._now(),
            )
            return IntegratedContext.model_validate(context)
        except Exception as error:
            raise ToolError("integrate", f"invalid Module 05 result: {error}") from error

    async def risk(
        self, query: TravelQuery, context: IntegratedContext | None
    ) -> RiskResult:
        try:
            result = await self._risk_knowledge.risk(
                query.model_dump(mode="python"),
                context.model_dump(mode="python") if context is not None else None,
            )
            return RiskResult.model_validate(result.model_dump(mode="python"))
        except Exception as error:
            raise ToolError("risk", f"invalid Module 06 result: {error}") from error

    async def knowledge(
        self, query: TravelQuery, alerts: list[Alert]
    ) -> KnowledgeResult:
        try:
            result = await self._risk_knowledge.knowledge(
                query.model_dump(mode="python"),
                [alert.model_dump(mode="python") for alert in alerts],
            )
            return KnowledgeResult.model_validate(result.model_dump(mode="python"))
        except Exception as error:
            raise ToolError("knowledge", f"invalid Module 06 result: {error}") from error

    async def routes(
        self,
        query: TravelQuery,
        context: IntegratedContext | None,
        risk: RiskResult | None,
    ) -> RouteResult:
        try:
            result = await self._risk_knowledge.routes(
                query.model_dump(mode="python"),
                context.model_dump(mode="python") if context is not None else None,
                risk.model_dump(mode="python") if risk is not None else None,
            )
            return RouteResult.model_validate(result.model_dump(mode="python"))
        except Exception as error:
            raise ToolError("routes", f"invalid Module 06 result: {error}") from error

"""Report data model built from incident records."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from src.compliance.mappings import COMPLIANCE_DISCLAIMER, CitationRegistry, default_registry
from src.core.incident_manager import OPEN_STATES, IncidentRecord, IncidentState
from src.core.models import utc_now_iso

REPORT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ReportData:
    title: str
    period_start: str
    period_end: str
    generated_at: str
    generated_by: str
    totals: dict[str, int]
    by_severity: dict[str, int]
    by_zone: dict[str, int]
    by_violation: dict[str, int]
    by_state: dict[str, int]
    daily_trend: dict[str, int]
    unresolved: list[dict[str, Any]]
    corrective_actions: list[dict[str, Any]]
    incidents: list[dict[str, Any]]
    compliance: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    disclaimer: str = COMPLIANCE_DISCLAIMER


def _row(incident: IncidentRecord) -> dict[str, Any]:
    reviewed = any(h.to_state in ("RESOLVED", "FALSE_POSITIVE", "DISMISSED") for h in incident.history)
    return {
        "id": incident.id,
        "opened_at": incident.opened_at,
        "camera_id": incident.camera_id,
        "zone_id": incident.zone_id,
        "violation": incident.violation,
        "severity": incident.severity,
        "state": incident.state,
        "occurrences": incident.occurrences,
        "evidence_count": len(incident.evidence_refs),
        "human_reviewed": reviewed,
    }


def build_report(
    incidents: list[IncidentRecord],
    *,
    title: str,
    period_start: str,
    period_end: str,
    generated_by: str,
    registry: CitationRegistry | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReportData:
    registry = registry or default_registry()
    in_period = [i for i in incidents if period_start <= i.opened_at <= period_end]
    open_values = {s.value for s in OPEN_STATES}
    unresolved = [_row(i) for i in in_period if i.state in open_values]
    actions = [
        {"incident_id": i.id, "at": h.at, "actor": h.actor, "action": h.to_state, "note": h.reason}
        for i in in_period
        for h in i.history
        if h.to_state in (IncidentState.INTERVENTION_LOGGED.value, IncidentState.RESOLVED.value)
    ]
    violations = Counter(i.violation for i in in_period)
    return ReportData(
        title=title,
        period_start=period_start,
        period_end=period_end,
        generated_at=utc_now_iso(),
        generated_by=generated_by,
        totals={
            "incidents": len(in_period),
            "unresolved": len(unresolved),
            "resolved": sum(1 for i in in_period if i.state == IncidentState.RESOLVED.value),
            "false_positive": sum(1 for i in in_period if i.state == IncidentState.FALSE_POSITIVE.value),
            "occurrences": sum(i.occurrences for i in in_period),
        },
        by_severity=dict(Counter(i.severity for i in in_period)),
        by_zone=dict(Counter(i.zone_id for i in in_period)),
        by_violation=dict(violations),
        by_state=dict(Counter(i.state for i in in_period)),
        daily_trend=dict(sorted(Counter(i.opened_at[:10] for i in in_period).items())),
        unresolved=unresolved,
        corrective_actions=actions,
        incidents=[_row(i) for i in in_period],
        compliance=[registry.describe(v) for v in sorted(violations)],
        metadata={
            "schema_version": REPORT_SCHEMA_VERSION,
            "mapping_version": registry.version,
            **(metadata or {}),
        },
    )

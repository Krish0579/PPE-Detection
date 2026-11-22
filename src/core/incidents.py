"""Incident lifecycle domain model and deduplication service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ESCALATED = "ESCALATED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


@dataclass
class Incident:
    camera_id: str
    zone_id: str
    violation: str
    severity: str = "WARNING"
    worker_id: int | None = None
    evidence_ref: str | None = None
    id: str = field(default_factory=lambda: f"INC-{uuid.uuid4().hex[:12].upper()}")
    status: IncidentStatus = IncidentStatus.DETECTED
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged_at: str | None = None
    resolved_at: str | None = None

    def transition(self, target: IncidentStatus) -> None:
        allowed = {
            IncidentStatus.DETECTED: {IncidentStatus.ACKNOWLEDGED, IncidentStatus.ESCALATED, IncidentStatus.RESOLVED},
            IncidentStatus.ACKNOWLEDGED: {
                IncidentStatus.ESCALATED,
                IncidentStatus.IN_PROGRESS,
                IncidentStatus.RESOLVED,
            },
            IncidentStatus.ESCALATED: {IncidentStatus.IN_PROGRESS, IncidentStatus.RESOLVED},
            IncidentStatus.IN_PROGRESS: {IncidentStatus.RESOLVED},
            IncidentStatus.RESOLVED: set(),
        }
        if target not in allowed[self.status]:
            raise ValueError(f"Invalid incident transition: {self.status} -> {target}")
        self.status = target
        now = datetime.now(timezone.utc).isoformat()
        if target == IncidentStatus.ACKNOWLEDGED:
            self.acknowledged_at = now
        if target == IncidentStatus.RESOLVED:
            self.resolved_at = now


class IncidentDeduplicator:
    """Suppress repeated detections until cooldown expires or state changes."""

    def __init__(self, cooldown_seconds: float = 30.0) -> None:
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self._last_seen: dict[tuple[str, str, str, int | None], float] = {}

    def should_create(self, incident: Incident, now: float) -> bool:
        key = (incident.camera_id, incident.zone_id, incident.violation, incident.worker_id)
        previous = self._last_seen.get(key)
        if previous is not None and now - previous < self.cooldown_seconds:
            return False
        self._last_seen[key] = now
        return True

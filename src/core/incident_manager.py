"""Governed incident lifecycle with audit trail and alert deduplication (blueprint §4, §8).

State machine::

    DETECTED → ACKNOWLEDGED → INTERVENTION_LOGGED → RESOLVED
    additional states: REOPENED / FALSE_POSITIVE / DISMISSED

Every transition records who performed it, when, what changed and why.
Persistent detections update the existing open incident instead of creating
repeated alerts. This module supersedes nothing: the legacy
:mod:`src.core.incidents` model remains for existing callers.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol

from src.core.models import SafetyEvent, Severity, utc_now_iso


class IncidentState(str, Enum):
    DETECTED = "DETECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INTERVENTION_LOGGED = "INTERVENTION_LOGGED"
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    DISMISSED = "DISMISSED"


OPEN_STATES = frozenset(
    {IncidentState.DETECTED, IncidentState.ACKNOWLEDGED, IncidentState.INTERVENTION_LOGGED, IncidentState.REOPENED}
)

ALLOWED_TRANSITIONS: dict[IncidentState, frozenset[IncidentState]] = {
    IncidentState.DETECTED: frozenset(
        {IncidentState.ACKNOWLEDGED, IncidentState.FALSE_POSITIVE, IncidentState.DISMISSED}
    ),
    IncidentState.ACKNOWLEDGED: frozenset(
        {IncidentState.INTERVENTION_LOGGED, IncidentState.FALSE_POSITIVE, IncidentState.DISMISSED}
    ),
    IncidentState.INTERVENTION_LOGGED: frozenset({IncidentState.INTERVENTION_LOGGED, IncidentState.RESOLVED}),
    IncidentState.RESOLVED: frozenset({IncidentState.REOPENED}),
    IncidentState.REOPENED: frozenset(
        {IncidentState.ACKNOWLEDGED, IncidentState.FALSE_POSITIVE, IncidentState.DISMISSED}
    ),
    IncidentState.FALSE_POSITIVE: frozenset({IncidentState.REOPENED}),
    IncidentState.DISMISSED: frozenset({IncidentState.REOPENED}),
}

# Transitions that must carry a human-readable justification.
REASON_REQUIRED = frozenset(
    {
        IncidentState.INTERVENTION_LOGGED,
        IncidentState.RESOLVED,
        IncidentState.REOPENED,
        IncidentState.FALSE_POSITIVE,
        IncidentState.DISMISSED,
    }
)

# Explicit permission per target state (see src.security.rbac).
TRANSITION_PERMISSIONS: dict[IncidentState, str] = {
    IncidentState.ACKNOWLEDGED: "incident.acknowledge",
    IncidentState.INTERVENTION_LOGGED: "incident.intervene",
    IncidentState.RESOLVED: "incident.resolve",
    IncidentState.REOPENED: "incident.reopen",
    IncidentState.FALSE_POSITIVE: "incident.dismiss",
    IncidentState.DISMISSED: "incident.dismiss",
}


class IncidentError(ValueError):
    pass


class AuthorizationError(PermissionError):
    pass


@dataclass(frozen=True)
class TransitionRecord:
    from_state: str
    to_state: str
    actor: str
    at: str
    reason: str = ""
    changes: dict[str, Any] = field(default_factory=dict)


@dataclass
class IncidentRecord:
    camera_id: str
    zone_id: str
    violation: str
    severity: str
    track_id: int | None = None
    rule_id: str = ""
    id: str = field(default_factory=lambda: f"INC-{uuid.uuid4().hex[:12].upper()}")
    state: str = IncidentState.DETECTED.value
    opened_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    first_seen: float = 0.0
    last_seen: float = 0.0
    occurrences: int = 1
    evidence_refs: list[str] = field(default_factory=list)
    history: list[TransitionRecord] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return IncidentState(self.state) in OPEN_STATES

    @property
    def dedupe_key(self) -> tuple[str, str, str, int | None]:
        return (self.camera_id, self.zone_id, self.violation, self.track_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IncidentRecord:
        payload = dict(data)
        payload["history"] = [TransitionRecord(**h) for h in payload.get("history", [])]
        payload["evidence_refs"] = list(payload.get("evidence_refs", []))
        return cls(**payload)


class IncidentRepository(Protocol):
    def save(self, incident: IncidentRecord) -> None: ...
    def get(self, incident_id: str) -> IncidentRecord | None: ...
    def find_open(self, dedupe_key: tuple[str, str, str, int | None]) -> IncidentRecord | None: ...
    def list_incidents(
        self, states: frozenset[IncidentState] | None = None, limit: int = 500
    ) -> list[IncidentRecord]: ...


AuditSink = Callable[[str, str, str, dict[str, Any]], None]
Authorizer = Callable[[str, str], bool]
Listener = Callable[[str, IncidentRecord], None]


class IncidentManager:
    """Owns incident persistence, deduplication and governed transitions."""

    def __init__(
        self,
        repository: IncidentRepository,
        *,
        authorizer: Authorizer | None = None,
        audit: AuditSink | None = None,
        listener: Listener | None = None,
    ) -> None:
        self._repo = repository
        self._authorize = authorizer
        self._audit = audit
        self._listener = listener
        self._lock = threading.RLock()

    # --- ingestion with deduplication ------------------------------------
    def ingest(self, event: SafetyEvent) -> tuple[IncidentRecord, bool]:
        """Create a new incident or fold the event into the matching open one.

        Returns ``(incident, created)``.
        """
        with self._lock:
            existing = self._repo.find_open(event.dedupe_key)
            if existing is not None:
                existing.occurrences += 1
                existing.last_seen = max(existing.last_seen, event.confirmed_at)
                existing.updated_at = utc_now_iso()
                if event.severity.rank > Severity.parse(existing.severity).rank:
                    existing.severity = event.severity.value
                self._repo.save(existing)
                self._notify("updated", existing)
                return existing, False

            incident = IncidentRecord(
                camera_id=event.camera_id,
                zone_id=event.zone_id,
                violation=event.violation,
                severity=event.severity.value,
                track_id=event.track_id,
                rule_id=event.rule_id,
                first_seen=event.first_seen,
                last_seen=event.confirmed_at,
            )
            self._repo.save(incident)
            self._record_audit("system", "incident.open", incident.id, {"event_id": event.id})
            self._notify("opened", incident)
            return incident, True

    def attach_evidence(self, incident_id: str, evidence_ref: str, actor: str = "system") -> IncidentRecord:
        with self._lock:
            incident = self._require(incident_id)
            if evidence_ref and evidence_ref not in incident.evidence_refs:
                incident.evidence_refs.append(evidence_ref)
                incident.updated_at = utc_now_iso()
                self._repo.save(incident)
                self._record_audit(actor, "incident.evidence", incident_id, {"evidence_ref": evidence_ref})
            return incident

    # --- governed transitions -------------------------------------------
    def transition(
        self,
        incident_id: str,
        target: IncidentState | str,
        *,
        actor: str,
        role: str = "",
        reason: str = "",
        changes: dict[str, Any] | None = None,
    ) -> IncidentRecord:
        target = IncidentState(target)
        if not actor:
            raise IncidentError("actor is required for incident transitions")
        permission = TRANSITION_PERMISSIONS.get(target, "")
        if self._authorize is not None and permission and not self._authorize(role, permission):
            self._record_audit(actor, "authorization.denied", incident_id, {"permission": permission, "role": role})
            raise AuthorizationError(f"role '{role}' lacks permission '{permission}'")
        if target in REASON_REQUIRED and not reason.strip():
            raise IncidentError(f"a reason is required to move an incident to {target.value}")
        with self._lock:
            incident = self._require(incident_id)
            current = IncidentState(incident.state)
            if target not in ALLOWED_TRANSITIONS[current]:
                raise IncidentError(f"Invalid incident transition: {current.value} -> {target.value}")
            record = TransitionRecord(
                from_state=current.value,
                to_state=target.value,
                actor=actor,
                at=utc_now_iso(),
                reason=reason.strip()[:2000],
                changes=dict(changes or {}),
            )
            incident.state = target.value
            incident.updated_at = record.at
            incident.history.append(record)
            self._repo.save(incident)
            self._record_audit(actor, "incident.transition", incident_id, asdict(record))
            self._notify("transition", incident)
            return incident

    # --- queries ---------------------------------------------------------
    def get(self, incident_id: str) -> IncidentRecord | None:
        return self._repo.get(incident_id)

    def active(self, limit: int = 500) -> list[IncidentRecord]:
        return self._repo.list_incidents(OPEN_STATES, limit)

    def history(self, limit: int = 500) -> list[IncidentRecord]:
        return self._repo.list_incidents(None, limit)

    # --- internals -------------------------------------------------------
    def _require(self, incident_id: str) -> IncidentRecord:
        incident = self._repo.get(incident_id)
        if incident is None:
            raise IncidentError(f"Unknown incident: {incident_id}")
        return incident

    def _record_audit(self, actor: str, action: str, target: str, details: dict[str, Any]) -> None:
        if self._audit is not None:
            self._audit(actor, action, target, details)

    def _notify(self, kind: str, incident: IncidentRecord) -> None:
        if self._listener is not None:
            self._listener(kind, incident)

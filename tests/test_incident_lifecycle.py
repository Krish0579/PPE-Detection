from __future__ import annotations

import pytest

from src.core.incident_manager import (
    AuthorizationError,
    IncidentError,
    IncidentManager,
    IncidentRecord,
    IncidentRepository,
    IncidentState,
)
from src.core.models import SafetyEvent, Severity


class InMemoryIncidentRepository(IncidentRepository):
    def __init__(self):
        self.incidents: dict[str, IncidentRecord] = {}

    def save(self, incident: IncidentRecord) -> None:
        self.incidents[incident.id] = incident

    def get(self, incident_id: str) -> IncidentRecord | None:
        return self.incidents.get(incident_id)

    def find_open(self, dedupe_key: tuple[str, str, str, int | None]) -> IncidentRecord | None:
        for inc in self.incidents.values():
            if inc.is_open and inc.dedupe_key == dedupe_key:
                return inc
        return None

    def list_incidents(self, states: frozenset[IncidentState] | None = None, limit: int = 500) -> list[IncidentRecord]:
        res = []
        for inc in self.incidents.values():
            if states is None or IncidentState(inc.state) in states:
                res.append(inc)
        return res[:limit]

def test_ingest_deduplication():
    repo = InMemoryIncidentRepository()
    manager = IncidentManager(repo)

    event1 = SafetyEvent(
        rule_id="R1", camera_id="C1", zone_id="Z1", violation="missing_helmet",
        severity=Severity.WARNING, track_id=1, first_seen=10.0, confirmed_at=12.0
    )
    inc1, created1 = manager.ingest(event1)
    assert created1
    assert inc1.occurrences == 1
    assert inc1.last_seen == 12.0

    event2 = SafetyEvent(
        rule_id="R1", camera_id="C1", zone_id="Z1", violation="missing_helmet",
        severity=Severity.CRITICAL, track_id=1, first_seen=10.0, confirmed_at=15.0
    )
    inc2, created2 = manager.ingest(event2)
    assert not created2
    assert inc2.id == inc1.id
    assert inc2.occurrences == 2
    assert inc2.last_seen == 15.0
    assert inc2.severity == Severity.CRITICAL.value

def test_transitions_and_authorization():
    repo = InMemoryIncidentRepository()
    
    def authorizer(role: str, permission: str) -> bool:
        if role == "admin": return True
        if role == "viewer" and permission == "incident.acknowledge": return True  # noqa: SIM103
        return False
        
    manager = IncidentManager(repo, authorizer=authorizer)

    event = SafetyEvent(
        rule_id="R1", camera_id="C1", zone_id="Z1", violation="missing_helmet",
        severity=Severity.WARNING, track_id=1, first_seen=10.0, confirmed_at=12.0
    )
    inc, _ = manager.ingest(event)
    
    with pytest.raises(AuthorizationError):
        manager.transition(inc.id, IncidentState.FALSE_POSITIVE, actor="u1", role="viewer", reason="test")

    inc = manager.transition(inc.id, IncidentState.ACKNOWLEDGED, actor="u1", role="viewer")
    assert inc.state == IncidentState.ACKNOWLEDGED.value
    assert len(inc.history) == 1
    assert inc.history[0].actor == "u1"

    with pytest.raises(IncidentError, match="reason is required"):
        manager.transition(inc.id, IncidentState.INTERVENTION_LOGGED, actor="u2", role="admin", reason="")

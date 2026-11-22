from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from src.compliance.mappings import CitationRegistry, RequirementReference
from src.reporting.exporters import to_csv, to_json, to_pdf
from src.reporting.model import build_report


# Mock IncidentHistory
@dataclass
class IncidentHistory:
    at: str
    actor: str
    to_state: str
    reason: str

# Mock IncidentRecord as expected by reporting.model
@dataclass
class IncidentRecord:
    id: str
    opened_at: str
    camera_id: str
    zone_id: str
    violation: str
    severity: str
    state: str
    occurrences: int = 1
    evidence_refs: list[str] = field(default_factory=list)
    history: list[IncidentHistory] = field(default_factory=list)

# Mock enum states
class MockIncidentState:
    RESOLVED = type('State', (), {'value': 'RESOLVED'})
    FALSE_POSITIVE = type('State', (), {'value': 'FALSE_POSITIVE'})
    INTERVENTION_LOGGED = type('State', (), {'value': 'INTERVENTION_LOGGED'})
    OPEN = type('State', (), {'value': 'OPEN'})

def mock_open_states():
    return [MockIncidentState.OPEN]

@pytest.fixture
def sample_incidents():
    return [
        IncidentRecord(
            id="inc-1", opened_at="2023-01-01T10:00:00Z", camera_id="cam1", zone_id="zoneA",
            violation="missing_helmet", severity="high", state="OPEN", occurrences=2,
            evidence_refs=["img1.jpg"]
        ),
        IncidentRecord(
            id="inc-2", opened_at="2023-01-02T11:00:00Z", camera_id="cam2", zone_id="zoneB",
            violation="missing_vest", severity="low", state="RESOLVED", occurrences=1,
            history=[IncidentHistory(at="2023-01-02T12:00:00Z", actor="admin", to_state="RESOLVED", reason="fixed")]
        )
    ]

@pytest.fixture
def patch_incident_states(monkeypatch):
    monkeypatch.setattr("src.reporting.model.OPEN_STATES", mock_open_states())
    monkeypatch.setattr("src.reporting.model.IncidentState", MockIncidentState)

def test_build_report(patch_incident_states, sample_incidents):
    reg = CitationRegistry([RequirementReference("helmet", "std", "1", "Head")])
    
    report = build_report(
        incidents=sample_incidents,
        title="Test Report",
        period_start="2023-01-01T00:00:00Z",
        period_end="2023-01-31T23:59:59Z",
        generated_by="system",
        registry=reg
    )
    
    assert report.title == "Test Report"
    assert report.totals["incidents"] == 2
    assert report.totals["unresolved"] == 1
    assert report.totals["resolved"] == 1
    assert report.totals["occurrences"] == 3
    
    assert report.by_severity["high"] == 1
    assert report.by_zone["zoneA"] == 1
    assert report.by_violation["missing_helmet"] == 1
    
    assert len(report.unresolved) == 1
    assert report.unresolved[0]["id"] == "inc-1"
    
    assert len(report.corrective_actions) == 1
    assert report.corrective_actions[0]["incident_id"] == "inc-2"
    
    assert len(report.incidents) == 2
    assert len(report.compliance) == 2  # one for each unique violation

def test_to_csv(patch_incident_states, sample_incidents):
    report = build_report(
        incidents=sample_incidents,
        title="CSV Report",
        period_start="2023-01-01",
        period_end="2023-01-31",
        generated_by="tester"
    )
    
    csv_str = to_csv(report)
    assert "id,opened_at,camera_id,zone_id,violation,severity,state" in csv_str
    assert "inc-1" in csv_str
    assert "inc-2" in csv_str

def test_to_csv_formula_injection(patch_incident_states):
    bad_incident = IncidentRecord(
        id="=CMD()", opened_at="2023-01-01T10:00:00Z", camera_id="@FOO", zone_id="-BAR",
        violation="+BAZ", severity="high", state="OPEN", occurrences=1
    )
    
    report = build_report([bad_incident], title="Test", period_start="2020-01-01", period_end="2099-12-31", generated_by="sys")
    csv_str = to_csv(report)
    
    # _safe_cell prepends ' to formula-prefixed strings
    assert "'=CMD()" in csv_str
    assert "'@FOO" in csv_str
    assert "'-BAR" in csv_str
    assert "'+BAZ" in csv_str

def test_to_json(patch_incident_states, sample_incidents):
    report = build_report(
        incidents=sample_incidents,
        title="JSON Report",
        period_start="2023-01-01",
        period_end="2023-01-31",
        generated_by="tester"
    )
    
    json_str = to_json(report)
    data = json.loads(json_str)
    
    assert data["title"] == "JSON Report"
    assert len(data["incidents"]) == 2
    assert data["incidents"][0]["id"] == "inc-1"

def test_to_pdf(patch_incident_states, sample_incidents):
    # This requires reportlab to be available
    pytest.importorskip("reportlab")
    
    report = build_report(
        incidents=sample_incidents,
        title="PDF Report",
        period_start="2023-01-01",
        period_end="2023-01-31",
        generated_by="tester"
    )
    
    pdf_bytes = to_pdf(report)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")

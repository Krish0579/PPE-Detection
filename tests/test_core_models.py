from __future__ import annotations

import pytest

from src.core.models import (
    BoundingBox,
    DetectionResult,
    PersonObservation,
    SafetyEvent,
    Severity,
)


def test_severity_escalation():
    assert Severity.INFO.escalate() == Severity.NOTICE
    assert Severity.CRITICAL.escalate() == Severity.EMERGENCY
    assert Severity.EMERGENCY.escalate() == Severity.EMERGENCY
    assert Severity.INFO.escalate(2) == Severity.WARNING

def test_severity_parse():
    assert Severity.parse("HIGH") == Severity.CRITICAL
    assert Severity.parse("LOW") == Severity.NOTICE
    assert Severity.parse(Severity.WARNING) == Severity.WARNING
    assert Severity.parse("unknown", default=Severity.INFO) == Severity.INFO
    assert Severity.parse("unknown") == Severity.WARNING

def test_bounding_box():
    box = BoundingBox(10, 20, 30, 40)
    assert box.area == 20 * 20
    assert box.as_tuple() == (10, 20, 30, 40)

    with pytest.raises(ValueError):
        BoundingBox(30, 20, 10, 40)

def test_person_observation():
    box = BoundingBox(0, 0, 10, 10)
    person = PersonObservation(
        track_id=1,
        box=box,
        confidence=0.9,
        ppe={"helmet": "PRESENT", "vest": "MISSING"},
        zone_id="Z1"
    )
    assert person.ppe_state("helmet") == "PRESENT"
    assert person.ppe_state("vest") == "MISSING"
    assert person.ppe_state("gloves") == "UNKNOWN"

def test_detection_result():
    box = BoundingBox(0, 0, 10, 10)
    person = PersonObservation(track_id=1, box=box, confidence=0.9)
    result = DetectionResult(
        camera_id="CAM1",
        frame_id=100,
        timestamp=12345.0,
        persons=(person,),
        inference_ms=10.0
    )
    assert result.camera_id == "CAM1"
    assert len(result.persons) == 1

def test_safety_event():
    event = SafetyEvent(
        rule_id="R1",
        camera_id="CAM1",
        zone_id="Z1",
        violation="missing_helmet",
        severity=Severity.WARNING,
        track_id=42,
        first_seen=1000.0,
        confirmed_at=1005.0
    )
    assert event.dedupe_key == ("CAM1", "Z1", "missing_helmet", 42)
    assert event.id.startswith("EVT-")

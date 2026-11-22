from __future__ import annotations

import pytest

from src.core.models import BoundingBox, DetectionResult, PersonObservation, Severity
from src.core.rules import RuleEngine, SafetyRule, TemporalConfirmer


def test_safety_rule_validation():
    with pytest.raises(ValueError, match="required"):
        SafetyRule(rule_id="", zone_id="Z1")
    
    with pytest.raises(ValueError, match="non-negative"):
        SafetyRule(rule_id="R1", zone_id="Z1", confirm_seconds=-1.0)

    with pytest.raises(ValueError, match="within"):
        SafetyRule(rule_id="R1", zone_id="Z1", min_confidence=1.5)

def test_temporal_confirmer():
    confirmer = TemporalConfirmer()
    key = ("R1", "CAM1", 1, "missing_helmet")
    
    track1 = confirmer.observe(key, 10.0)
    assert track1.first_seen == 10.0
    assert track1.last_seen == 10.0
    assert not track1.confirmed

    track2 = confirmer.observe(key, 12.0)
    assert track2 is track1
    assert track2.last_seen == 12.0

    cleared = confirmer.expire(16.0, {"R1": 3.0})
    assert cleared == [key]
    assert len(confirmer) == 0

def test_rule_engine_evaluate():
    rule = SafetyRule(
        rule_id="R1",
        zone_id="Z1",
        required_ppe=frozenset({"helmet"}),
        severity=Severity.WARNING,
        confirm_seconds=2.0
    )
    engine = RuleEngine([rule])

    box = BoundingBox(0, 0, 10, 10)
    # Frame 1: person seen missing helmet
    person1 = PersonObservation(track_id=1, box=box, confidence=0.9, ppe={"helmet": "MISSING"}, zone_id="Z1")
    res1 = DetectionResult(camera_id="CAM1", frame_id=1, timestamp=10.0, persons=(person1,))
    events1 = engine.evaluate(res1)
    assert len(events1) == 0  # not confirmed yet (needs 2.0s)
    assert engine.pending_conditions == 1

    # Frame 2: 1 second later
    res2 = DetectionResult(camera_id="CAM1", frame_id=2, timestamp=11.0, persons=(person1,))
    events2 = engine.evaluate(res2)
    assert len(events2) == 0

    # Frame 3: 2 seconds later (confirmed)
    res3 = DetectionResult(camera_id="CAM1", frame_id=3, timestamp=12.0, persons=(person1,))
    events3 = engine.evaluate(res3)
    assert len(events3) == 1
    
    event = events3[0]
    assert event.rule_id == "R1"
    assert event.severity == Severity.WARNING
    assert event.violation == "missing_helmet"

    # Evaluate escalation
    rule = SafetyRule(
        rule_id="R2",
        zone_id="Z1",
        required_ppe=frozenset({"helmet"}),
        severity=Severity.WARNING,
        confirm_seconds=2.0,
        escalate_after_seconds=5.0
    )
    engine2 = RuleEngine([rule])
    # t=10: start tracking
    engine2.evaluate(DetectionResult(camera_id="CAM1", frame_id=1, timestamp=10.0, persons=(person1,)))
    # t=12: confirm (persisted=2.0 >= confirm_seconds=2.0)
    evts_confirm = engine2.evaluate(DetectionResult(camera_id="CAM1", frame_id=2, timestamp=12.0, persons=(person1,)))
    assert len(evts_confirm) == 1
    assert evts_confirm[0].severity == Severity.WARNING  # confirmed, not escalated yet
    # t=16: escalate (persisted=6.0 >= escalate_after_seconds=5.0)
    evts_escalate = engine2.evaluate(DetectionResult(camera_id="CAM1", frame_id=3, timestamp=16.0, persons=(person1,)))
    assert len(evts_escalate) == 1
    assert evts_escalate[0].severity == Severity.CRITICAL  # escalated

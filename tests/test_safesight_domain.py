"""Focused tests for the production domain and integrity boundaries."""

from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from types import SimpleNamespace

from src.alerts.webhooks import WebhookDispatcher, _sign, build_violation_payload
from src.core.incidents import Incident, IncidentDeduplicator, IncidentStatus
from src.core.zones import ViolationType, ZonePolicyEngine
from src.storage.integrity import compute_image_sha256, verify_snapshot_integrity
from src.video.camera_registry import CameraFeedConfig, CameraRegistry


def test_zone_policy_required_ppe_and_dwell():
    engine = ZonePolicyEngine()
    worker = SimpleNamespace(
        worker_id=7,
        zone="Heavy Machinery Bay",
        is_restricted_zone=False,
        dwell_seconds=121,
        gear={
            "helmet": "COMPLIANT",
            "vest": "COMPLIANT",
            "boots": "COMPLIANT",
            "gloves": "VIOLATION",
            "goggles": "COMPLIANT",
        },
    )
    result = engine.evaluate_worker_zone_compliance(worker)
    assert not result.compliant
    assert any(v.type == ViolationType.MISSING_PPE for v in result.violations)
    assert any(v.type == ViolationType.EXCESSIVE_DWELL for v in result.violations)


def test_zone_policy_unknown_zone():
    result = ZonePolicyEngine().evaluate_worker_zone_compliance(SimpleNamespace(worker_id=1, zone="unknown", gear={}))
    assert not result.compliant
    assert result.violations[0].type == ViolationType.UNKNOWN_ZONE


def test_camera_registry_health_and_zone_mapping():
    registry = CameraRegistry([CameraFeedConfig("CAM-01", "Assembly A", "Assembly Line A", "demo", "demo")])
    assert registry.for_zone("Assembly Line A")[0].id == "CAM-01"
    health = registry.update_health("CAM-01", status="LIVE", fps=24.5, latency_ms=42.0)
    assert health.status == "LIVE"
    assert registry.health("CAM-01").fps == 24.5


def test_incident_state_machine():
    incident = Incident("CAM-01", "Z-01", "missing helmet", "HIGH", worker_id=2)
    incident.transition(IncidentStatus.ACKNOWLEDGED)
    incident.transition(IncidentStatus.ESCALATED)
    incident.transition(IncidentStatus.IN_PROGRESS)
    incident.transition(IncidentStatus.RESOLVED)
    assert incident.resolved_at is not None


def test_incident_invalid_transition():
    incident = Incident("CAM-01", "Z-01", "missing helmet")
    try:
        incident.transition(IncidentStatus.IN_PROGRESS)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid incident transition was accepted")


def test_incident_deduplication():
    incident = Incident("CAM-01", "Z-01", "missing helmet", worker_id=2)
    dedupe = IncidentDeduplicator(30)
    assert dedupe.should_create(incident, 100.0)
    assert not dedupe.should_create(incident, 110.0)
    assert dedupe.should_create(incident, 131.0)


def test_evidence_sha256_and_tamper_detection(tmp_path: Path):
    payload = b"evidence-bytes"
    expected = hashlib.sha256(payload).hexdigest()
    assert compute_image_sha256(payload) == expected
    path = tmp_path / "evidence.jpg"
    path.write_bytes(payload)
    assert verify_snapshot_integrity(path, expected)
    path.write_bytes(b"tampered")
    assert not verify_snapshot_integrity(path, expected)


def test_webhook_hmac_signature():
    body = b'{"incident_id":"INC-1"}'
    signature = _sign(body, "secret")
    assert signature == "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    payload = build_violation_payload(["no-helmet"], 1, 1, 0.0, incident_id="INC-1", zone_id="Z-01", severity="HIGH")
    assert payload["incident_id"] == "INC-1"


def test_dispatcher_disabled_endpoint_is_non_blocking():
    dispatcher = WebhookDispatcher([], secret="secret")
    assert dispatcher.dispatch({"event": "test"}) == []
    dispatcher.close()


def test_zone_policy_get_policy_by_name_and_id():
    engine = ZonePolicyEngine()
    policy_by_name = engine.get_policy("Assembly Line A")
    assert policy_by_name is not None
    assert policy_by_name.zone_id == "Z-01"

    policy_by_id = engine.get_policy("Z-02")
    assert policy_by_id is not None
    assert policy_by_id.name == "Heavy Machinery Bay"
    assert policy_by_id.max_dwell_seconds == 120.0

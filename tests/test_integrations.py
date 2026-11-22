"""Tests for the integrations package (adapters, policy, dispatcher)."""

from __future__ import annotations

import time

from src.core.models import Severity
from src.integrations.adapters import (
    DeliveryResult,
    SlackAdapter,
    SyslogAdapter,
    TeamsAdapter,
    WebhookAdapter,
)
from src.integrations.dispatcher import NotificationDispatcher
from src.integrations.policy import Notification, NotificationPolicy


def _make_notification(**kwargs):
    defaults = {
        "incident_id": "INC-0001",
        "kind": "opened",
        "severity": Severity.WARNING,
        "title": "Missing hard hat",
        "text": "Worker detected without helmet in zone Z-01.",
        "camera_id": "CAM-01",
        "zone_id": "Z-01",
    }
    defaults.update(kwargs)
    return Notification(**defaults)


# --- NotificationPolicy ---


class TestNotificationPolicy:
    def test_targets_route_by_severity(self):
        policy = NotificationPolicy(
            routes={Severity.WARNING: ("webhook",), Severity.CRITICAL: ("webhook", "slack")},
            cooldown_sec=0,
        )
        n = _make_notification(severity=Severity.CRITICAL)
        targets = policy.targets(n)
        assert "webhook" in targets
        assert "slack" in targets

    def test_targets_filtered_by_kind(self):
        policy = NotificationPolicy(
            routes={Severity.INFO: ("webhook",)},
            kinds=frozenset({"opened"}),
            cooldown_sec=0,
        )
        n = _make_notification(kind="updated")
        assert policy.targets(n) == []

    def test_cooldown_deduplication(self):
        policy = NotificationPolicy(
            routes={Severity.WARNING: ("webhook",)},
            cooldown_sec=60,
        )
        n = _make_notification()
        t = time.time()
        assert len(policy.targets(n, now=t)) > 0
        assert policy.targets(n, now=t + 1) == []  # within cooldown
        assert len(policy.targets(n, now=t + 61)) > 0  # after cooldown

    def test_below_threshold_returns_empty(self):
        policy = NotificationPolicy(
            routes={Severity.CRITICAL: ("webhook",)},
            cooldown_sec=0,
        )
        n = _make_notification(severity=Severity.INFO)
        assert policy.targets(n) == []


# --- Adapters format ---


class _FakeHttpResult:
    ok = True
    status = 200
    reason = ""


def _fake_http(url, payload, timeout, allowlist, secret):
    return _FakeHttpResult()


class TestWebhookAdapter:
    def test_format_contains_required_fields(self):
        adapter = WebhookAdapter("https://example.com/hook", transport=_fake_http)
        n = _make_notification()
        payload = adapter.format(n)
        assert payload["event"] == "incident.opened"
        assert payload["severity"] == "WARNING"
        assert payload["incident_id"] == "INC-0001"

    def test_send_uses_transport(self):
        adapter = WebhookAdapter("https://example.com/hook", transport=_fake_http)
        result = adapter.send(_make_notification())
        assert result.ok


class TestSlackAdapter:
    def test_format_has_blocks(self):
        adapter = SlackAdapter("https://hooks.slack.com/test", transport=_fake_http)
        payload = adapter.format(_make_notification())
        assert "blocks" in payload
        assert "text" in payload


class TestTeamsAdapter:
    def test_format_has_sections(self):
        adapter = TeamsAdapter("https://outlook.office.com/webhook/test", transport=_fake_http)
        payload = adapter.format(_make_notification())
        assert payload["@type"] == "MessageCard"
        assert "sections" in payload


class TestSyslogAdapter:
    def test_format_produces_bytes(self):
        captured = []

        def _capture(data, addr):
            captured.append(data)

        adapter = SyslogAdapter(transport=_capture)
        n = _make_notification()
        msg = adapter.format(n)
        assert isinstance(msg, bytes)
        assert b"Missing hard hat" in msg

    def test_send_calls_transport(self):
        captured = []

        def _capture(data, addr):
            captured.append(data)

        adapter = SyslogAdapter(transport=_capture)
        result = adapter.send(_make_notification())
        assert result.ok
        assert len(captured) == 1


# --- Dispatcher ---


class _CountingAdapter:
    name = "counter"

    def __init__(self):
        self.count = 0

    def send(self, notification):
        self.count += 1
        return DeliveryResult(True, self.name)


class _FailingAdapter:
    name = "fail"

    def send(self, notification):
        return DeliveryResult(False, self.name, reason="always fails")


class TestNotificationDispatcher:
    def test_submit_and_flush(self):
        adapter = _CountingAdapter()
        policy = NotificationPolicy(
            routes={Severity.WARNING: ("counter",)},
            cooldown_sec=0,
        )
        dispatcher = NotificationDispatcher([adapter], policy, workers=1, sleep=lambda _: None)
        dispatcher.start()
        try:
            assert dispatcher.submit(_make_notification())
            assert dispatcher.flush(timeout=5.0)
            assert adapter.count == 1
            stats = dispatcher.stats()
            assert stats["delivered"] == 1
        finally:
            dispatcher.stop()

    def test_filtered_notifications_not_queued(self):
        adapter = _CountingAdapter()
        policy = NotificationPolicy(
            routes={Severity.EMERGENCY: ("counter",)},
            cooldown_sec=0,
        )
        dispatcher = NotificationDispatcher([adapter], policy, workers=1)
        dispatcher.start()
        try:
            result = dispatcher.submit(_make_notification(severity=Severity.INFO))
            assert not result
            stats = dispatcher.stats()
            assert stats["filtered"] >= 1
        finally:
            dispatcher.stop()

    def test_failure_retries(self):
        adapter = _FailingAdapter()
        policy = NotificationPolicy(
            routes={Severity.WARNING: ("fail",)},
            cooldown_sec=0,
        )
        dispatcher = NotificationDispatcher(
            [adapter], policy, workers=1, max_attempts=2, sleep=lambda _: None
        )
        dispatcher.start()
        try:
            dispatcher.submit(_make_notification())
            dispatcher.flush(timeout=5.0)
            stats = dispatcher.stats()
            assert stats["failed"] >= 1
        finally:
            dispatcher.stop()

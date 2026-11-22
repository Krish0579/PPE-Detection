"""Notification adapters: generic webhook, Slack, Microsoft Teams, PagerDuty, Syslog.

HTTP adapters reuse :func:`src.alerts.webhooks.post_json`, inheriting its URL
validation, allowlist (SSRF guard) and optional HMAC signing. Transports are
injectable so adapters are testable without network access.
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from src.alerts.webhooks import post_json
from src.core.models import Severity
from src.integrations.policy import Notification


@dataclass(frozen=True)
class DeliveryResult:
    ok: bool
    adapter: str
    reason: str = ""
    status: int = 0


class NotificationAdapter(Protocol):
    name: str

    def send(self, notification: Notification) -> DeliveryResult: ...


HttpTransport = Callable[[str, dict, float, tuple[str, ...], str], Any]


def _default_http(url: str, payload: dict, timeout: float, allowlist: tuple[str, ...], secret: str) -> Any:
    return post_json(url, payload, timeout_sec=timeout, allowlist=allowlist, secret=secret)


class _HttpAdapter:
    name = "http"

    def __init__(
        self,
        url: str,
        *,
        allowlist: tuple[str, ...] = (),
        secret: str = "",
        timeout_sec: float = 5.0,
        transport: HttpTransport | None = None,
    ) -> None:
        self.url = url
        self.allowlist = tuple(allowlist)
        self.secret = secret
        self.timeout_sec = timeout_sec
        self._transport = transport or _default_http

    def format(self, notification: Notification) -> dict[str, Any]:
        raise NotImplementedError

    def send(self, notification: Notification) -> DeliveryResult:
        result = self._transport(self.url, self.format(notification), self.timeout_sec, self.allowlist, self.secret)
        return DeliveryResult(
            bool(getattr(result, "ok", False)),
            self.name,
            str(getattr(result, "reason", "")),
            int(getattr(result, "status", 0) or 0),
        )


class WebhookAdapter(_HttpAdapter):
    name = "webhook"

    def format(self, notification: Notification) -> dict[str, Any]:
        return {
            "service": "safe-sight-ai",
            "event": f"incident.{notification.kind}",
            "incident_id": notification.incident_id,
            "severity": notification.severity.value,
            "title": notification.title,
            "text": notification.text,
            "camera_id": notification.camera_id,
            "zone_id": notification.zone_id,
            "timestamp": notification.created_at,
            "data": notification.data,
        }


_SLACK_EMOJI = {
    Severity.INFO: ":information_source:",
    Severity.NOTICE: ":large_blue_circle:",
    Severity.WARNING: ":warning:",
    Severity.CRITICAL: ":rotating_light:",
    Severity.EMERGENCY: ":sos:",
}


class SlackAdapter(_HttpAdapter):
    name = "slack"

    def format(self, notification: Notification) -> dict[str, Any]:
        header = f"{_SLACK_EMOJI[notification.severity]} *{notification.severity.value}* · {notification.title}"
        context = f"Incident `{notification.incident_id}` · camera {notification.camera_id or '-'}"
        context += f" · zone {notification.zone_id or '-'}"
        return {
            "text": f"{notification.severity.value}: {notification.title}",
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": header}},
                {"type": "section", "text": {"type": "plain_text", "text": notification.text[:2900]}},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": context}]},
            ],
        }


_TEAMS_COLOR = {
    Severity.INFO: "0EA5E9",
    Severity.NOTICE: "3B82F6",
    Severity.WARNING: "F59E0B",
    Severity.CRITICAL: "DC2626",
    Severity.EMERGENCY: "7F1D1D",
}


class TeamsAdapter(_HttpAdapter):
    name = "teams"

    def format(self, notification: Notification) -> dict[str, Any]:
        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "themeColor": _TEAMS_COLOR[notification.severity],
            "summary": notification.title,
            "sections": [
                {
                    "activityTitle": f"{notification.severity.value} · {notification.title}",
                    "text": notification.text,
                    "facts": [
                        {"name": "Incident", "value": notification.incident_id},
                        {"name": "Camera", "value": notification.camera_id or "-"},
                        {"name": "Zone", "value": notification.zone_id or "-"},
                    ],
                }
            ],
        }


_PD_SEVERITY = {
    Severity.INFO: "info",
    Severity.NOTICE: "info",
    Severity.WARNING: "warning",
    Severity.CRITICAL: "error",
    Severity.EMERGENCY: "critical",
}


class PagerDutyAdapter(_HttpAdapter):
    """PagerDuty Events API v2. The routing key is a secret: pass it from the environment."""

    name = "pagerduty"
    EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"

    def __init__(self, routing_key: str, **kwargs: Any) -> None:
        if not routing_key:
            raise ValueError("PagerDuty routing key is required")
        kwargs.setdefault("allowlist", ("https://events.pagerduty.com/v2/",))
        super().__init__(kwargs.pop("url", self.EVENTS_URL), **kwargs)
        self._routing_key = routing_key

    def format(self, notification: Notification) -> dict[str, Any]:
        resolved = notification.kind == "transition" and notification.data.get("state") == "RESOLVED"
        return {
            "routing_key": self._routing_key,
            "event_action": "resolve" if resolved else "trigger",
            "dedup_key": notification.incident_id,
            "payload": {
                "summary": f"{notification.title}"[:1024],
                "severity": _PD_SEVERITY[notification.severity],
                "source": notification.camera_id or "safe-sight-ai",
                "component": notification.zone_id or "shopfloor",
                "custom_details": {"text": notification.text, **notification.data},
            },
        }


_SYSLOG_SEVERITY = {
    Severity.INFO: 6,
    Severity.NOTICE: 5,
    Severity.WARNING: 4,
    Severity.CRITICAL: 2,
    Severity.EMERGENCY: 0,
}

UdpTransport = Callable[[bytes, tuple[str, int]], None]


def _default_udp(data: bytes, address: tuple[str, int]) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(data, address)


class SyslogAdapter:
    """RFC 5424 syslog over UDP (facility local0 by default)."""

    name = "syslog"

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 514,
        *,
        facility: int = 16,
        app_name: str = "safe-sight-ai",
        transport: UdpTransport | None = None,
    ) -> None:
        if not 0 <= facility <= 23:
            raise ValueError("syslog facility must be within 0..23")
        self.address = (host, int(port))
        self.facility = facility
        self.app_name = app_name
        self._transport = transport or _default_udp

    def format(self, notification: Notification) -> bytes:
        pri = self.facility * 8 + _SYSLOG_SEVERITY[notification.severity]
        ts = datetime.fromtimestamp(notification.created_at, tz=timezone.utc).isoformat()
        host = socket.gethostname() or "-"
        msg = f"{notification.incident_id} {notification.severity.value} {notification.title}: {notification.text}"
        msg = msg.replace("\n", " ")[:1800]
        return f"<{pri}>1 {ts} {host} {self.app_name} - {notification.kind} - {msg}".encode()

    def send(self, notification: Notification) -> DeliveryResult:
        try:
            self._transport(self.format(notification), self.address)
            return DeliveryResult(True, self.name)
        except OSError as exc:
            return DeliveryResult(False, self.name, f"{type(exc).__name__}: {exc}"[:300])

"""Resilient enterprise webhook delivery with HMAC-SHA256 signing."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


@dataclass
class WebhookResult:
    ok: bool
    status: int = 0
    reason: str = ""
    elapsed_ms: float = 0.0
    attempts: int = 1


def _is_allowed(url: str, allowlist: tuple[str, ...]) -> bool:
    if not allowlist:
        return True
    try:
        candidate = urlsplit(url)
    except ValueError:
        return False
    if candidate.username or candidate.password or not candidate.hostname:
        return False
    host = candidate.hostname.lower()
    for raw in allowlist:
        try:
            allowed = urlsplit(raw if "://" in raw else f"https://{raw}")
        except ValueError:
            continue
        if not allowed.hostname or allowed.hostname.lower() != host:
            continue
        if "://" in raw and allowed.scheme != candidate.scheme:
            continue
        if allowed.port is not None and allowed.port != candidate.port:
            continue
        base = allowed.path.rstrip("/")
        path = candidate.path or "/"
        if not base or path == base or path.startswith(base + "/"):
            return True
    return False


def build_violation_payload(
    labels: list[str],
    workers: int,
    violations: int,
    safety_score: float,
    model_name: str = "",
    camera: str = "CAM-01",
    incident_id: str | None = None,
    zone_id: str = "",
    severity: str = "WARNING",
    evidence_digest: str = "",
    incident_status: str = "DETECTED",
) -> dict:
    return {
        "service": "safe-sight-ai",
        "event": "ppe-violation",
        "incident_id": incident_id,
        "timestamp": time.time(),
        "zone_id": zone_id,
        "camera": camera,
        "model": model_name,
        "workers": int(workers),
        "violations": int(violations),
        "safety_score": round(float(safety_score), 1),
        "labels": sorted(set(labels)),
        "evidence_digest": evidence_digest,
        "severity": severity,
        "incident_status": incident_status,
    }


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def post_json(
    url: str,
    payload: dict,
    timeout_sec: float = 5.0,
    allowlist: tuple[str, ...] = (),
    secret: str = "",
) -> WebhookResult:
    if not url or not url.startswith(("https://", "http://")):
        return WebhookResult(False, reason="webhook URL must start with http(s)://")
    try:
        parsed = urlsplit(url)
    except ValueError:
        return WebhookResult(False, reason="webhook URL is not parseable")
    if parsed.username or parsed.password:
        return WebhookResult(False, reason="credentials in webhook URL are not allowed")
    if not _is_allowed(url, allowlist):
        return WebhookResult(False, reason="webhook URL outside allowlist")
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "safe-sight-ai/1.0"}
    if secret:
        headers["X-SafeSight-Signature"] = _sign(body, secret)
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=max(1.0, float(timeout_sec))) as response:
            elapsed = (time.perf_counter() - started) * 1000.0
            return WebhookResult(200 <= response.status < 300, response.status, elapsed_ms=elapsed)
    except Exception as exc:
        elapsed = (time.perf_counter() - started) * 1000.0
        logger.warning("Webhook delivery failed: %s", type(exc).__name__)
        return WebhookResult(False, reason=f"{type(exc).__name__}: {exc}"[:300], elapsed_ms=elapsed)


class WebhookDispatcher:
    """Non-blocking dispatcher with retry/backoff and per-key cooldown."""

    def __init__(
        self,
        endpoints: list[str] | tuple[str, ...],
        secret: str = "",
        allowlist: tuple[str, ...] = (),
        timeout_sec: float = 5.0,
        retries: int = 2,
        cooldown_sec: float = 30.0,
    ) -> None:
        self.endpoints = tuple(endpoints)
        self.secret = secret
        self.allowlist = allowlist
        self.timeout_sec = timeout_sec
        self.retries = max(0, int(retries))
        self.cooldown_sec = max(0.0, float(cooldown_sec))
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, min(8, len(self.endpoints) or 1)), thread_name_prefix="safesight-webhook"
        )
        self._last_sent: dict[str, float] = {}
        self._lock = threading.Lock()

    def dispatch(self, payload: dict, dedupe_key: str = "") -> list:
        now = time.monotonic()
        with self._lock:
            if dedupe_key and now - self._last_sent.get(dedupe_key, 0.0) < self.cooldown_sec:
                return []
            if dedupe_key:
                self._last_sent[dedupe_key] = now
        return [self._executor.submit(self._deliver_with_retry, endpoint, payload) for endpoint in self.endpoints]

    def _deliver_with_retry(self, endpoint: str, payload: dict) -> WebhookResult:
        result = WebhookResult(False, reason="not attempted", attempts=0)
        for attempt in range(self.retries + 1):
            result = post_json(endpoint, payload, self.timeout_sec, self.allowlist, self.secret)
            result.attempts = attempt + 1
            if result.ok:
                return result
            if attempt < self.retries:
                time.sleep(min(8.0, 0.5 * (2**attempt)))
        return result

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

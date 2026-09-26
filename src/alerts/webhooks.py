"""Outbound violation webhooks (Slack-compatible / generic JSON).

Stdlib-only so the runtime lockfile stays unchanged. Delivery is best-effort:
network failures are returned as ``(False, reason)`` and logged by the caller —
they must never crash the operator session.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WebhookResult:
    ok: bool
    status: int = 0
    reason: str = ""
    elapsed_ms: float = 0.0


def _is_allowed(url: str, allowlist: tuple[str, ...]) -> bool:
    if not allowlist:
        return True
    return any(url.startswith(prefix) for prefix in allowlist)


def build_violation_payload(
    labels: list[str],
    workers: int,
    violations: int,
    safety_score: float,
    model_name: str = "",
    camera: str = "CAM-01",
) -> dict:
    return {
        "service": "safe-sight-ai",
        "event": "ppe-violation",
        "timestamp": time.time(),
        "camera": camera,
        "model": model_name,
        "workers": int(workers),
        "violations": int(violations),
        "safety_score": round(float(safety_score), 1),
        "labels": sorted(set(labels)),
    }


def post_json(
    url: str,
    payload: dict,
    timeout_sec: float = 5.0,
    allowlist: tuple[str, ...] = (),
) -> WebhookResult:
    if not url or not url.startswith(("https://", "http://")):
        return WebhookResult(ok=False, reason="webhook URL must start with http(s)://")
    if not _is_allowed(url, allowlist):
        return WebhookResult(ok=False, reason="webhook URL outside allowlist")
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "safe-sight-ai/1.0"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=max(1.0, float(timeout_sec))) as response:
            elapsed = (time.perf_counter() - started) * 1000.0
            return WebhookResult(ok=200 <= response.status < 300, status=response.status, elapsed_ms=elapsed)
    except Exception as exc:  # intentional best-effort boundary — see per-file-ignores (BLE001)
        elapsed = (time.perf_counter() - started) * 1000.0
        logger.debug("Webhook delivery to %s failed: %s", url.split("?")[0], exc)
        return WebhookResult(ok=False, reason=f"{type(exc).__name__}: {exc}"[:300], elapsed_ms=elapsed)

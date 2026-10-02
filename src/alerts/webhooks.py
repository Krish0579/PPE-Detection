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
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


@dataclass
class WebhookResult:
    ok: bool
    status: int = 0
    reason: str = ""
    elapsed_ms: float = 0.0


def _is_allowed(url: str, allowlist: tuple[str, ...]) -> bool:
    """Host-aware allowlist matching (SSRF defense).

    Plain ``startswith`` string matching admits suffix/domain attacks such as
    ``https://hooks.slack.com.evil.tld/`` against an entry of
    ``https://hooks.slack.com/`` whenever the entry's trailing slash is dropped.
    Here the candidate URL is parsed and compared structurally:

    - the host must match the entry host exactly (no substring/suffix matches);
    - if the entry carries a scheme, the candidate scheme must equal it
      (blocks ``https`` entry -> ``http`` downgrade);
    - if the entry carries a path, the candidate path must equal it or live
      beneath it (``/hooks`` admits ``/hooks/x`` but not ``/hooksetc``);
    - URLs embedding credentials (``user@host``) never match.

    Entries may be bare hosts (``hooks.slack.com``), which match the whole host
    on any scheme already accepted by ``post_json``. An empty allowlist keeps
    the documented allow-all behaviour (configuration-controlled gate).
    """
    if not allowlist:
        return True
    try:
        candidate = urlsplit(url)
        candidate_port = candidate.port
    except ValueError:
        return False
    if candidate.username or candidate.password:
        return False
    c_host = (candidate.hostname or "").lower()
    if not c_host:
        return False
    for raw_entry in allowlist:
        entry = raw_entry.strip()
        if not entry:
            continue
        try:
            allowed = urlsplit(entry if "://" in entry else f"https://{entry}")
            allowed_port = allowed.port
        except ValueError:
            continue
        a_host = (allowed.hostname or "").lower()
        if not a_host or a_host != c_host:
            continue
        if "://" in entry and allowed.scheme != candidate.scheme:
            continue
        if allowed_port is not None and allowed_port != candidate_port:
            continue
        a_path = allowed.path.rstrip("/")
        if not a_path:
            return True
        c_path = candidate.path or "/"
        if c_path == a_path or c_path.startswith(a_path + "/"):
            return True
    return False


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
    try:
        parsed = urlsplit(url)
    except ValueError:
        return WebhookResult(ok=False, reason="webhook URL is not parseable")
    if parsed.username or parsed.password:
        return WebhookResult(ok=False, reason="credentials in webhook URL are not allowed")
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

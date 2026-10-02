"""Lightweight health/version payload for operators and uptime probes."""

from __future__ import annotations

import os
import time
from pathlib import Path

from src.__version__ import __release_channel__, __version__


def build_health_payload(
    model_name: str = "",
    device: str = "cpu",
    model_loaded: bool = False,
    evidence_dir: Path | None = None,
    started_at: float | None = None,
) -> dict:
    now = time.time()
    payload: dict = {
        "service": "safe-sight-ai",
        "version": __version__,
        "channel": __release_channel__,
        "status": "ok" if model_loaded else "degraded",
        "model_loaded": bool(model_loaded),
        "model_name": model_name or "unknown",
        "device": device,
        "timestamp": now,
        "uptime_sec": round(now - started_at, 1) if started_at else 0.0,
        "build": {
            "git_sha": os.environ.get("GIT_SHA", "unknown"),
            "image_tag": os.environ.get("IMAGE_TAG", "unknown"),
        },
    }
    if evidence_dir is not None:
        try:
            files = list(Path(evidence_dir).glob("viol_*.jpg"))
            payload["evidence_files"] = len(files)
        except OSError:
            payload["evidence_files"] = -1
    return payload

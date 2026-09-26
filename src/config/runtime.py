"""Production runtime configuration — env-validated, secure-by-default.

Centralizes every ``PPE_*`` / ``SAFE_SIGHT_*`` knob so operators get one
documented surface instead of scattered ``os.environ.get`` calls. All security
sensitive flags default to the safe value; enabling them requires an explicit
operator opt-in.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _as_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(raw)) if raw is not None else default
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _as_float(raw: str | None, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(str(raw)) if raw is not None else default
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class RuntimeConfig:
    """Validated production runtime knobs."""

    # Model trust boundary — both default OFF for internet-exposed instances.
    allow_external_model_path: bool = False
    enable_model_upload: bool = False
    trusted_model_dir: Path = field(default_factory=lambda: Path("models"))

    # Upload limits (MB).
    max_image_mb: int = 25
    max_video_mb: int = 500
    max_model_mb: int = 250

    # Evidence lifecycle.
    evidence_retention_days: int = 30
    max_snapshots: int = 50
    max_db_events: int = 5000

    # Inference defaults.
    confidence: float = 0.25
    iou: float = 0.45
    max_detections: int = 50

    # Operations.
    environment: str = "production"
    log_level: str = "INFO"
    operator_password_sha256: str = ""
    auth_required: bool = False
    webhook_url: str = ""
    webhook_allowlist: tuple[str, ...] = ()
    rtsp_sources: tuple[str, ...] = ()
    privacy_blur_faces: bool = False
    metrics_enabled: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def is_auth_enabled(self) -> bool:
        return bool(self.auth_required and self.operator_password_sha256)

    def validated(self) -> list[str]:
        """Return human-readable warnings for contradictory settings."""
        warnings: list[str] = []
        if self.is_production and self.allow_external_model_path:
            warnings.append("PPE_ALLOW_EXTERNAL_MODEL_PATH=true weakens the trusted-checkpoint policy.")
        if self.is_production and self.enable_model_upload:
            warnings.append("PPE_ENABLE_MODEL_UPLOAD=true permits browser checkpoint uploads.")
        if self.auth_required and not self.operator_password_sha256:
            warnings.append("SAFE_SIGHT_AUTH_REQUIRED=true without SAFE_SIGHT_OPERATOR_PASSWORD_SHA256.")
        if self.webhook_url and self.webhook_allowlist and not any(
            self.webhook_url.startswith(prefix) for prefix in self.webhook_allowlist
        ):
            warnings.append("SAFE_SIGHT_WEBHOOK_URL is outside SAFE_SIGHT_WEBHOOK_ALLOWLIST.")
        return warnings


def load_runtime_config(env: dict[str, str] | None = None) -> RuntimeConfig:
    """Build a validated config from the process environment (or a test mapping)."""
    source = env if env is not None else os.environ
    get = source.get

    allowlist_raw = (get("SAFE_SIGHT_WEBHOOK_ALLOWLIST") or "").strip()
    allowlist = tuple(p.strip() for p in allowlist_raw.split(",") if p.strip())
    rtsp_raw = (get("PPE_RTSP_SOURCES") or "").strip()
    rtsp_sources = tuple(s.strip() for s in rtsp_raw.split(",") if s.strip())

    return RuntimeConfig(
        allow_external_model_path=_as_bool(get("PPE_ALLOW_EXTERNAL_MODEL_PATH"), False),
        enable_model_upload=_as_bool(get("PPE_ENABLE_MODEL_UPLOAD"), False),
        trusted_model_dir=Path(get("PPE_TRUSTED_MODEL_DIR") or "models"),
        max_image_mb=_as_int(get("PPE_MAX_IMAGE_MB"), 25, 1, 500),
        max_video_mb=_as_int(get("PPE_MAX_VIDEO_MB"), 500, 1, 4096),
        max_model_mb=_as_int(get("PPE_MAX_MODEL_MB"), 250, 1, 2048),
        evidence_retention_days=_as_int(get("PPE_EVIDENCE_RETENTION_DAYS"), 30, 1, 3650),
        max_snapshots=_as_int(get("PPE_MAX_SNAPSHOTS"), 50, 1, 5000),
        max_db_events=_as_int(get("PPE_MAX_DB_EVENTS"), 5000, 100, 200000),
        confidence=_as_float(get("PPE_CONF"), 0.25, 0.01, 0.99),
        iou=_as_float(get("PPE_IOU"), 0.45, 0.01, 0.99),
        max_detections=_as_int(get("PPE_MAX_DET"), 50, 1, 300),
        environment=(get("SAFE_SIGHT_ENV") or "production"),
        log_level=(get("SAFE_SIGHT_LOG_LEVEL") or "INFO").upper(),
        operator_password_sha256=(get("SAFE_SIGHT_OPERATOR_PASSWORD_SHA256") or "").strip().lower(),
        auth_required=_as_bool(get("SAFE_SIGHT_AUTH_REQUIRED"), False),
        webhook_url=(get("SAFE_SIGHT_WEBHOOK_URL") or "").strip(),
        webhook_allowlist=allowlist,
        rtsp_sources=rtsp_sources,
        privacy_blur_faces=_as_bool(get("PPE_PRIVACY_BLUR_FACES"), False),
        metrics_enabled=_as_bool(get("SAFE_SIGHT_METRICS_ENABLED"), True),
    )

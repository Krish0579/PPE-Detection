"""Centralized camera configuration and health registry."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from time import time
from urllib.parse import urlparse

_USB_RE = re.compile(r"^usb:(\d{1,2})$", re.IGNORECASE)
_RTSP_RE = re.compile(r"^rtsp:(.+)$", re.IGNORECASE)
_HTTP_RE = re.compile(r"^https?:.+", re.IGNORECASE)


@dataclass(frozen=True)
class CameraFeedConfig:
    id: str
    display_name: str
    zone: str
    source_type: str
    uri: str
    active: bool = True
    target_fps: int = 30
    resolution: tuple[int, int] | None = None

    @property
    def redacted_uri(self) -> str:
        if self.source_type in {"rtsp", "http", "webrtc"}:
            try:
                parsed = urlparse(self.uri if "://" in self.uri else f"rtsp://{self.uri}")
                return f"{self.source_type}://{parsed.hostname or '<redacted>'}"
            except ValueError:
                return f"{self.source_type}://<redacted>"
        return self.uri if self.source_type == "demo" else f"{self.source_type}:{self.uri}"


@dataclass(frozen=True)
class CameraSource(CameraFeedConfig):
    """Backward-compatible source object used by existing callers."""

    label: str = ""

    def __init__(self, id: str, kind: str, address: str, label: str = "", zone: str = "") -> None:
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "display_name", label or id)
        object.__setattr__(self, "zone", zone)
        object.__setattr__(self, "source_type", kind)
        object.__setattr__(self, "uri", address)
        object.__setattr__(self, "active", True)
        object.__setattr__(self, "target_fps", 30)
        object.__setattr__(self, "resolution", None)
        object.__setattr__(self, "label", label)

    @property
    def kind(self) -> str:
        return self.source_type

    @property
    def address(self) -> str:
        return self.uri

    @property
    def redacted(self) -> str:
        return self.redacted_uri


@dataclass
class CameraHealth:
    status: str = "UNKNOWN"
    fps: float = 0.0
    latency_ms: float = 0.0
    width: int = 0
    height: int = 0
    last_error: str = ""
    updated_at: float = field(default_factory=time)


class CameraRegistry:
    def __init__(self, cameras: list[CameraFeedConfig] | None = None) -> None:
        self._cameras = {camera.id: camera for camera in (cameras or [])}
        self._health: dict[str, CameraHealth] = {}

    def register(self, camera: CameraFeedConfig) -> None:
        self._cameras[camera.id] = camera

    def get(self, camera_id: str) -> CameraFeedConfig | None:
        return self._cameras.get(camera_id)

    def all(self) -> list[CameraFeedConfig]:
        return list(self._cameras.values())

    def for_zone(self, zone: str) -> list[CameraFeedConfig]:
        return [c for c in self._cameras.values() if c.zone == zone]

    def update_health(self, camera_id: str, **values: object) -> CameraHealth:
        health = self._health.setdefault(camera_id, CameraHealth())
        for key, value in values.items():
            if hasattr(health, key):
                setattr(health, key, value)
        health.updated_at = time()
        return health

    def health(self, camera_id: str) -> CameraHealth:
        return self._health.get(camera_id, CameraHealth())


def parse_camera_sources(raw: str) -> list[CameraSource]:
    sources: list[CameraSource] = []
    for index, token in enumerate([t.strip() for t in (raw or "").split(",") if t.strip()], start=1):
        usb = _USB_RE.match(token)
        if usb:
            sources.append(CameraSource(f"CAM-{index:02d}", "usb", usb.group(1), token))
            continue
        rtsp = _RTSP_RE.match(token)
        if rtsp and rtsp.group(1).strip():
            sources.append(CameraSource(f"CAM-{index:02d}", "rtsp", rtsp.group(1).strip(), token))
            continue
        if _HTTP_RE.match(token):
            sources.append(CameraSource(f"CAM-{index:02d}", "http", token, token))
            continue
        if token.lower() == "demo":
            sources.append(CameraSource(f"CAM-{index:02d}", "demo", "demo", "demo"))
    return sources


def default_sources() -> list[CameraSource]:
    return [CameraSource("CAM-01", "usb", "0", "usb:0", "Assembly Line A")]

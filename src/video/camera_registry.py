"""Multi-camera source registry (USB index, RTSP/HTTP stream, image folder).

Additive and non-breaking: the existing single-camera ``OpenCVCameraManager``
keeps working unchanged. New deployments describe cameras via
``PPE_CAMERA_SOURCES`` (comma-separated) or explicit registration, e.g.::

    PPE_CAMERA_SOURCES="usb:0, rtsp:rtsp://cam-02:554/stream, http:http://cam-03/mjpeg"

RTSP URLs may embed credentials — they are never logged verbatim; only the
redacted host form appears in diagnostics.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

_USB_RE = re.compile(r"^usb:(\d{1,2})$", re.IGNORECASE)
_RTSP_RE = re.compile(r"^rtsp:(.+)$", re.IGNORECASE)
_HTTP_RE = re.compile(r"^https?:.+", re.IGNORECASE)


@dataclass(frozen=True)
class CameraSource:
    id: str
    kind: str  # "usb" | "rtsp" | "http" | "demo"
    address: str
    label: str = ""

    @property
    def redacted(self) -> str:
        if self.kind in {"rtsp", "http"}:
            try:
                parsed = urlparse(self.address if "://" in self.address else f"rtsp://{self.address}")
                host = parsed.hostname or self.address
                return f"{self.kind}://{host}"
            except Exception:
                return f"{self.kind}://<redacted>"
        return f"{self.kind}:{self.address}"


def parse_camera_sources(raw: str) -> list[CameraSource]:
    sources: list[CameraSource] = []
    for index, token in enumerate([t.strip() for t in (raw or "").split(",") if t.strip()], start=1):
        usb = _USB_RE.match(token)
        if usb:
            sources.append(CameraSource(id=f"CAM-{index:02d}", kind="usb", address=usb.group(1), label=token))
            continue
        rtsp = _RTSP_RE.match(token)
        if rtsp:
            address = rtsp.group(1).strip()
            if address:
                sources.append(CameraSource(id=f"CAM-{index:02d}", kind="rtsp", address=address, label=token))
            continue
        if _HTTP_RE.match(token):
            sources.append(CameraSource(id=f"CAM-{index:02d}", kind="http", address=token, label=token))
            continue
        if token.lower() == "demo":
            sources.append(CameraSource(id=f"CAM-{index:02d}", kind="demo", address="demo", label="demo"))
    return sources


def default_sources() -> list[CameraSource]:
    return [CameraSource(id="CAM-01", kind="usb", address="0", label="usb:0")]

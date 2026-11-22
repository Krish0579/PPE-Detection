"""Stable cross-layer contracts (blueprint §1 Target Architecture).

Vision produces :class:`DetectionResult`; the safety rule engine turns those into
:class:`SafetyEvent`; incident management, UI, reporting and integrations only
consume these contracts. Nothing in this module may import UI, Streamlit,
OpenCV or model code — it is the dependency floor of the platform.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Severity(str, Enum):
    """Alert severity ladder (blueprint §4): INFO → NOTICE → WARNING → CRITICAL → EMERGENCY."""

    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"

    @property
    def rank(self) -> int:
        return _SEVERITY_ORDER.index(self)

    def escalate(self, steps: int = 1) -> Severity:
        idx = min(len(_SEVERITY_ORDER) - 1, max(0, self.rank + int(steps)))
        return _SEVERITY_ORDER[idx]

    @classmethod
    def parse(cls, raw: str | Severity | None, default: Severity | None = None) -> Severity:
        """Parse legacy severity strings (HIGH/MODERATE/...) into the canonical ladder."""
        if isinstance(raw, Severity):
            return raw
        text = str(raw or "").strip().upper()
        if text in cls.__members__:
            return cls[text]
        legacy = {"LOW": cls.NOTICE, "MODERATE": cls.WARNING, "MEDIUM": cls.WARNING, "HIGH": cls.CRITICAL}
        if text in legacy:
            return legacy[text]
        return default if default is not None else cls.WARNING


_SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.INFO,
    Severity.NOTICE,
    Severity.WARNING,
    Severity.CRITICAL,
    Severity.EMERGENCY,
)


@dataclass(frozen=True)
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int

    def __post_init__(self) -> None:
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError(f"Invalid bounding box: {self}")

    @property
    def area(self) -> int:
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass(frozen=True)
class PersonObservation:
    """One tracked person in one frame, with per-item PPE observation state.

    ``ppe`` maps a PPE item (``helmet``, ``vest`` ...) to ``PRESENT``,
    ``MISSING`` or ``UNKNOWN``. The detector never decides compliance — it
    only reports what it saw.
    """

    track_id: int | None
    box: BoundingBox
    confidence: float
    ppe: dict[str, str] = field(default_factory=dict)
    zone_id: str = ""

    def ppe_state(self, item: str) -> str:
        return str(self.ppe.get(item, "UNKNOWN")).upper()


@dataclass(frozen=True)
class DetectionResult:
    """Structured vision output for one processed frame."""

    camera_id: str
    frame_id: int
    timestamp: float
    persons: tuple[PersonObservation, ...] = ()
    inference_ms: float = 0.0
    backend: str = "cpu"
    model_version: str = ""


@dataclass(frozen=True)
class SafetyEvent:
    """A confirmed rule breach produced by the safety rule engine."""

    rule_id: str
    camera_id: str
    zone_id: str
    violation: str
    severity: Severity
    track_id: int | None
    first_seen: float
    confirmed_at: float
    confidence: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:12].upper()}")

    @property
    def dedupe_key(self) -> tuple[str, str, str, int | None]:
        return (self.camera_id, self.zone_id, self.violation, self.track_id)

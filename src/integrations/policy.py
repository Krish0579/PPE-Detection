"""Notification contract and routing policy."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from src.core.models import Severity


@dataclass(frozen=True)
class Notification:
    incident_id: str
    kind: str  # opened | updated | transition | escalated | digest
    severity: Severity
    title: str
    text: str
    camera_id: str = ""
    zone_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    @property
    def dedupe_key(self) -> str:
        return f"{self.incident_id}:{self.kind}:{self.severity.value}"


@dataclass
class NotificationPolicy:
    """Decides *whether* and *where* a notification is delivered.

    ``routes`` maps a minimum severity to adapter names; a notification goes to
    every adapter whose threshold it meets. ``kinds`` filters lifecycle kinds.
    ``cooldown_sec`` suppresses identical notifications (alert deduplication).
    """

    routes: dict[Severity, tuple[str, ...]] = field(default_factory=dict)
    kinds: frozenset[str] = frozenset({"opened", "escalated", "transition", "digest"})
    cooldown_sec: float = 60.0
    _last_sent: dict[str, float] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def targets(self, notification: Notification, now: float | None = None) -> list[str]:
        if notification.kind not in self.kinds:
            return []
        now = time.time() if now is None else now
        with self._lock:
            last = self._last_sent.get(notification.dedupe_key)
            if last is not None and now - last < self.cooldown_sec:
                return []
            selected: list[str] = []
            for threshold, adapters in sorted(self.routes.items(), key=lambda kv: kv[0].rank):
                if notification.severity.rank >= threshold.rank:
                    selected.extend(a for a in adapters if a not in selected)
            if selected:
                self._last_sent[notification.dedupe_key] = now
                if len(self._last_sent) > 10_000:
                    cutoff = now - self.cooldown_sec
                    self._last_sent = {k: v for k, v in self._last_sent.items() if v >= cutoff}
            return selected

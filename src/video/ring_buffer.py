"""Bounded, freshness-first frame buffer (blueprint §5).

Under load the oldest frames are dropped: for safety monitoring a fresh frame
is preferable to processing a stale backlog. The buffer can never grow without
bound and reports drop counts for observability.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BufferedFrame:
    frame_id: int
    captured_at: float
    data: Any


class FrameRingBuffer:
    def __init__(self, capacity: int = 4, max_age_sec: float = 1.0) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if max_age_sec <= 0:
            raise ValueError("max_age_sec must be > 0")
        self.capacity = capacity
        self.max_age_sec = max_age_sec
        self._frames: deque[BufferedFrame] = deque(maxlen=capacity)
        self._cond = threading.Condition()
        self._next_id = 0
        self.dropped_overflow = 0
        self.dropped_stale = 0
        self.pushed = 0

    def push(self, data: Any, captured_at: float | None = None) -> int:
        captured_at = time.monotonic() if captured_at is None else captured_at
        with self._cond:
            if len(self._frames) == self.capacity:
                self.dropped_overflow += 1
            self._next_id += 1
            self._frames.append(BufferedFrame(self._next_id, captured_at, data))
            self.pushed += 1
            self._cond.notify()
            return self._next_id

    def pop_latest(self, now: float | None = None, timeout: float | None = None) -> BufferedFrame | None:
        """Return the freshest non-stale frame and discard everything older."""
        with self._cond:
            if not self._frames and timeout:
                self._cond.wait(timeout)
            if not self._frames:
                return None
            now = time.monotonic() if now is None else now
            latest = self._frames.pop()
            self.dropped_stale += len(self._frames)  # older backlog is skipped deliberately
            self._frames.clear()
            if now - latest.captured_at > self.max_age_sec:
                self.dropped_stale += 1
                return None
            return latest

    @property
    def depth(self) -> int:
        with self._cond:
            return len(self._frames)

    def stats(self) -> dict[str, int]:
        with self._cond:
            return {
                "depth": len(self._frames),
                "capacity": self.capacity,
                "pushed": self.pushed,
                "dropped_overflow": self.dropped_overflow,
                "dropped_stale": self.dropped_stale,
            }

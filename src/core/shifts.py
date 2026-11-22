"""Configurable shift schedule and shift-close automation (blueprint §10).

Shifts are data, not code: any number of shifts (including ones crossing
midnight) can be configured. At shift close the manager aggregates incidents,
builds a digest via a supplied report builder, archives it and notifies
authorized recipients — each step injected so it can be tested and replaced.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any


@dataclass(frozen=True)
class ShiftDefinition:
    name: str
    start: time
    end: time

    @property
    def crosses_midnight(self) -> bool:
        return self.end <= self.start

    def window_for(self, day: date) -> tuple[datetime, datetime]:
        start = datetime.combine(day, self.start)
        end = datetime.combine(day + timedelta(days=1) if self.crosses_midnight else day, self.end)
        return start, end


def parse_shifts(raw: str) -> list[ShiftDefinition]:
    """Parse ``"A=06:00-14:00,B=14:00-22:00,C=22:00-06:00"``."""
    shifts = []
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            name, span = chunk.split("=", 1)
            start_s, end_s = span.split("-", 1)
            shifts.append(
                ShiftDefinition(name.strip(), time.fromisoformat(start_s.strip()), time.fromisoformat(end_s.strip()))
            )
        except ValueError as exc:
            raise ValueError(f"Invalid shift definition {chunk!r}: expected NAME=HH:MM-HH:MM") from exc
    return shifts


DEFAULT_SHIFTS = "A=06:00-14:00,B=14:00-22:00,C=22:00-06:00"


@dataclass(frozen=True)
class ShiftWindow:
    shift: ShiftDefinition
    start: datetime
    end: datetime

    @property
    def label(self) -> str:
        return f"{self.shift.name} {self.start:%Y-%m-%d %H:%M}–{self.end:%H:%M}"


class ShiftManager:
    def __init__(self, shifts: Iterable[ShiftDefinition] | None = None) -> None:
        self.shifts = list(shifts) if shifts is not None else parse_shifts(DEFAULT_SHIFTS)
        if not self.shifts:
            raise ValueError("at least one shift must be configured")
        names = [s.name for s in self.shifts]
        if len(set(names)) != len(names):
            raise ValueError("shift names must be unique")

    def current(self, at: datetime) -> ShiftWindow | None:
        for day in (at.date() - timedelta(days=1), at.date()):
            for shift in self.shifts:
                start, end = shift.window_for(day)
                if start <= at < end:
                    return ShiftWindow(shift, start, end)
        return None

    def previous(self, at: datetime) -> ShiftWindow | None:
        """The most recent shift window that ended at or before ``at``."""
        candidates = []
        for offset in (2, 1, 0):
            day = at.date() - timedelta(days=offset)
            for shift in self.shifts:
                start, end = shift.window_for(day)
                if end <= at:
                    candidates.append(ShiftWindow(shift, start, end))
        return max(candidates, key=lambda w: w.end) if candidates else None

    def close_shift(
        self,
        window: ShiftWindow,
        *,
        fetch_incidents: Callable[[datetime, datetime], list[Any]],
        build_digest: Callable[[ShiftWindow, list[Any]], dict[str, Any]],
        archive: Callable[[ShiftWindow, dict[str, Any]], str],
        notify: Callable[[ShiftWindow, dict[str, Any], str], None] | None = None,
    ) -> dict[str, Any]:
        """aggregate events → generate digest → archive → notify."""
        incidents = fetch_incidents(window.start, window.end)
        digest = build_digest(window, incidents)
        location = archive(window, digest)
        if notify is not None:
            notify(window, digest, location)
        return {"shift": window.label, "incidents": len(incidents), "archive": location}

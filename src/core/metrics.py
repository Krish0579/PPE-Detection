"""Safety summaries derived from the current worker-association result."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


class WorkerSafetyState(Protocol):
    """The subset of worker state needed to produce operator-facing totals."""

    is_compliant: bool
    has_active_violation: bool


@dataclass(frozen=True)
class SafetySummary:
    """A truthful, presentation-ready summary of one observed frame."""

    total_workers: int
    safe_workers: int
    violating_workers: int
    safety_score: float | None

    @property
    def has_observation(self) -> bool:
        return self.total_workers > 0


def summarise_workers(workers: Iterable[WorkerSafetyState]) -> SafetySummary:
    """Calculate a score only when at least one worker is observed."""
    observed_workers = list(workers)
    total_workers = len(observed_workers)
    safe_workers = sum(1 for worker in observed_workers if worker.is_compliant)
    violating_workers = sum(1 for worker in observed_workers if worker.has_active_violation)
    safety_score = None if total_workers == 0 else round((safe_workers / total_workers) * 100.0, 1)
    return SafetySummary(total_workers, safe_workers, violating_workers, safety_score)

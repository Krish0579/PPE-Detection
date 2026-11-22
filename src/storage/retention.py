"""Configurable retention policy across evidence, audit, reports and raw frames (blueprint §14).

The existing :func:`src.storage.backup.enforce_retention` keeps handling
``viol_*.jpg`` evidence; this module generalises retention to every artifact
class with an explicit, validated policy and a dry-run mode.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RetentionPolicy:
    evidence_days: int = 30
    audit_days: int = 365
    reports_days: int = 180
    raw_frames_days: int = 2

    def __post_init__(self) -> None:
        for name in ("evidence_days", "audit_days", "reports_days", "raw_frames_days"):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be >= 1 day")

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> RetentionPolicy:
        env = dict(os.environ if env is None else env)

        def _days(key: str, default: int) -> int:
            try:
                return max(1, int(env.get(key, default)))
            except (TypeError, ValueError):
                return default

        return cls(
            evidence_days=_days("PPE_EVIDENCE_RETENTION_DAYS", 30),
            audit_days=_days("SAFE_SIGHT_AUDIT_RETENTION_DAYS", 365),
            reports_days=_days("SAFE_SIGHT_REPORT_RETENTION_DAYS", 180),
            raw_frames_days=_days("SAFE_SIGHT_RAW_FRAME_RETENTION_DAYS", 2),
        )


@dataclass(frozen=True)
class PruneResult:
    scanned: int
    deleted: tuple[str, ...]
    freed_bytes: int
    dry_run: bool


def prune_directory(
    directory: str | Path,
    max_age_days: int,
    *,
    pattern: str = "*",
    dry_run: bool = False,
    now: float | None = None,
) -> PruneResult:
    """Delete regular files matching ``pattern`` older than ``max_age_days``.

    Symlinks and paths that resolve outside ``directory`` are never touched
    (directory-traversal guard).
    """
    root = Path(directory).resolve()
    if not root.is_dir():
        return PruneResult(0, (), 0, dry_run)
    cutoff = (time.time() if now is None else now) - max(1, int(max_age_days)) * 86400.0
    deleted: list[str] = []
    freed = 0
    scanned = 0
    for path in sorted(root.glob(pattern)):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            resolved = path.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        scanned += 1
        stat = resolved.stat()
        if stat.st_mtime >= cutoff:
            continue
        if not dry_run:
            try:
                resolved.unlink()
            except OSError:
                continue
        deleted.append(resolved.name)
        freed += stat.st_size
    return PruneResult(scanned, tuple(deleted), freed, dry_run)

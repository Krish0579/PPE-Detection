"""Evidence backup + retention enforcement (SQLite online backup + file purge).

Keeps the audit trail defensible: the database is copied with the SQLite
``backup`` API (never a raw file copy on a live WAL database), file purges are
mirrored into the ``snapshots`` index, and every run returns a machine-readable
receipt dict.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def backup_sqlite(db_path: Path, backup_dir: Path) -> dict:
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if not db_path.is_file():
        return {"ok": False, "reason": "database file not found", "path": ""}
    stamp = time.strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"ppe_events_{stamp}.db"
    try:
        with sqlite3.connect(str(db_path), timeout=15.0) as src, sqlite3.connect(str(dest)) as dst:
            src.backup(dst)
        return {"ok": True, "path": str(dest), "bytes": dest.stat().st_size}
    except (sqlite3.DatabaseError, OSError) as exc:
        logger.warning("SQLite backup failed: %s", exc)
        try:
            dest.unlink(missing_ok=True)
        except OSError:
            pass
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"[:200], "path": ""}


def enforce_retention(evidence_dir: Path, snapshots_table_purge=None, retention_days: int = 30) -> dict:
    """Delete ``viol_*.jpg`` files older than the retention window.

    ``snapshots_table_purge`` is an optional callable taking the list of deleted
    filenames so the caller (EvidenceManager) can mirror the purge into SQLite
    without creating an import cycle.
    """
    cutoff = time.time() - max(1, int(retention_days)) * 86400.0
    deleted: list[str] = []
    freed = 0
    evidence_dir = Path(evidence_dir)
    try:
        candidates = sorted(evidence_dir.glob("viol_*.jpg"))
    except OSError:
        return {"deleted": 0, "freed_bytes": 0, "files": []}
    for path in candidates:
        try:
            stat = path.stat()
            if stat.st_mtime < cutoff:
                freed += stat.st_size
                path.unlink()
                deleted.append(path.name)
        except OSError:
            continue
    if deleted and snapshots_table_purge is not None:
        try:
            snapshots_table_purge(deleted)
        except Exception as exc:  # intentional: caller callback must not fail retention — see per-file-ignores
            logger.warning("Snapshot index purge mirror failed: %s", exc)
    return {"deleted": len(deleted), "freed_bytes": freed, "files": deleted}


def copy_support_bundle(source_paths: list[Path], dest_dir: Path) -> Path:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in source_paths:
        src = Path(src)
        if src.is_file():
            try:
                shutil.copy2(src, dest_dir / src.name)
            except OSError:
                continue
    return dest_dir

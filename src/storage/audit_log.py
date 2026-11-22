"""Append-only, tamper-evident audit log (blueprint §8, §11).

Each entry stores the SHA-256 of its canonical content chained to the previous
entry's hash, so deletion or modification breaks :meth:`AuditLog.verify_chain`.
When an ``hmac_key`` is supplied, entries additionally carry an HMAC-SHA256
authenticity tag. A plain hash is integrity evidence only — it is never
described as a signature.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.models import utc_now_iso

GENESIS_HASH = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    details TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    hmac_tag TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log(target);
CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(at);
"""


@dataclass(frozen=True)
class AuditEntry:
    seq: int
    at: str
    actor: str
    action: str
    target: str
    details: dict[str, Any]
    prev_hash: str
    entry_hash: str
    hmac_tag: str = ""


def _canonical(at: str, actor: str, action: str, target: str, details_json: str, prev_hash: str) -> bytes:
    return json.dumps([at, actor, action, target, details_json, prev_hash], separators=(",", ":")).encode("utf-8")


class AuditLog:
    def __init__(self, db_path: str | Path, hmac_key: bytes | None = None) -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._key = hmac_key or None
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=15.0)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def record(self, actor: str, action: str, target: str, details: dict[str, Any] | None = None) -> AuditEntry:
        if not actor or not action:
            raise ValueError("actor and action are required")
        details_json = json.dumps(details or {}, sort_keys=True, separators=(",", ":"), default=str)
        at = utc_now_iso()
        with self._lock:
            row = self._conn.execute("SELECT entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
            prev_hash = row[0] if row else GENESIS_HASH
            canonical = _canonical(at, actor, action, target, details_json, prev_hash)
            entry_hash = hashlib.sha256(canonical).hexdigest()
            tag = hmac.new(self._key, canonical, hashlib.sha256).hexdigest() if self._key else ""
            cursor = self._conn.execute(
                "INSERT INTO audit_log (at, actor, action, target, details, prev_hash, entry_hash, hmac_tag) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (at, actor[:200], action[:200], str(target)[:200], details_json, prev_hash, entry_hash, tag),
            )
            self._conn.commit()
            seq = int(cursor.lastrowid or 0)
        return AuditEntry(seq, at, actor, action, str(target), details or {}, prev_hash, entry_hash, tag)

    def __call__(self, actor: str, action: str, target: str, details: dict[str, Any]) -> None:
        """Adapter so the log can be injected as an ``AuditSink`` callable."""
        self.record(actor, action, target, details)

    def entries(self, target: str | None = None, limit: int = 1000) -> list[AuditEntry]:
        limit = max(0, min(int(limit), 100_000))
        with self._lock:
            if target is None:
                rows = self._conn.execute("SELECT * FROM audit_log ORDER BY seq ASC LIMIT ?", (limit,)).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM audit_log WHERE target = ? ORDER BY seq ASC LIMIT ?", (target, limit)
                ).fetchall()
        return [AuditEntry(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]), r[6], r[7], r[8]) for r in rows]

    def verify_chain(self) -> tuple[bool, int | None]:
        """Return ``(ok, first_bad_seq)`` after recomputing every hash (and HMAC when keyed)."""
        prev = GENESIS_HASH
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq, at, actor, action, target, details, prev_hash, entry_hash, hmac_tag "
                "FROM audit_log ORDER BY seq ASC"
            ).fetchall()
        for seq, at, actor, action, target, details_json, prev_hash, entry_hash, tag in rows:
            canonical = _canonical(at, actor, action, target, details_json, prev_hash)
            if prev_hash != prev or hashlib.sha256(canonical).hexdigest() != entry_hash:
                return False, seq
            if self._key and not hmac.compare_digest(tag, hmac.new(self._key, canonical, hashlib.sha256).hexdigest()):
                return False, seq
            prev = entry_hash
        return True, None

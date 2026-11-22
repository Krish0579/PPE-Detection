"""Repository implementations behind the incident repository interface (blueprint §14).

SQLite supports edge / single-node deployments. A future PostgreSQL
implementation only needs to satisfy :class:`~src.core.incident_manager.IncidentRepository`
— the application never issues SQL outside this module. Relational metadata
lives here; large evidence artifacts stay on the filesystem / object storage.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from src.core.incident_manager import OPEN_STATES, IncidentRecord, IncidentState


class InMemoryIncidentRepository:
    """Thread-safe reference implementation for tests and demo mode."""

    def __init__(self) -> None:
        self._items: dict[str, IncidentRecord] = {}
        self._lock = threading.Lock()

    def save(self, incident: IncidentRecord) -> None:
        with self._lock:
            self._items[incident.id] = IncidentRecord.from_dict(incident.to_dict())

    def get(self, incident_id: str) -> IncidentRecord | None:
        with self._lock:
            item = self._items.get(incident_id)
            return IncidentRecord.from_dict(item.to_dict()) if item else None

    def find_open(self, dedupe_key: tuple[str, str, str, int | None]) -> IncidentRecord | None:
        with self._lock:
            for item in self._items.values():
                if item.is_open and item.dedupe_key == dedupe_key:
                    return IncidentRecord.from_dict(item.to_dict())
        return None

    def list_incidents(self, states: frozenset[IncidentState] | None = None, limit: int = 500) -> list[IncidentRecord]:
        wanted = {s.value for s in states} if states else None
        with self._lock:
            items = [i for i in self._items.values() if wanted is None or i.state in wanted]
        items.sort(key=lambda i: i.opened_at, reverse=True)
        return [IncidentRecord.from_dict(i.to_dict()) for i in items[: max(0, int(limit))]]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    violation TEXT NOT NULL,
    track_id INTEGER,
    state TEXT NOT NULL,
    severity TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_incidents_state ON incidents(state);
CREATE INDEX IF NOT EXISTS idx_incidents_dedupe ON incidents(camera_id, zone_id, violation, track_id);
CREATE INDEX IF NOT EXISTS idx_incidents_opened ON incidents(opened_at);
"""


class SQLiteIncidentRepository:
    """Durable incident store using parameterized queries only."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=15.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def ping(self) -> bool:
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    def save(self, incident: IncidentRecord) -> None:
        payload = json.dumps(incident.to_dict(), separators=(",", ":"), sort_keys=True)
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO incidents (id, camera_id, zone_id, violation, track_id, state, severity,
                                       opened_at, updated_at, payload)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    state=excluded.state, severity=excluded.severity,
                    updated_at=excluded.updated_at, payload=excluded.payload
                """,
                (
                    incident.id,
                    incident.camera_id,
                    incident.zone_id,
                    incident.violation,
                    incident.track_id,
                    incident.state,
                    incident.severity,
                    incident.opened_at,
                    incident.updated_at,
                    payload,
                ),
            )
            self._conn.commit()

    def get(self, incident_id: str) -> IncidentRecord | None:
        with self._lock:
            row = self._conn.execute("SELECT payload FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        return IncidentRecord.from_dict(json.loads(row[0])) if row else None

    def find_open(self, dedupe_key: tuple[str, str, str, int | None]) -> IncidentRecord | None:
        camera_id, zone_id, violation, track_id = dedupe_key
        open_states = sorted(s.value for s in OPEN_STATES)
        placeholders = ",".join("?" for _ in open_states)
        query = (
            "SELECT payload FROM incidents WHERE camera_id = ? AND zone_id = ? AND violation = ? "
            "AND track_id IS ? AND state IN (" + placeholders + ") ORDER BY opened_at DESC LIMIT 1"
        )
        with self._lock:
            row = self._conn.execute(query, (camera_id, zone_id, violation, track_id, *open_states)).fetchone()
        return IncidentRecord.from_dict(json.loads(row[0])) if row else None

    def list_incidents(self, states: frozenset[IncidentState] | None = None, limit: int = 500) -> list[IncidentRecord]:
        limit = max(0, min(int(limit), 10_000))
        with self._lock:
            if states:
                values = sorted(s.value for s in states)
                placeholders = ",".join("?" for _ in values)
                rows = self._conn.execute(
                    "SELECT payload FROM incidents WHERE state IN (" + placeholders + ") "
                    "ORDER BY opened_at DESC LIMIT ?",
                    (*values, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT payload FROM incidents ORDER BY opened_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [IncidentRecord.from_dict(json.loads(r[0])) for r in rows]

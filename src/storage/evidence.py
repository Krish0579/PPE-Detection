import csv
import io
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd

from src.config.settings import DB_PATH, EVIDENCE_DIR, JPEG_QUALITY, MAX_DB_EVENTS, MAX_SNAPSHOTS, PROJECT_ROOT

logger = logging.getLogger(__name__)
ALLOWED_EVENT_STATUSES = frozenset({"ACTIVE", "ACKNOWLEDGED", "RESOLVED"})


class EvidenceManager:
    """Manages violation frames, SQLite database event logging, disk storage, and reporting."""

    def __init__(
        self,
        storage_dir: Path = EVIDENCE_DIR,
        max_snapshots: int = MAX_SNAPSHOTS,
        db_path: Path | None = None,
        max_db_events: int = MAX_DB_EVENTS,
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.max_snapshots = max(1, int(max_snapshots))
        self.max_db_events = max(100, int(max_db_events))
        self.last_error = ""

        # Database initialization
        self.db_path = Path(db_path) if db_path else (self.storage_dir.parent / "ppe_events.db" if self.storage_dir.parent.exists() else DB_PATH)
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create database directory %s: %s", self.db_path.parent, exc)

        self._db_lock = threading.Lock()
        self._active_session_id: int | None = None
        self._snapshots_synced = False  # B4: one-time disk -> DB index backfill
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a resilient SQLite connection with WAL mode enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA busy_timeout=15000;")
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
        except sqlite3.DatabaseError as exc:
            self._record_error("Could not configure the evidence database", exc)
        return conn

    def _record_error(self, message: str, exc: Exception) -> None:
        """Keep an operator-safe diagnostic while retaining details in application logs."""
        self.last_error = message
        logger.exception("%s: %s", message, exc)

    def _init_db(self) -> None:
        """Initialize SQLite database tables and indices if not already present."""
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    conn.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS sessions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            start_time REAL NOT NULL,
                            end_time REAL,
                            model_path TEXT,
                            device TEXT,
                            total_frames INTEGER DEFAULT 0,
                            total_violations INTEGER DEFAULT 0,
                            total_persons INTEGER DEFAULT 0,
                            compliance_rate REAL DEFAULT 100.0
                        );

                        CREATE TABLE IF NOT EXISTS events (
                            id TEXT PRIMARY KEY,
                            session_id INTEGER,
                            timestamp REAL NOT NULL,
                            person_id INTEGER,
                            event_type TEXT NOT NULL,
                            violation_type TEXT,
                            severity TEXT DEFAULT 'WARNING',
                            confidence REAL DEFAULT 0.0,
                            duration REAL DEFAULT 0.0,
                            snapshot_path TEXT,
                            status TEXT DEFAULT 'ACTIVE',
                            FOREIGN KEY (session_id) REFERENCES sessions(id)
                        );

                        CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
                        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
                        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);

                        CREATE TABLE IF NOT EXISTS snapshots (
                            filename TEXT PRIMARY KEY,
                            timestamp REAL NOT NULL,
                            labels TEXT DEFAULT '',
                            violation_count INTEGER DEFAULT 0,
                            size_bytes INTEGER DEFAULT 0,
                            event_id TEXT,
                            session_id INTEGER
                        );

                        CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON snapshots(timestamp DESC);
                        """
                    )
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not initialize the evidence database", exc)

    def start_session(self, model_path: str = "models/best.pt", device: str = "cpu") -> int:
        """Register a new monitoring session in the database."""
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    cur = conn.cursor()
                    from pathlib import Path as _Path
                    _model_p = _Path(model_path)
                    try:
                        stored_model_path = str(_model_p.relative_to(PROJECT_ROOT))
                    except ValueError:
                        stored_model_path = str(model_path)
                    cur.execute(
                        "INSERT INTO sessions (start_time, model_path, device) VALUES (?, ?, ?)",
                        (time.time(), stored_model_path, str(device)),
                    )
                    conn.commit()
                    self._active_session_id = cur.lastrowid
                    return self._active_session_id
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not start an evidence session", exc)
                return 1

    def resolve_snapshot_path(self, stored_path: str) -> Path:
        """Resolve a stored snapshot path (relative or absolute) to an absolute path."""
        p = Path(stored_path)
        if p.is_absolute():
            return p
        return PROJECT_ROOT / p

    def update_session(
        self,
        session_id: int,
        total_frames: int,
        total_violations: int,
        total_persons: int,
        compliance_rate: float,
        end_time: float | None = None,
    ) -> None:
        """Update live telemetry metrics for an existing monitoring session."""
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        """
                        UPDATE sessions
                        SET total_frames = ?, total_violations = ?, total_persons = ?, compliance_rate = ?, end_time = ?
                        WHERE id = ?
                        """,
                        (total_frames, total_violations, total_persons, round(compliance_rate, 2), end_time or time.time(), session_id),
                    )
                    conn.commit()
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not update the evidence session", exc)

    def _prune_events(self, conn: sqlite3.Connection) -> None:
        """B4: Keep the events table bounded — delete oldest rows beyond the retention cap."""
        try:
            conn.execute(
                """
                DELETE FROM events
                WHERE id IN (
                    SELECT id FROM events
                    ORDER BY timestamp DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (self.max_db_events,),
            )
        except sqlite3.DatabaseError as exc:
            self._record_error("Could not prune retained evidence events", exc)

    def log_event(
        self,
        event_type: str,
        violation_type: str,
        timestamp: float | None = None,
        person_id: int = 1,
        severity: str = "WARNING",
        confidence: float = 0.0,
        duration: float = 0.0,
        snapshot_path: str | None = None,
        status: str = "ACTIVE",
        session_id: int | None = None,
    ) -> str:
        """Record an incident or clearance event in the SQLite database."""
        ts = timestamp or time.time()
        if not event_type or len(event_type) > 64:
            raise ValueError("event_type must contain 1-64 characters")
        if len(violation_type) > 500:
            raise ValueError("violation_type must contain at most 500 characters")
        normalized_status = status.upper()
        if normalized_status not in ALLOWED_EVENT_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(ALLOWED_EVENT_STATUSES))}")
        evt_id = f"evt_{datetime.fromtimestamp(ts).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        target_session = session_id if session_id is not None else self._active_session_id

        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO events (id, session_id, timestamp, person_id, event_type, violation_type, severity, confidence, duration, snapshot_path, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            evt_id,
                            target_session,
                            ts,
                            person_id,
                            event_type,
                            violation_type,
                            severity,
                            round(confidence, 4),
                            round(duration, 2),
                            snapshot_path,
                            normalized_status,
                        ),
                    )
                    self._prune_events(conn)
                    conn.commit()
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not record the evidence event", exc)
        return evt_id

    def update_event_status(self, event_id: str, new_status: str) -> bool:
        """Update the operational status of an event ('ACKNOWLEDGED', 'RESOLVED', 'ACTIVE')."""
        if not event_id or len(event_id) > 100:
            return False
        normalized_status = new_status.upper()
        if normalized_status not in ALLOWED_EVENT_STATUSES:
            return False
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        "UPDATE events SET status = ? WHERE id = ?",
                        (normalized_status, event_id),
                    )
                    conn.commit()
                    return cursor.rowcount == 1
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not update the evidence event", exc)
                return False

    def query_events(
        self,
        session_id: int | None = None,
        event_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query logged events with optional filters."""
        query = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []

        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)
        if event_type is not None:
            query += " AND event_type = ?"
            params.append(event_type)
        if status is not None:
            query += " AND status = ?"
            params.append(status.upper())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))

        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    rows = conn.execute(query, params).fetchall()
                    return [dict(r) for r in rows]
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not query evidence events", exc)
                return []

    def query_sessions(self, limit: int = 20) -> list[dict]:
        """Query recent monitoring sessions."""
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    rows = conn.execute(
                        "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?",
                        (max(1, min(int(limit), 500)),),
                    ).fetchall()
                    return [dict(r) for r in rows]
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not query evidence sessions", exc)
                return []

    def encode_jpeg(self, frame: np.ndarray, quality: int = JPEG_QUALITY) -> bytes | None:
        """Encode raw BGR frame to compressed JPEG bytes."""
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None
        quality = max(40, min(100, int(quality)))
        try:
            ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            return buf.tobytes() if ok else None
        except cv2.error as exc:
            self._record_error("Could not encode evidence image", exc)
            return None

    def save_snapshot(
        self,
        frame: np.ndarray,
        violating_labels: list[str],
        timestamp: float | None = None,
        person_id: int = 1,
        log_to_db: bool = True,
    ) -> dict | None:
        """Encode frame, save to disk, optionally log to SQLite, and return snapshot record."""
        ts = timestamp or time.time()
        jpeg_bytes = self.encode_jpeg(frame)
        if not jpeg_bytes:
            return None

        # Use labels only as a human-readable slug after removing path/control characters.
        label_slug = "-".join(
            filter(None, (re.sub(r"[^a-z0-9-]+", "-", str(label).lower()).strip("-") for label in sorted(set(violating_labels))))
        )[:30] or "violation"
        dt_str = datetime.fromtimestamp(ts).strftime("%Y%m%d_%H%M%S") + f"_{int((ts % 1) * 1000):03d}"
        filename = f"viol_{dt_str}_{label_slug}.jpg"
        file_path = self.storage_dir / filename

        # Atomically write to disk so readers never receive partial JPEG evidence.
        temp_path: Path | None = None
        try:
            with open(self.storage_dir / f".{filename}.{uuid.uuid4().hex}.tmp", "wb") as temp_file:
                temp_file.write(jpeg_bytes)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_path = Path(temp_file.name)
            temp_path.replace(file_path)
        except OSError as exc:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            self._record_error("Could not save evidence image", exc)
            return None

        # Prune old snapshots to stay within max_snapshots limit (also drop
        # their rows from the DB snapshot index so the gallery stays in sync)
        try:
            existing = sorted(self.storage_dir.glob("viol_*.jpg"))
            if len(existing) > self.max_snapshots:
                pruned_names = []
                for old_file in existing[: len(existing) - self.max_snapshots]:
                    old_file.unlink(missing_ok=True)
                    pruned_names.append(old_file.name)
                if pruned_names:
                    try:
                        with self._db_lock, self._get_connection() as conn:
                            placeholders = ",".join("?" for _ in pruned_names)
                            conn.execute(
                                f"DELETE FROM snapshots WHERE filename IN ({placeholders})",
                                pruned_names,
                            )
                            conn.commit()
                    except sqlite3.DatabaseError as exc:
                        self._record_error("Could not prune snapshot index rows", exc)
        except OSError as exc:
            self._record_error("Could not prune retained evidence images", exc)

        # Log event into SQLite DB
        event_id = None
        if log_to_db:
            try:
                v_type = ", ".join(violating_labels) if violating_labels else "violation"
                try:
                    rel_path = str(file_path.relative_to(PROJECT_ROOT))
                except ValueError:
                    rel_path = str(file_path)
                event_id = self.log_event(
                    event_type="VIOLATION",
                    violation_type=v_type,
                    timestamp=ts,
                    person_id=person_id,
                    severity="CRITICAL" if any("helmet" in l.lower() or "vest" in l.lower() for l in violating_labels) else "WARNING",
                    snapshot_path=rel_path,
                )
            except (sqlite3.DatabaseError, ValueError) as exc:
                self._record_error("Could not record the evidence image event", exc)

        # B4: index the new capture in the SQLite snapshot gallery table
        try:
            labels_str = ", ".join(sorted(set(violating_labels)))
            with self._db_lock, self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO snapshots
                        (filename, timestamp, labels, violation_count, size_bytes, event_id, session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        filename,
                        ts,
                        labels_str,
                        len(set(violating_labels)),
                        len(jpeg_bytes),
                        event_id,
                        self._active_session_id,
                    ),
                )
                conn.commit()
        except sqlite3.DatabaseError as exc:
            self._record_error("Could not index the evidence snapshot", exc)

        return {
            "ts": ts,
            "datetime": dt_str,
            "labels": violating_labels,
            "filename": filename,
            "path": str(file_path),
            "jpeg": jpeg_bytes,
            "event_id": event_id,
        }

    # ------------------------------------------------------------------
    # B4: DB-backed snapshot index — query/filter/paginate/delete
    # ------------------------------------------------------------------

    _SNAPSHOT_FILENAME_RE = re.compile(r"^viol_[A-Za-z0-9_\-]+\.jpg$")

    def _meta_from_filename(self, filename: str) -> tuple[float, str]:
        """Derive (timestamp, label-slug) from a snapshot filename; mtime fallback."""
        m = re.match(r"^viol_(\d{8})_(\d{6})_(\d{3})_([A-Za-z0-9\-]+)\.jpg$", filename)
        if m:
            try:
                ts = datetime.strptime(f"{m.group(1)}_{m.group(2)}", "%Y%m%d_%H%M%S").astimezone().timestamp() + int(m.group(3)) / 1000.0
                return ts, m.group(4)
            except ValueError:
                pass
        p = self.storage_dir / filename
        try:
            return p.stat().st_mtime, ""
        except OSError:
            return time.time(), ""

    def _sync_snapshots_from_disk(self, conn: sqlite3.Connection) -> None:
        """One-time backfill: index existing viol_*.jpg files missing from the DB."""
        known = {r["filename"] for r in conn.execute("SELECT filename FROM snapshots").fetchall()}
        for p in self.storage_dir.glob("viol_*.jpg"):
            if p.name in known:
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            ts, slug = self._meta_from_filename(p.name)
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO snapshots (filename, timestamp, labels, violation_count, size_bytes) VALUES (?, ?, ?, ?, ?)",
                    (p.name, ts, slug, 0, size),
                )
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not backfill snapshot index row", exc)

    def _ensure_snapshot_index(self) -> None:
        """Backfill the snapshot index from disk exactly once per manager lifetime."""
        if self._snapshots_synced:
            return
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    self._sync_snapshots_from_disk(conn)
                    conn.commit()
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not sync the snapshot index", exc)
        self._snapshots_synced = True

    @staticmethod
    def _sanitize_label_query(label: str | None) -> str | None:
        """Reduce a label filter to a safe LIKE fragment (no wildcards/control chars)."""
        if not label:
            return None
        cleaned = re.sub(r"[^a-zA-Z0-9\-, ]+", "", str(label)).strip().lower()
        return cleaned or None

    def _snapshot_filter_sql(self, day: str | None, label: str | None) -> tuple[str, list[Any]]:
        """Build the shared WHERE fragment + params for day/label snapshot filters."""
        query = ""
        params: list[Any] = []
        if day:
            try:
                day_start = datetime.strptime(day, "%Y-%m-%d").astimezone().timestamp()
                query += " AND timestamp >= ? AND timestamp < ?"
                params.extend([day_start, day_start + 86400.0])
            except ValueError:
                pass
        label_q = self._sanitize_label_query(label)
        if label_q:
            query += " AND LOWER(labels) LIKE ?"
            params.append(f"%{label_q}%")
        elif label is not None and str(label).strip():
            # Non-empty but unsanitizable filter (e.g. only wildcards/control
            # chars) must match nothing rather than widening the query.
            query += " AND 1=0"
        return query, params

    def query_snapshots(
        self,
        limit: int = 24,
        offset: int = 0,
        day: str | None = None,
        label: str | None = None,
    ) -> list[dict]:
        """Return indexed captures newest-first with optional day/label filters.

        Args:
            limit: max rows to return (1..500).
            offset: rows to skip (for cumulative 'load more' windows).
            day: local-date filter as ``YYYY-MM-DD``.
            label: substring filter matched against stored violation labels.
        """
        self._ensure_snapshot_index()
        where, params = self._snapshot_filter_sql(day, label)
        query = (
            "SELECT filename, timestamp, labels, violation_count, size_bytes FROM snapshots WHERE 1=1"
            + where
            + " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        )
        params.extend([max(1, min(int(limit), 500)), max(0, int(offset))])
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    rows = conn.execute(query, params).fetchall()
                    return [dict(r) for r in rows]
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not query the snapshot index", exc)
                return []

    def count_snapshots(self, day: str | None = None, label: str | None = None) -> int:
        """Count indexed captures matching the given filters."""
        self._ensure_snapshot_index()
        where, params = self._snapshot_filter_sql(day, label)
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    row = conn.execute("SELECT COUNT(*) AS n FROM snapshots WHERE 1=1" + where, params).fetchone()
                    return int(row["n"]) if row else 0
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not count the snapshot index", exc)
                return 0

    def get_snapshot_days(self) -> list[str]:
        """Distinct local capture days (YYYY-MM-DD), newest first."""
        self._ensure_snapshot_index()
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    rows = conn.execute(
                        "SELECT DISTINCT date(timestamp, 'unixepoch', 'localtime') AS d FROM snapshots ORDER BY d DESC"
                    ).fetchall()
                    return [r["d"] for r in rows if r["d"]]
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not list snapshot days", exc)
                return []

    def get_snapshot_labels(self) -> list[str]:
        """Distinct label tokens found in the snapshot index (for filter options)."""
        self._ensure_snapshot_index()
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    rows = conn.execute("SELECT labels FROM snapshots WHERE labels != ''").fetchall()
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not list snapshot labels", exc)
                return []
        tokens: set[str] = set()
        for row in rows:
            for part in re.split(r"[,\-]+", str(row["labels"])):
                tok = part.strip().lower()
                if tok and tok != "violation":
                    tokens.add(tok)
        return sorted(tokens)

    def delete_snapshot(self, filename: str) -> bool:
        """Delete a capture from disk and the snapshot index (path-safe)."""
        if not filename or not self._SNAPSHOT_FILENAME_RE.match(str(filename)):
            return False
        file_path = self.storage_dir / str(filename)
        if not file_path.is_file():
            # Still remove any stale index row so the gallery self-heals.
            with self._db_lock:
                try:
                    with self._get_connection() as conn:
                        conn.execute("DELETE FROM snapshots WHERE filename = ?", (str(filename),))
                        conn.commit()
                except sqlite3.DatabaseError:
                    pass
            return False
        try:
            file_path.unlink()
        except OSError as exc:
            self._record_error("Could not delete the evidence image", exc)
            return False
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM snapshots WHERE filename = ?", (str(filename),))
                    conn.commit()
                    return True
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not delete the snapshot index row", exc)
                return False

    def create_zip_archive(self, snapshots: list[dict]) -> bytes:
        """Bundle snapshots and an audit manifest into a downloadable in-memory ZIP archive."""
        zip_buf = io.BytesIO()
        manifest_items = []
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, snap in enumerate(snapshots, 1):
                ts_val = snap.get("ts", time.time())
                stamp = snap.get("datetime") or datetime.fromtimestamp(ts_val).strftime("%Y%m%d_%H%M%S")
                filename = f"evidence_{i:03d}_{stamp}.jpg"
                jpeg_bytes = snap.get("jpeg")
                if not jpeg_bytes and snap.get("path"):
                    try:
                        with open(snap["path"], "rb") as f:
                            jpeg_bytes = f.read()
                    except OSError as exc:
                        logger.warning("Skipping unreadable snapshot %s during ZIP export: %s", snap.get("path"), exc)
                        jpeg_bytes = None
                if jpeg_bytes:
                    zf.writestr(filename, jpeg_bytes)
                    manifest_items.append({
                        "index": i,
                        "filename": filename,
                        "timestamp": ts_val,
                        "labels": snap.get("labels", []),
                    })
            manifest_json = json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "total_snapshots": len(snapshots),
                    "items": manifest_items,
                },
                indent=2,
            )
            zf.writestr("manifest.json", manifest_json.encode("utf-8"))
        return zip_buf.getvalue()

    def generate_report_payload(
        self,
        total_frames: int,
        fps: float,
        model_name: str,
        counts: dict[str, int],
        detections: list[dict],
        events: list[dict],
    ) -> tuple[bytes, bytes]:
        """Generate (csv_bytes, json_bytes) for session report export."""
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        report = {
            "generated_at": now_iso,
            "model": model_name,
            "total_frames_processed": total_frames,
            "last_fps": round(float(fps), 2),
            "total_class_counts": counts,
            "current_detections": detections,
            "recent_events": events,
        }
        json_bytes = json.dumps(report, indent=2, default=str).encode("utf-8")

        # Tabular CSV of current frame detections
        if detections:
            df = pd.DataFrame(detections)
            csv_bytes = df.to_csv(index=False).encode("utf-8")
        else:
            csv_bytes = b"label,display_label,confidence,conf,x1,y1,x2,y2,violation,compliance,category\n"

        return csv_bytes, json_bytes

    def generate_pdf_report(
        self,
        total_frames: int,
        fps: float,
        model_name: str,
        counts: dict[str, int],
        events: list[dict],
        person_incidents: list[dict] | None = None,
        session_id: int | str | None = None,
        include_snapshots: bool = False,
    ) -> bytes:
        """Generate a certified audit report in PDF format."""
        from src.storage.pdf_report import generate_audit_pdf

        return generate_audit_pdf(
            total_frames=total_frames,
            fps=fps,
            model_name=model_name,
            counts=counts,
            person_incidents=person_incidents or [],
            events=events or [],
            session_id=session_id or self._active_session_id,
            include_snapshots=include_snapshots,
            evidence_dir=self.storage_dir,
        )

    def export_shift_audit_csv(self, session_id: int | None = None) -> str:
        """Generate a comprehensive shift audit CSV report for OSHA/ISO 45001 compliance.
        
        Returns CSV string with columns:
        [Timestamp, Worker ID, Zone, Helmet, Vest, Gloves, Boots, Goggles, Compliance Status, Incident Note]
        """
        with self._db_lock:
            try:
                with self._get_connection() as conn:
                    # Get all events for the session (or all if None)
                    if session_id is not None:
                        rows = conn.execute(
                            "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp ASC",
                            (session_id,)
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            "SELECT * FROM events ORDER BY timestamp ASC"
                        ).fetchall()
                    
                    # Also get session info for context
                    conn.execute(
                        "SELECT * FROM sessions ORDER BY start_time DESC LIMIT 1"
                    ).fetchall()
            except sqlite3.DatabaseError as exc:
                self._record_error("Could not query events for shift audit", exc)
                return "Timestamp,Worker ID,Zone,Helmet,Vest,Gloves,Boots,Goggles,Compliance Status,Incident Note\n"

        if not rows:
            return "Timestamp,Worker ID,Zone,Helmet,Vest,Gloves,Boots,Goggles,Compliance Status,Incident Note\n"

        # Build per-worker compliance timeline from events
        worker_compliance: dict[int, dict[str, Any]] = {}
        
        for row in rows:
            person_id = row["person_id"] or 1
            ts = row["timestamp"]
            dt_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            event_type = row["event_type"]
            violation_type = row["violation_type"] or ""
            status = row["status"]
            
            if person_id not in worker_compliance:
                worker_compliance[person_id] = {
                    "helmet": "UNKNOWN",
                    "vest": "UNKNOWN", 
                    "gloves": "UNKNOWN",
                    "boots": "UNKNOWN",
                    "goggles": "UNKNOWN",
                    "zone": "Production Floor",
                    "violations": [],
                    "last_update": ts
                }
            
            w_data = worker_compliance[person_id]
            w_data["last_update"] = max(w_data["last_update"], ts)
            
            # Parse violations from event
            if event_type in ("VIOLATION", "VIOLATION_UPDATE") and violation_type:
                for v in violation_type.split(","):
                    v = v.strip().lower()
                    if "helmet" in v or "hardhat" in v:
                        w_data["helmet"] = "VIOLATION"
                    if "vest" in v:
                        w_data["vest"] = "VIOLATION"
                    if "glove" in v:
                        w_data["gloves"] = "VIOLATION"
                    if "boot" in v or "shoe" in v:
                        w_data["boots"] = "VIOLATION"
                    if "goggle" in v or "glass" in v or "eye" in v:
                        w_data["goggles"] = "VIOLATION"
                    if "restrict" in v or "zone" in v:
                        w_data["zone"] = "Restricted Zone"
                
                w_data["violations"].append(f"{dt_str}: {violation_type} ({status})")

        # Generate RFC 4180 compliant CSV content
        out_buf = io.StringIO()
        writer = csv.writer(out_buf)
        writer.writerow([
            "Timestamp", "Worker ID", "Zone", "Helmet", "Vest",
            "Gloves", "Boots", "Goggles", "Compliance Status", "Incident Note"
        ])

        for worker_id, data in sorted(worker_compliance.items()):
            dt_str = datetime.fromtimestamp(data["last_update"]).strftime("%Y-%m-%d %H:%M:%S")

            # Determine overall compliance
            required = ["helmet", "vest", "boots", "gloves", "goggles"]
            has_violation = any(data.get(k) == "VIOLATION" for k in required)
            compliance_status = "NON-COMPLIANT" if has_violation else "COMPLIANT"

            incident_note = "; ".join(data["violations"][-3:]) if data["violations"] else "No violations recorded"

            writer.writerow([
                dt_str,
                f"Worker #{worker_id:02d}",
                data["zone"],
                data["helmet"],
                data["vest"],
                data["gloves"],
                data["boots"],
                data["goggles"],
                compliance_status,
                incident_note,
            ])

        return out_buf.getvalue()

    def get_storage_telemetry(self) -> dict[str, Any]:
        """Return storage usage statistics for the evidence directory."""
        try:
            files = list(self.storage_dir.glob("viol_*.jpg"))
            total_count = len(files)
            
            total_size_bytes = 0
            oldest_ts = None
            
            for f in files:
                try:
                    stat = f.stat()
                    total_size_bytes += stat.st_size
                    if oldest_ts is None or stat.st_mtime < oldest_ts:
                        oldest_ts = stat.st_mtime
                except OSError:
                    continue
            
            total_size_mb = total_size_bytes / (1024 * 1024)
            oldest_str = datetime.fromtimestamp(oldest_ts).strftime("%Y-%m-%d %H:%M:%S") if oldest_ts else "N/A"
            
            return {
                "file_count": total_count,
                "total_size_mb": round(total_size_mb, 2),
                "total_size_bytes": total_size_bytes,
                "oldest_capture": oldest_str,
                "storage_dir": str(self.storage_dir),
                "max_snapshots_configured": self.max_snapshots,
            }
        except Exception as exc:
            self._record_error("Could not compute storage telemetry", exc)
            return {
                "file_count": 0,
                "total_size_mb": 0.0,
                "total_size_bytes": 0,
                "oldest_capture": "N/A",
                "storage_dir": str(self.storage_dir),
                "max_snapshots_configured": self.max_snapshots,
            }

    def prune_stale_snapshots(self, older_than_hours: int = 24) -> dict[str, Any]:
        """Remove evidence snapshots older than specified hours.
        
        Returns dict with count of deleted files and bytes freed.
        """
        import time as time_module
        cutoff = time_module.time() - (older_than_hours * 3600)
        deleted_count = 0
        freed_bytes = 0
        
        try:
            for f in self.storage_dir.glob("viol_*.jpg"):
                try:
                    stat = f.stat()
                    if stat.st_mtime < cutoff:
                        freed_bytes += stat.st_size
                        f.unlink()
                        deleted_count += 1
                except OSError:
                    continue
            
            # Also clean up associated database events for deleted snapshots (optional, keeps DB size in check)
            # We don't auto-delete DB rows as they serve as audit trail
            
            return {
                "deleted_count": deleted_count,
                "freed_mb": round(freed_bytes / (1024 * 1024), 2),
                "freed_bytes": freed_bytes,
                "older_than_hours": older_than_hours,
            }
        except Exception as exc:
            self._record_error("Could not prune stale snapshots", exc)
            return {
                "deleted_count": 0,
                "freed_mb": 0.0,
                "freed_bytes": 0,
                "older_than_hours": older_than_hours,
                "error": str(exc),
            }

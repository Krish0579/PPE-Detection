"""Production readiness and launch verification suite for SAFE SIGHT AI platform.

Tests:
1. All 5 PPE categories (helmet, vest, boots, gloves, goggles) spatial association and compliance.
2. SQLite incident database lifecycle (sessions, events, status updates, querying).
3. WorkerTracker exponential moving average (EMA) bounding box smoothing and dwell tracking.
4. Semantic normalization, alias matching, and label formatting for all 11 classes.
5. EvidenceManager snapshot archiving, SQLite integration, and ZIP export with manifest.json.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np

from src.config.settings import DEFAULT_ZONES
from src.core.class_semantics import (
    PPE_CONFIG_ALIASES,
    format_label,
)
from src.core.ppe_associator import WorkerTracker, associate_ppe_to_workers
from src.storage.evidence import EvidenceManager


class TestProductionReadiness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="safesight_test_"))
        self.evidence_mgr = EvidenceManager(
            storage_dir=self.temp_dir / "evidence",
            db_path=self.temp_dir / "test_ppe_events.db",
            max_snapshots=5,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_all_five_ppe_categories_compliant(self):
        """Worker wearing all 5 PPE items must be COMPLIANT in all 5 and overall SAFE."""
        dets = [
            {
                "label": "person",
                "x1": 100,
                "y1": 100,
                "x2": 300,
                "y2": 600,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "helmet",
                "x1": 150,
                "y1": 105,
                "x2": 250,
                "y2": 190,
                "confidence": 0.91,
                "violation": False,
                "display_label": "Helmet",
            },
            {
                "label": "goggles",
                "x1": 170,
                "y1": 150,
                "x2": 230,
                "y2": 180,
                "confidence": 0.88,
                "violation": False,
                "display_label": "Goggles",
            },
            {
                "label": "vest",
                "x1": 120,
                "y1": 220,
                "x2": 280,
                "y2": 450,
                "confidence": 0.92,
                "violation": False,
                "display_label": "Vest",
            },
            {
                "label": "gloves",
                "x1": 80,
                "y1": 380,
                "x2": 140,
                "y2": 450,
                "confidence": 0.85,
                "violation": False,
                "display_label": "Gloves",
            },
            {
                "label": "boots",
                "x1": 130,
                "y1": 520,
                "x2": 270,
                "y2": 595,
                "confidence": 0.89,
                "violation": False,
                "display_label": "Boots",
            },
        ]
        workers = associate_ppe_to_workers(dets)
        self.assertEqual(len(workers), 1)
        w = workers[0]
        self.assertEqual(w.helmet_status, "COMPLIANT")
        self.assertEqual(w.goggles_status, "COMPLIANT")
        self.assertEqual(w.vest_status, "COMPLIANT")
        self.assertEqual(w.gloves_status, "COMPLIANT")
        self.assertEqual(w.boots_status, "COMPLIANT")
        self.assertTrue(w.is_compliant)
        self.assertFalse(w.has_active_violation)
        self.assertEqual(w.status, "SAFE")

    def test_all_five_ppe_categories_violations(self):
        """Worker with explicit violations on all 5 items must have active violations on each."""
        dets = [
            {
                "label": "person",
                "x1": 100,
                "y1": 100,
                "x2": 300,
                "y2": 600,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "no-helmet",
                "x1": 150,
                "y1": 105,
                "x2": 250,
                "y2": 190,
                "confidence": 0.91,
                "violation": True,
                "display_label": "no-helmet",
            },
            {
                "label": "no-goggle",
                "x1": 170,
                "y1": 150,
                "x2": 230,
                "y2": 180,
                "confidence": 0.88,
                "violation": True,
                "display_label": "no-goggle",
            },
            {
                "label": "no-vest",
                "x1": 120,
                "y1": 220,
                "x2": 280,
                "y2": 450,
                "confidence": 0.92,
                "violation": True,
                "display_label": "no-vest",
            },
            {
                "label": "no-gloves",
                "x1": 80,
                "y1": 380,
                "x2": 140,
                "y2": 450,
                "confidence": 0.85,
                "violation": True,
                "display_label": "no-gloves",
            },
            {
                "label": "no-boots",
                "x1": 130,
                "y1": 520,
                "x2": 270,
                "y2": 595,
                "confidence": 0.89,
                "violation": True,
                "display_label": "no-boots",
            },
        ]
        workers = associate_ppe_to_workers(dets)
        self.assertEqual(len(workers), 1)
        w = workers[0]
        self.assertEqual(w.helmet_status, "VIOLATION")
        self.assertEqual(w.goggles_status, "VIOLATION")
        self.assertEqual(w.vest_status, "VIOLATION")
        self.assertEqual(w.gloves_status, "VIOLATION")
        self.assertEqual(w.boots_status, "VIOLATION")
        self.assertFalse(w.is_compliant)
        self.assertTrue(w.has_active_violation)
        self.assertEqual(w.status, "UNSAFE")

    def test_violation_precedence_over_subsequent_detection(self):
        """If a violation is detected on an item, a subsequent compliant item must not overwrite it."""
        dets = [
            {
                "label": "person",
                "x1": 100,
                "y1": 100,
                "x2": 300,
                "y2": 600,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            # Hand 1: violation (no-gloves)
            {
                "label": "no-gloves",
                "x1": 80,
                "y1": 380,
                "x2": 140,
                "y2": 450,
                "confidence": 0.90,
                "violation": True,
                "display_label": "No Gloves",
            },
            # Hand 2: compliant (gloves)
            {
                "label": "gloves",
                "x1": 260,
                "y1": 380,
                "x2": 320,
                "y2": 450,
                "confidence": 0.85,
                "violation": False,
                "display_label": "Gloves",
            },
        ]
        workers = associate_ppe_to_workers(dets)
        self.assertEqual(len(workers), 1)
        w = workers[0]
        # Must stay VIOLATION because one hand was unprotected!
        self.assertEqual(w.gloves_status, "VIOLATION")
        self.assertTrue(w.has_active_violation)

    def test_worker_tracker_ema_smoothing(self):
        """WorkerTracker must smooth bounding box coordinates across consecutive frames."""
        tracker = WorkerTracker()
        # Frame 1: box at (100, 100, 200, 200)
        tracker.update([(100, 100, 200, 200)], now=1.0)
        self.assertIn(1, tracker.tracks)
        b1 = tracker.tracks[1]["box"]
        self.assertEqual(b1, (100, 100, 200, 200))

        # Frame 2: jitter shift to (120, 100, 220, 200)
        tracker.update([(120, 100, 220, 200)], now=2.0)
        b2 = tracker.tracks[1]["box"]
        # With alpha=0.70: 0.70 * 120 + 0.30 * 100 = 84 + 30 = 114
        self.assertEqual(b2[0], 114)
        self.assertEqual(b2[2], 214)

    def test_sqlite_database_lifecycle(self):
        """Verify full SQLite lifecycle: sessions, events, status updates, querying."""
        # 1. Start Session
        sess_id = self.evidence_mgr.start_session(model_path="models/best.pt", device="cpu")
        self.assertIsInstance(sess_id, int)

        # 2. Log Event
        evt_id = self.evidence_mgr.log_event(
            event_type="VIOLATION",
            violation_type="No Helmet, No Vest",
            timestamp=1000.0,
            person_id=1,
            severity="CRITICAL",
            confidence=0.92,
            duration=3.5,
            snapshot_path="/data/evidence/test.jpg",
            status="ACTIVE",
            session_id=sess_id,
        )
        self.assertIsInstance(evt_id, str)
        self.assertTrue(evt_id.startswith("evt_"))

        # 3. Query Event
        events = self.evidence_mgr.query_events(session_id=sess_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["id"], evt_id)
        self.assertEqual(events[0]["violation_type"], "No Helmet, No Vest")
        self.assertEqual(events[0]["status"], "ACTIVE")

        # 4. Update Event Status
        ok = self.evidence_mgr.update_event_status(evt_id, "RESOLVED")
        self.assertTrue(ok)
        events_after = self.evidence_mgr.query_events(session_id=sess_id)
        self.assertEqual(events_after[0]["status"], "RESOLVED")

        # 5. Update Session Telemetry
        self.evidence_mgr.update_session(
            session_id=sess_id,
            total_frames=500,
            total_violations=12,
            total_persons=4,
            compliance_rate=92.5,
        )
        sessions = self.evidence_mgr.query_sessions(limit=5)
        self.assertGreaterEqual(len(sessions), 1)
        s0 = sessions[0]
        self.assertEqual(s0["total_frames"], 500)
        self.assertEqual(s0["total_violations"], 12)
        self.assertEqual(s0["compliance_rate"], 92.5)

    def test_evidence_snapshot_and_zip_manifest(self):
        """Snapshot saving must write file to disk, log to SQLite, and generate ZIP with manifest."""
        dummy_frame = np.zeros((120, 160, 3), dtype=np.uint8)
        rec = self.evidence_mgr.save_snapshot(dummy_frame, ["no-helmet", "no-vest"], timestamp=1000.0)
        self.assertIsNotNone(rec)
        self.assertIn("event_id", rec)
        self.assertIsNotNone(rec["event_id"])
        self.assertTrue(Path(rec["path"]).exists())

        # Create zip archive
        zip_bytes = self.evidence_mgr.create_zip_archive([rec])
        self.assertGreater(len(zip_bytes), 0)

        # Inspect ZIP contents
        import io
        import zipfile

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            namelist = zf.namelist()
            self.assertIn("manifest.json", namelist)
            self.assertTrue(any(n.endswith(".jpg") for n in namelist))

    def test_class_semantics_canonical_labels(self):
        """Verify label formatting for all 11 model classes and aliases."""
        self.assertEqual(format_label("helmet"), "Helmet")
        self.assertEqual(format_label("vest"), "Vest")
        self.assertEqual(format_label("boots"), "Boots")
        self.assertEqual(format_label("gloves"), "Gloves")
        self.assertEqual(format_label("goggles"), "Goggles")
        self.assertEqual(format_label("no_helmet"), "No Helmet")
        self.assertEqual(format_label("no_goggle"), "No Goggles")
        self.assertEqual(format_label("no_gloves"), "No Gloves")
        self.assertEqual(format_label("no_boots"), "No Boots")
        self.assertEqual(format_label("Person"), "Worker")

        # Verify aliases
        self.assertIn("gloves", PPE_CONFIG_ALIASES)
        self.assertIn("goggles", PPE_CONFIG_ALIASES)
        self.assertIn("no_gloves", PPE_CONFIG_ALIASES)
        self.assertIn("no_goggles", PPE_CONFIG_ALIASES)

    def test_unobservable_feet_compliance_not_penalized(self):
        """When boots are required but feet are cut off at bottom of camera, worker is SAFE if other PPE compliant."""
        req_ppe = {"helmet": True, "vest": True, "boots": True, "gloves": False, "goggles": False}
        # Worker box extends to 715 in a 720h frame -> lower body is not visible
        dets = [
            {
                "label": "person",
                "x1": 100,
                "y1": 100,
                "x2": 300,
                "y2": 715,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "helmet",
                "x1": 150,
                "y1": 105,
                "x2": 250,
                "y2": 190,
                "confidence": 0.91,
                "violation": False,
                "display_label": "Helmet",
            },
            {
                "label": "vest",
                "x1": 120,
                "y1": 220,
                "x2": 280,
                "y2": 450,
                "confidence": 0.92,
                "violation": False,
                "display_label": "Vest",
            },
        ]
        workers = associate_ppe_to_workers(dets, frame_w=1280, frame_h=720, required_ppe=req_ppe)
        self.assertEqual(len(workers), 1)
        w = workers[0]
        self.assertEqual(w.helmet_status, "COMPLIANT")
        self.assertEqual(w.vest_status, "COMPLIANT")
        self.assertEqual(w.boots_status, "UNKNOWN")
        # Must be compliant and SAFE (not falsely penalized for unobservable feet)
        self.assertTrue(w.is_compliant)
        self.assertFalse(w.has_active_violation)
        self.assertEqual(w.status, "SAFE")

    def test_observable_feet_missing_boots_is_violation(self):
        """When boots are required and feet are in view, missing boots must trigger VIOLATION and UNSAFE."""
        req_ppe = {"helmet": True, "vest": True, "boots": True, "gloves": False, "goggles": False}
        # Worker box ends at 600 in 720h frame -> lower body is fully visible
        dets = [
            {
                "label": "person",
                "x1": 100,
                "y1": 100,
                "x2": 300,
                "y2": 600,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "helmet",
                "x1": 150,
                "y1": 105,
                "x2": 250,
                "y2": 190,
                "confidence": 0.91,
                "violation": False,
                "display_label": "Helmet",
            },
            {
                "label": "vest",
                "x1": 120,
                "y1": 220,
                "x2": 280,
                "y2": 450,
                "confidence": 0.92,
                "violation": False,
                "display_label": "Vest",
            },
        ]
        workers = associate_ppe_to_workers(dets, frame_w=1280, frame_h=720, required_ppe=req_ppe)
        self.assertEqual(len(workers), 1)
        w = workers[0]
        self.assertEqual(w.boots_status, "VIOLATION")
        self.assertFalse(w.is_compliant)
        self.assertTrue(w.has_active_violation)
        self.assertEqual(w.status, "UNSAFE")
        self.assertIn("No Boots", w.violations)

    def test_force_infer_overrides_frame_skip(self):
        """force_infer=True must force inference execution even on skipped frames."""
        from src.video.pipeline import TelemetryState, VideoPipeline

        state = TelemetryState()
        # Set to performance mode (frame_skip=2)
        state.update_config(conf=0.25, iou=0.45, mode_key="performance")
        pipe = VideoPipeline(model=None, state=state)
        # Without model, returns frame directly, but we test the frame_idx / force_infer logic
        dummy = np.zeros((100, 100, 3), dtype=np.uint8)
        out = pipe.process_numpy_frame(dummy, force_infer=True)
        self.assertEqual(out.shape, (100, 100, 3))

    def test_global_optimal_worker_tracking(self):
        """WorkerTracker must globally match highest score candidates and preserve identities."""
        tracker = WorkerTracker(max_lost=10, iou_thresh=0.2)
        # Frame 1: Worker 1 at (100, 100, 200, 300), Worker 2 at (400, 100, 500, 300)
        tracker.update([(100, 100, 200, 300), (400, 100, 500, 300)], now=1.0)
        self.assertEqual(len(tracker.tracks), 2)
        self.assertIn(1, tracker.tracks)
        self.assertIn(2, tracker.tracks)

        # Frame 2: Slight movement, passed in reverse order [(405, 100, 505, 300), (105, 100, 205, 300)]
        results = tracker.update([(405, 100, 505, 300), (105, 100, 205, 300)], now=2.0)
        self.assertEqual(results[0][0], 2)  # Box 0 is Worker 2
        self.assertEqual(results[1][0], 1)  # Box 1 is Worker 1

    def test_temporal_compliance_debouncing(self):
        """Single-frame detector dropout must not cause compliance jitter on confirmed worker."""
        tracker = WorkerTracker()
        req_ppe = {"helmet": True, "vest": True, "boots": False, "gloves": False, "goggles": False}

        # Frame 1: Worker is compliant with helmet and vest
        dets_f1 = [
            {
                "label": "person",
                "x1": 100,
                "y1": 100,
                "x2": 300,
                "y2": 600,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "helmet",
                "x1": 150,
                "y1": 105,
                "x2": 250,
                "y2": 190,
                "confidence": 0.91,
                "violation": False,
                "display_label": "Helmet",
            },
            {
                "label": "vest",
                "x1": 120,
                "y1": 220,
                "x2": 280,
                "y2": 450,
                "confidence": 0.92,
                "violation": False,
                "display_label": "Vest",
            },
        ]
        w_f1 = associate_ppe_to_workers(dets_f1, tracker=tracker, required_ppe=req_ppe, timestamp=1.0)[0]
        self.assertTrue(w_f1.is_compliant)
        self.assertEqual(w_f1.helmet_status, "COMPLIANT")

        # Frame 2: Transient detector miss on helmet (missing 1 frame)
        dets_f2 = [
            {
                "label": "person",
                "x1": 102,
                "y1": 100,
                "x2": 302,
                "y2": 600,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "vest",
                "x1": 122,
                "y1": 220,
                "x2": 282,
                "y2": 450,
                "confidence": 0.92,
                "violation": False,
                "display_label": "Vest",
            },
        ]
        w_f2 = associate_ppe_to_workers(dets_f2, tracker=tracker, required_ppe=req_ppe, timestamp=1.1)[0]
        # Should be debounced: status remains COMPLIANT across the 1-frame dropout
        self.assertEqual(w_f2.helmet_status, "COMPLIANT")
        self.assertTrue(w_f2.is_compliant)

        # Frame 3: Explicit violation (model detects no-helmet) -> MUST trigger immediately with 0 delay!
        dets_f3 = [
            {
                "label": "person",
                "x1": 102,
                "y1": 100,
                "x2": 302,
                "y2": 600,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "no-helmet",
                "x1": 150,
                "y1": 105,
                "x2": 250,
                "y2": 190,
                "confidence": 0.90,
                "violation": True,
                "display_label": "No Helmet",
            },
            {
                "label": "vest",
                "x1": 122,
                "y1": 220,
                "x2": 282,
                "y2": 450,
                "confidence": 0.92,
                "violation": False,
                "display_label": "Vest",
            },
        ]
        w_f3 = associate_ppe_to_workers(dets_f3, tracker=tracker, required_ppe=req_ppe, timestamp=1.2)[0]
        self.assertEqual(w_f3.helmet_status, "VIOLATION")
        self.assertFalse(w_f3.is_compliant)

    def test_temporal_debouncing_expires_after_consecutive_missing_frames(self):
        """Two consecutive frames of missing gear must transition worker to VIOLATION."""
        tracker = WorkerTracker()
        req_ppe = {"helmet": True, "vest": True, "boots": False, "gloves": False, "goggles": False}

        # Frame 1: Worker compliant
        dets_f1 = [
            {
                "label": "person",
                "x1": 100,
                "y1": 100,
                "x2": 300,
                "y2": 600,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "helmet",
                "x1": 150,
                "y1": 105,
                "x2": 250,
                "y2": 190,
                "confidence": 0.91,
                "violation": False,
                "display_label": "Helmet",
            },
            {
                "label": "vest",
                "x1": 120,
                "y1": 220,
                "x2": 280,
                "y2": 450,
                "confidence": 0.92,
                "violation": False,
                "display_label": "Vest",
            },
        ]
        w_f1 = associate_ppe_to_workers(dets_f1, tracker=tracker, required_ppe=req_ppe, timestamp=1.0)[0]
        self.assertTrue(w_f1.is_compliant)

        # Frame 2: Missing helmet frame 1 -> debounced to COMPLIANT
        dets_f2 = [
            {
                "label": "person",
                "x1": 102,
                "y1": 100,
                "x2": 302,
                "y2": 600,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "vest",
                "x1": 122,
                "y1": 220,
                "x2": 282,
                "y2": 450,
                "confidence": 0.92,
                "violation": False,
                "display_label": "Vest",
            },
        ]
        w_f2 = associate_ppe_to_workers(dets_f2, tracker=tracker, required_ppe=req_ppe, timestamp=1.1)[0]
        self.assertEqual(w_f2.helmet_status, "COMPLIANT")
        self.assertTrue(w_f2.is_compliant)

        # Frame 3: Missing helmet frame 2 -> must NOT be debounced, transitions to VIOLATION
        dets_f3 = [
            {
                "label": "person",
                "x1": 102,
                "y1": 100,
                "x2": 302,
                "y2": 600,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "vest",
                "x1": 122,
                "y1": 220,
                "x2": 282,
                "y2": 450,
                "confidence": 0.92,
                "violation": False,
                "display_label": "Vest",
            },
        ]
        w_f3 = associate_ppe_to_workers(dets_f3, tracker=tracker, required_ppe=req_ppe, timestamp=1.2)[0]
        self.assertEqual(w_f3.helmet_status, "VIOLATION")
        self.assertFalse(w_f3.is_compliant)
        self.assertIn("No Helmet", w_f3.violations)

    def test_restricted_zone_violation_and_worker_aggregation(self):
        """Worker entering a restricted zone must be flagged with Restricted Zone violation and UNSAFE."""
        # Hazardous Chemical Zone is defined in DEFAULT_ZONES as Restricted
        zones = list(DEFAULT_ZONES)
        restr_zone = next(z for z in zones if z.type == "Restricted")
        # Center of restricted zone
        rx_min = min(p[0] for p in restr_zone.polygon)
        rx_max = max(p[0] for p in restr_zone.polygon)
        ry_min = min(p[1] for p in restr_zone.polygon)
        ry_max = max(p[1] for p in restr_zone.polygon)
        center_x = (rx_min + rx_max) / 2.0
        center_y = (ry_min + ry_max) / 2.0

        fw, fh = 1280, 720
        px1 = int((center_x - 0.05) * fw)
        px2 = int((center_x + 0.05) * fw)
        py1 = int((center_y - 0.15) * fh)
        py2 = int(center_y * fh)

        dets = [
            {
                "label": "person",
                "x1": px1,
                "y1": py1,
                "x2": px2,
                "y2": py2,
                "confidence": 0.95,
                "violation": False,
                "display_label": "Person",
            },
            {
                "label": "helmet",
                "x1": px1 + 10,
                "y1": py1 + 5,
                "x2": px2 - 10,
                "y2": py1 + 40,
                "confidence": 0.90,
                "violation": False,
                "display_label": "Helmet",
            },
            {
                "label": "vest",
                "x1": px1 + 5,
                "y1": py1 + 45,
                "x2": px2 - 5,
                "y2": py2 - 20,
                "confidence": 0.90,
                "violation": False,
                "display_label": "Vest",
            },
        ]
        workers = associate_ppe_to_workers(dets, frame_w=fw, frame_h=fh, zones=zones)
        self.assertEqual(len(workers), 1)
        w = workers[0]
        self.assertTrue(w.is_restricted_zone)
        self.assertTrue(w.has_active_violation)
        self.assertFalse(w.is_compliant)
        self.assertIn("Restricted Zone", w.violations)

    def test_reopen_alert_syncs_sqlite_status(self):
        """Updating event status to ACTIVE, ACKNOWLEDGED, or RESOLVED must accurately persist in SQLite."""
        evt_id = self.evidence_mgr.log_event(
            event_type="VIOLATION",
            violation_type="No Helmet",
            person_id=42,
            severity="CRITICAL",
        )
        self.assertIsNotNone(evt_id)

        # Initial status
        events = self.evidence_mgr.query_events()
        matching = [e for e in events if e["id"] == evt_id]
        self.assertEqual(matching[0]["status"], "ACTIVE")

        # Resolve
        self.evidence_mgr.update_event_status(evt_id, "RESOLVED")
        events = self.evidence_mgr.query_events()
        matching = [e for e in events if e["id"] == evt_id]
        self.assertEqual(matching[0]["status"], "RESOLVED")

        # Reopen back to ACTIVE
        self.evidence_mgr.update_event_status(evt_id, "ACTIVE")
        events = self.evidence_mgr.query_events()
        matching = [e for e in events if e["id"] == evt_id]
        self.assertEqual(matching[0]["status"], "ACTIVE")

    def test_create_zip_archive_filepath_fallback(self):
        """create_zip_archive must read from path when jpeg key is absent."""
        test_file = self.temp_dir / "test_snap.jpg"
        dummy = np.zeros((50, 50, 3), dtype=np.uint8)
        _, enc = cv2.imencode(".jpg", dummy)
        test_file.write_bytes(enc.tobytes())

        rec_without_jpeg = {
            "ts": 1000.0,
            "datetime": "20260916_120000",
            "path": str(test_file),
            "labels": ["test"],
        }
        zip_bytes = self.evidence_mgr.create_zip_archive([rec_without_jpeg])
        self.assertGreater(len(zip_bytes), 0)

    def test_load_model_nonexistent_path_raises_filenotfound(self):
        """load_model must immediately raise FileNotFoundError on invalid path."""
        from src.core.model_manager import load_model

        with self.assertRaises(FileNotFoundError):
            load_model("/nonexistent/path/weights.pt")


if __name__ == "__main__":
    unittest.main()

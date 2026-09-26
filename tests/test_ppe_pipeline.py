"""Comprehensive verification suite for PPE Vision AI platform using standard unittest."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from src.config.settings import BGR_BAD, BGR_OK, THEME_DARK
from src.core.class_semantics import (
    bgr_for,
    format_label,
    hex_for,
    is_boots,
    is_compliance,
    is_gloves,
    is_goggles,
    is_helmet,
    is_person,
    is_vest,
    is_violation,
    normalize,
)
from src.core.model_manager import available_devices, best_device, device_label, resolve_model_path
from src.core.ppe_associator import WorkerStatus, associate_ppe_to_workers
from src.storage.evidence import EvidenceManager
from src.video.pipeline import TelemetryState
from src.video.renderer import OverlayRenderer


class TestPPEPlatform(unittest.TestCase):

    def test_class_semantics(self):
        self.assertEqual(normalize("NO_HELMET "), "no-helmet")
        self.assertTrue(is_violation("no-helmet"))
        self.assertTrue(is_violation("no-vest"))
        self.assertFalse(is_violation("helmet"))

        self.assertTrue(is_compliance("helmet"))
        self.assertTrue(is_compliance("hard-hat"))
        self.assertTrue(is_compliance("vest"))
        self.assertFalse(is_compliance("no-vest"))

        self.assertTrue(is_person("person"))
        self.assertTrue(is_person("worker"))
        self.assertFalse(is_person("helmet"))

        self.assertTrue(is_helmet("hard-hat"))
        self.assertTrue(is_vest("safety-vest"))
        self.assertTrue(is_boots("safety-boots"))
        self.assertTrue(is_gloves("gloves"))
        self.assertTrue(is_goggles("goggles"))
        self.assertTrue(is_violation("no-gloves"))
        self.assertTrue(is_violation("no-goggle"))

        self.assertEqual(bgr_for("no-helmet"), BGR_BAD)
        self.assertEqual(bgr_for("helmet"), BGR_OK)
        from src.config.settings import THEME_LIGHT
        self.assertEqual(hex_for("no-helmet", THEME_DARK), THEME_DARK["bad"])
        self.assertEqual(hex_for("no-helmet"), THEME_LIGHT["bad"])
        self.assertEqual(format_label("no-helmet"), "No Helmet")
        # Regression: 'officer' should not be detected as violation
        self.assertFalse(is_violation("officer"))

    def test_model_manager_devices(self):
        devices = available_devices()
        self.assertIn("cpu", devices)
        best = best_device()
        self.assertIsInstance(best, str)
        lbl = device_label(best)
        self.assertTrue(len(lbl) > 0)

        path, is_fallback = resolve_model_path()
        self.assertIsInstance(path, str)
        self.assertIsInstance(is_fallback, bool)

    def test_ppe_worker_association(self):
        mock_detections = [
            {"label": "person", "x1": 100, "y1": 100, "x2": 300, "y2": 600, "confidence": 0.95, "violation": False, "display_label": "Person"},
            {"label": "helmet", "x1": 150, "y1": 110, "x2": 250, "y2": 200, "confidence": 0.91, "violation": False, "display_label": "Helmet"},
            {"label": "no-vest", "x1": 120, "y1": 250, "x2": 280, "y2": 450, "confidence": 0.88, "violation": True, "display_label": "No Vest"},
        ]
        workers = associate_ppe_to_workers(mock_detections)
        self.assertEqual(len(workers), 1)
        w = workers[0]
        self.assertEqual(w.worker_id, 1)
        self.assertEqual(w.helmet_status, "COMPLIANT")
        self.assertEqual(w.vest_status, "VIOLATION")
        self.assertTrue(w.has_active_violation)

    def test_renderer_hud(self):
        renderer = OverlayRenderer()
        dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        boxes = np.array([[50, 50, 200, 200]], dtype=np.float32)
        scores = np.array([0.92], dtype=np.float32)
        labels = ["helmet"]

        out = renderer.draw_detections(dummy_frame.copy(), boxes, labels, scores)
        self.assertEqual(out.shape, dummy_frame.shape)

        worker = WorkerStatus(worker_id=1, box=(50, 50, 200, 400), helmet_status="COMPLIANT", vest_status="COMPLIANT")
        out = renderer.draw_worker_badges(out, [worker])
        self.assertEqual(out.shape, dummy_frame.shape)

        out = renderer.draw_telemetry_hud(out, fps=28.5, violations_count=0, workers_count=1, show_hud=True)
        self.assertEqual(out.shape, dummy_frame.shape)

    def test_evidence_storage_and_export(self):
        mgr = EvidenceManager(storage_dir=PROJECT_ROOT / "data" / "test_evidence")
        dummy_frame = np.zeros((240, 320, 3), dtype=np.uint8)

        rec = mgr.save_snapshot(dummy_frame, ["no-helmet"])
        self.assertIsNotNone(rec)
        self.assertIn("jpeg", rec)
        self.assertTrue(len(rec["jpeg"]) > 0)

        zip_bytes = mgr.create_zip_archive([rec])
        self.assertTrue(len(zip_bytes) > 0)

        csv_b, json_b = mgr.generate_report_payload(
            total_frames=100,
            fps=30.0,
            model_name="test_model",
            counts={"helmet": 5, "no-helmet": 1},
            detections=[{"label": "no-helmet", "confidence": 0.9}],
            events=[{"ts": 12345.0, "type": "VIOLATION"}],
        )
        self.assertIn(b"no-helmet", csv_b)
        self.assertIn(b"test_model", json_b)

    def test_telemetry_state_publish(self):
        state = TelemetryState()
        state.publish(
            counts={"person": 2, "helmet": 1, "no-helmet": 1},
            detections=[{"label": "no-helmet", "violation": True}, {"label": "helmet", "violation": False}],
            workers=[],
            fps=29.4,
            inference_ms=15.2,
            violations_count=1,
        )
        ui_snap = state.snapshot_ui()
        self.assertEqual(ui_snap["total_frames"], 1)
        self.assertEqual(ui_snap["fps"], 29.4)

        df = state.get_history_df()
        self.assertFalse(df.empty)
        self.assertIn("Workers", df.columns)
        self.assertIn("Helmets", df.columns)
        self.assertIn("Violations", df.columns)

    def test_demo_feed_and_numpy_pipeline(self):
        from src.video.demo_feed import DemoShopfloorFeed
        from src.video.pipeline import VideoPipeline

        feed = DemoShopfloorFeed(width=640, height=360)
        frame = feed.get_frame()
        self.assertEqual(frame.shape, (360, 640, 3))

        state = TelemetryState()
        pipeline = VideoPipeline(model=None, state=state)
        out = pipeline.process_numpy_frame(frame)
        self.assertEqual(out.shape, (360, 640, 3))

    def test_missing_model_clears_stale_observations(self):
        """A model outage must not leave an earlier detection visible to operators."""
        from src.video.pipeline import VideoPipeline

        state = TelemetryState()
        state.publish(
            counts={"person": 1},
            detections=[{"label": "person", "violation": False}],
            workers=[],
            fps=24.0,
            inference_ms=40.0,
            violations_count=0,
        )
        pipeline = VideoPipeline(model=None, state=state)

        output = pipeline.process_numpy_frame(np.zeros((24, 24, 3), dtype=np.uint8))
        snapshot = state.snapshot_ui()

        self.assertEqual(output.shape, (24, 24, 3))
        self.assertEqual(snapshot["detections"], [])
        self.assertEqual(snapshot["workers"], [])
        self.assertEqual(snapshot["counts"], {})
        self.assertIn("No model is loaded", snapshot["last_error"])

    def test_zero_ppe_worker_not_compliant(self):
        """Worker with zero detected PPE (all UNKNOWN) must NOT be compliant."""
        w = WorkerStatus(worker_id=1, box=(100, 100, 300, 600))
        self.assertFalse(w.is_compliant)
        self.assertFalse(w.has_active_violation)
        self.assertEqual(w.status, "UNSAFE")

        # Worker with helmet only -> compliant
        w_helmet = WorkerStatus(worker_id=2, box=(100, 100, 300, 600), helmet_status="COMPLIANT")
        self.assertTrue(w_helmet.is_compliant)
        self.assertEqual(w_helmet.status, "SAFE")

        # Worker with violation -> not compliant
        w_viol = WorkerStatus(worker_id=3, box=(100, 100, 300, 600), helmet_status="VIOLATION")
        self.assertFalse(w_viol.is_compliant)
        self.assertTrue(w_viol.has_active_violation)
        self.assertEqual(w_viol.status, "UNSAFE")

    def test_multi_worker_safety_metrics(self):
        """Test multi-worker scenario: Worker A compliant, Worker B violation."""
        detections = [
            # Worker A (compliant: helmet + vest)
            {"label": "person", "x1": 50, "y1": 100, "x2": 250, "y2": 600, "confidence": 0.95, "violation": False, "display_label": "Person"},
            {"label": "helmet", "x1": 100, "y1": 110, "x2": 200, "y2": 190, "confidence": 0.92, "violation": False, "display_label": "Helmet"},
            {"label": "vest", "x1": 80, "y1": 220, "x2": 220, "y2": 450, "confidence": 0.89, "violation": False, "display_label": "Vest"},
            # Worker B (violation: no-helmet + vest)
            {"label": "person", "x1": 400, "y1": 100, "x2": 600, "y2": 600, "confidence": 0.94, "violation": False, "display_label": "Person"},
            {"label": "no-helmet", "x1": 450, "y1": 110, "x2": 550, "y2": 190, "confidence": 0.90, "violation": True, "display_label": "No Helmet"},
            {"label": "vest", "x1": 430, "y1": 220, "x2": 570, "y2": 450, "confidence": 0.88, "violation": False, "display_label": "Vest"},
        ]
        workers = associate_ppe_to_workers(detections)
        self.assertEqual(len(workers), 2)

        total_w = len(workers)
        viol_w = sum(1 for w in workers if w.has_active_violation)
        safe_w = sum(1 for w in workers if w.is_compliant)

        self.assertEqual(total_w, 2)
        self.assertEqual(viol_w, 1)
        self.assertEqual(safe_w, 1)
        score = (safe_w / total_w) * 100.0
        self.assertEqual(score, 50.0)

    def test_boots_spatial_classification(self):
        """Boots detected at chest height must be classified as boots, not vest."""
        detections = [
            {"label": "person", "x1": 100, "y1": 100, "x2": 300, "y2": 600, "confidence": 0.95, "violation": False, "display_label": "Person"},
            # Boot at y=250-350 (chest zone rel_y=0.3-0.5)
            {"label": "boots", "x1": 150, "y1": 250, "x2": 250, "y2": 350, "confidence": 0.91, "violation": False, "display_label": "Boots"},
        ]
        workers = associate_ppe_to_workers(detections)
        self.assertEqual(len(workers), 1)
        w = workers[0]
        # Must be classified as boots, NOT vest!
        self.assertEqual(w.boots_status, "COMPLIANT")
        self.assertEqual(w.vest_status, "UNKNOWN")

    def test_state_machine_violation_update(self):
        """Test that state machine generates VIOLATION_UPDATE when new violation categories appear."""
        state = TelemetryState()
        # 2 frames of violation to confirm
        state.publish(
            counts={"person": 1, "no-helmet": 1},
            detections=[{"label": "no-helmet", "violation": True}],
            workers=[],
            fps=30.0,
            inference_ms=10.0,
            violations_count=1,
        )
        state.publish(
            counts={"person": 1, "no-helmet": 1},
            detections=[{"label": "no-helmet", "violation": True}],
            workers=[],
            fps=30.0,
            inference_ms=10.0,
            violations_count=1,
        )
        self.assertTrue(state.violating)
        events = state.get_events()
        self.assertTrue(any(e["type"] == "VIOLATION" for e in events))

        # Now new violation appears: no-vest
        state.publish(
            counts={"person": 1, "no-helmet": 1, "no-vest": 1},
            detections=[{"label": "no-helmet", "violation": True}, {"label": "no-vest", "violation": True}],
            workers=[],
            fps=30.0,
            inference_ms=10.0,
            violations_count=2,
        )
        events = state.get_events()
        self.assertTrue(any(e["type"] == "VIOLATION_UPDATE" for e in events))

    def test_worker_tracker_and_aggregated_labels(self):
        """Test persistent WorkerTracker across frames and multi-violation aggregation."""
        from src.core.ppe_associator import WorkerTracker

        tracker = WorkerTracker()
        now = 1000.0

        # Frame 1: Person 1 at (100, 100, 300, 600) with no-helmet and no-vest
        dets_frame1 = [
            {"label": "person", "x1": 100, "y1": 100, "x2": 300, "y2": 600, "confidence": 0.95, "violation": False, "display_label": "Person"},
            {"label": "no-helmet", "x1": 140, "y1": 110, "x2": 260, "y2": 190, "confidence": 0.90, "violation": True, "display_label": "no helmet"},
            {"label": "no-vest", "x1": 130, "y1": 220, "x2": 270, "y2": 450, "confidence": 0.88, "violation": True, "display_label": "no vest"},
        ]
        workers1 = associate_ppe_to_workers(dets_frame1, tracker=tracker, timestamp=now)
        self.assertEqual(len(workers1), 1)
        w1 = workers1[0]
        self.assertEqual(w1.worker_id, 1)
        self.assertIn("no helmet", w1.violations)
        self.assertIn("no vest", w1.violations)

        # Check aggregated label format
        viols_list = [v.replace("_", " ").lower() for v in w1.violations]
        top_label = f"Person {w1.worker_id} - {', '.join(viols_list)}"
        self.assertEqual(top_label, "Person 1 - no helmet, no vest")

        # Frame 2 (2 seconds later): Person 1 moves slightly, Person 2 enters with no goggles and no gloves
        now += 2.0
        dets_frame2 = [
            # Person 1 (shifted by 5px)
            {"label": "person", "x1": 105, "y1": 100, "x2": 305, "y2": 600, "confidence": 0.95, "violation": False, "display_label": "Person"},
            {"label": "no-helmet", "x1": 145, "y1": 110, "x2": 265, "y2": 190, "confidence": 0.90, "violation": True, "display_label": "no helmet"},
            {"label": "no-vest", "x1": 135, "y1": 220, "x2": 275, "y2": 450, "confidence": 0.88, "violation": True, "display_label": "no vest"},
            # Person 2
            {"label": "person", "x1": 500, "y1": 100, "x2": 700, "y2": 600, "confidence": 0.94, "violation": False, "display_label": "Person"},
            {"label": "no-goggles", "x1": 540, "y1": 130, "x2": 660, "y2": 170, "confidence": 0.85, "violation": True, "display_label": "no goggles"},
            {"label": "no-gloves", "x1": 520, "y1": 350, "x2": 580, "y2": 430, "confidence": 0.82, "violation": True, "display_label": "no gloves"},
        ]
        workers2 = associate_ppe_to_workers(dets_frame2, tracker=tracker, timestamp=now)
        self.assertEqual(len(workers2), 2)
        # Person 1 retains ID 1 and accumulated dwell time (2.0s)
        self.assertEqual(workers2[0].worker_id, 1)
        self.assertEqual(workers2[0].dwell_seconds, 2.0)
        # Person 2 gets ID 2
        self.assertEqual(workers2[1].worker_id, 2)
        self.assertEqual(workers2[1].dwell_seconds, 0.0)

        # Labels format
        p1_viols = [v.replace("_", " ").lower() for v in workers2[0].violations]
        p1_label = f"Person {workers2[0].worker_id} - {', '.join(p1_viols)}"
        self.assertEqual(p1_label, "Person 1 - no helmet, no vest")

        p2_viols = [v.replace("_", " ").lower() for v in workers2[1].violations]
        p2_label = f"Person {workers2[1].worker_id} - {', '.join(p2_viols)}"
        self.assertEqual(p2_label, "Person 2 - no goggles, no gloves")

    def test_opencv_camera_manager_simulation_fallback(self):
        """Test OpenCVCameraManager falls back to shopfloor simulation when hardware camera is absent."""
        import time
        from unittest.mock import patch

        from src.video.camera import OpenCVCameraManager

        mgr = OpenCVCameraManager.get_instance()
        self.assertIsNotNone(mgr)
        mgr.stop()

        # Mock _open_camera to simulate absent hardware camera
        with patch.object(mgr, "_open_camera", return_value=None):
            started = mgr.start(device_index=0, allow_simulation_fallback=True)
            self.assertTrue(started)

            # Wait briefly for capture thread to spin up and produce a frame
            time.sleep(0.06)

            self.assertTrue(mgr.is_running)
            self.assertTrue(mgr.is_simulated)
            latest_frame = mgr.get_latest_frame()
            self.assertIsNotNone(latest_frame)
            self.assertEqual(latest_frame.shape[0], 720)
            self.assertEqual(latest_frame.shape[1], 1280)

            # Stop manager
            mgr.stop()
            self.assertFalse(mgr.is_running)
            self.assertFalse(mgr.is_simulated)

    def test_opencv_camera_manager_no_fallback_records_error(self):
        """Test OpenCVCameraManager records a clear diagnostic error when hardware camera fails and fallback disabled."""
        import time
        from unittest.mock import patch

        from src.video.camera import OpenCVCameraManager

        mgr = OpenCVCameraManager.get_instance()
        mgr.stop()

        with patch.object(mgr, "_open_camera", return_value=None):
            mgr.start(device_index=0, allow_simulation_fallback=False)
            time.sleep(0.05)

            # Should not be running and should have an error string explaining hardware camera is unavailable
            self.assertFalse(mgr.is_running)
            self.assertFalse(mgr.is_simulated)
            self.assertIn("could not be opened by OpenCV", mgr.last_error)

            mgr.stop()


if __name__ == "__main__":
    unittest.main()

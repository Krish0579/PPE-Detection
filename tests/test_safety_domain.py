"""Worker-tracking identity and temporal-debounce behaviour.

Complements ``test_safesight_domain.py`` (which covers the incident, zone,
and integrity boundaries) by testing the tracker logic that decides whether a
worker's compliance status may be trusted frame to frame.
"""

from __future__ import annotations

import unittest

import numpy as np

from src.core.ppe_associator import WorkerStatus
from src.core.worker_tracker import WorkerTracker


def _worker(**kwargs: object) -> WorkerStatus:
    return WorkerStatus(worker_id=1, box=(0, 0, 10, 20), **kwargs)


def _tracked(**track_data: object) -> WorkerTracker:
    tracker = WorkerTracker()
    tracker.tracks[1] = track_data
    return tracker


class TestTemporalDebounce(unittest.TestCase):
    """A single-frame detector miss must not flip a worker's compliance status.

    Without this, a compliant worker generates a violation incident every time
    the detector blinks — which floods the evidence store with false alarms.
    """

    def test_untracked_worker_is_a_no_op(self) -> None:
        WorkerTracker().debounce_compliance(_worker(helmet_status="VIOLATION"))

    def test_single_frame_miss_stays_compliant(self) -> None:
        tracker = _tracked(gear_status={"helmet": "COMPLIANT"}, missing_streaks={"helmet": 0})
        worker = _worker(helmet_status="VIOLATION", violations=["no helmet"])

        tracker.debounce_compliance(worker)

        self.assertEqual(worker.helmet_status, "COMPLIANT")
        self.assertNotIn("no helmet", worker.violations)
        self.assertIn("Helmet", worker.compliances)

    def test_second_consecutive_miss_flags_violation(self) -> None:
        tracker = _tracked(gear_status={"helmet": "COMPLIANT"}, missing_streaks={"helmet": 1})
        worker = _worker(helmet_status="VIOLATION", violations=[])

        tracker.debounce_compliance(worker)

        self.assertEqual(worker.helmet_status, "VIOLATION")

    def test_explicit_violation_class_bypasses_debounce(self) -> None:
        """An explicit detector class is a confirmed breach, not a blink."""
        tracker = _tracked(gear_status={"helmet": "COMPLIANT"}, missing_streaks={"helmet": 0})
        worker = _worker(helmet_status="VIOLATION", explicit_violations=["helmet"])

        tracker.debounce_compliance(worker)

        self.assertEqual(worker.helmet_status, "VIOLATION")

    def test_compliant_frame_resets_streak(self) -> None:
        tracker = _tracked(gear_status={"helmet": "VIOLATION"}, missing_streaks={"helmet": 3})
        worker = _worker(helmet_status="COMPLIANT")

        tracker.debounce_compliance(worker)

        self.assertEqual(worker.helmet_status, "COMPLIANT")

    def test_track_without_prior_state_initialises(self) -> None:
        tracker = _tracked()
        worker = _worker(helmet_status="COMPLIANT")

        tracker.debounce_compliance(worker)

        self.assertIn("helmet", tracker.tracks[1]["gear_status"])


class TestFeatureSimilarity(unittest.TestCase):
    def test_absent_features_score_zero(self) -> None:
        self.assertEqual(WorkerTracker().compute_similarity(None, None), 0.0)

    def test_identical_features_score_near_one(self) -> None:
        tracker = WorkerTracker()
        feature = np.random.default_rng(0).random(64).astype("float32")
        self.assertGreater(tracker.compute_similarity(feature, feature), 0.9)

    def test_distinct_features_score_lower(self) -> None:
        tracker = WorkerTracker()
        rng = np.random.default_rng(7)
        first = rng.random(64).astype("float32")
        second = rng.random(64).astype("float32")
        self.assertLess(tracker.compute_similarity(first, second), 0.9)

    def test_score_is_bounded(self) -> None:
        tracker = WorkerTracker()
        rng = np.random.default_rng(3)
        for _ in range(5):
            score = tracker.compute_similarity(rng.random(32).astype("float32"), rng.random(32).astype("float32"))
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)

    def test_extract_feature_without_frame_returns_none(self) -> None:
        self.assertIsNone(WorkerTracker().extract_feature(None, (0, 0, 10, 10)))

    def test_extract_feature_from_image(self) -> None:
        frame = np.random.default_rng(1).integers(0, 255, (48, 48, 3), dtype=np.uint8)
        feature = WorkerTracker().extract_feature(frame, (4, 4, 44, 44))
        self.assertIsNotNone(feature)

    def test_degenerate_box_does_not_crash(self) -> None:
        frame = np.zeros((48, 48, 3), dtype=np.uint8)
        WorkerTracker().extract_feature(frame, (10, 10, 10, 10))


class TestTrackAssociation(unittest.TestCase):
    def test_no_detections_returns_no_results(self) -> None:
        self.assertEqual(WorkerTracker().update([], now=0.0), [])

    def test_new_detection_creates_a_track(self) -> None:
        tracker = WorkerTracker()
        results = tracker.update([(0, 0, 20, 40)], now=1.0)

        self.assertEqual(len(results), 1)
        self.assertEqual(len(tracker.tracks), 1)

    def test_identity_is_preserved_across_frames(self) -> None:
        """Re-identification across frames is what keeps evidence per-person."""
        tracker = WorkerTracker()
        first = tracker.update([(0, 0, 20, 40)], now=1.0)[0][0]
        second = tracker.update([(2, 1, 22, 41)], now=2.0)[0][0]
        self.assertEqual(first, second)

    def test_dwell_time_accumulates(self) -> None:
        tracker = WorkerTracker()
        tracker.update([(0, 0, 20, 40)], now=1.0)
        results = tracker.update([(0, 0, 20, 40)], now=6.0)
        self.assertGreater(results[0][1], 0.0)

    def test_lost_track_is_archived_to_gallery(self) -> None:
        tracker = WorkerTracker(max_lost=1)
        tracker.update([(0, 0, 20, 40)], now=1.0)

        for step in range(2, 8):
            tracker.update([], now=float(step))

        self.assertEqual(len(tracker.tracks), 0)
        self.assertEqual(len(tracker.gallery), 1)
        self.assertIn("dwell_accumulated", next(iter(tracker.gallery.values())))


if __name__ == "__main__":
    unittest.main()

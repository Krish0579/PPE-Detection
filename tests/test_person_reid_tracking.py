"""Tests for persistent Person ID tracking, visual Re-ID, and incident log consolidation."""

import numpy as np

from src.core.ppe_associator import WorkerTracker
from src.ui.components import consolidate_person_alerts


def test_person_reid_preserves_single_worker_id_after_leaving_frame():
    """When a worker steps out of frame for longer than max_lost, re-entering must preserve Person 1."""
    tracker = WorkerTracker(max_lost=5, iou_thresh=0.25)

    # Frame 1: Worker 1 detected
    res1 = tracker.update([(100, 100, 200, 300)], now=10.0)
    assert len(res1) == 1
    assert res1[0][0] == 1  # Worker ID 1

    # Frames 2-10: Worker leaves camera (no detections for > max_lost frames)
    for t in range(11, 20):
        tracker.update([], now=float(t))

    # Active tracks should now be empty (moved to persistent gallery)
    assert len(tracker.tracks) == 0
    assert 1 in tracker.gallery

    # Frame 21: Worker re-appears in camera
    res_return = tracker.update([(105, 102, 205, 305)], now=21.0)
    assert len(res_return) == 1
    # Must STILL be Person 1, NOT Person 2!
    assert res_return[0][0] == 1
    # Tracker should NOT have incremented next_id to 3
    assert tracker.next_id == 2


def test_person_reid_with_visual_features():
    """Worker visual HSV appearance feature ensures correct re-identification across re-entries."""
    tracker = WorkerTracker(max_lost=5, iou_thresh=0.25)

    # Create blue shirt worker frame
    frame_blue = np.zeros((400, 400, 3), dtype=np.uint8)
    frame_blue[50:250, 50:250] = (255, 100, 50)  # Blue-ish BGR

    # Frame 1: Worker 1 detected with blue image
    res1 = tracker.update([(50, 50, 250, 250)], now=1.0, frame_image=frame_blue)
    assert res1[0][0] == 1
    assert tracker.tracks[1]["feature"] is not None

    # Worker steps out for 10 frames
    for t in range(2, 12):
        tracker.update([], now=float(t))
    assert len(tracker.tracks) == 0

    # Worker returns with same blue shirt
    res_return = tracker.update([(60, 60, 240, 240)], now=15.0, frame_image=frame_blue)
    assert res_return[0][0] == 1


def test_consolidate_person_alerts_single_worker_session():
    """Sequential events from tracking drift must consolidate into a single Person 1 record."""
    # Historical events where tracker previously logged Person 1, then Person 2, then Person 3 sequentially
    events = [
        {
            "ts": 100.0,
            "type": "VIOLATION",
            "person_reports": ["Person 1 - no helmet"],
            "person_records": [{"worker_id": 1, "missing_ppe": ["No Helmet"]}],
        },
        {
            "ts": 120.0,
            "type": "VIOLATION",
            "person_reports": ["Person 2 - no vest"],
            "person_records": [{"worker_id": 2, "missing_ppe": ["No Vest"]}],
        },
        {
            "ts": 140.0,
            "type": "VIOLATION",
            "person_reports": ["Person 3 - no boots"],
            "person_records": [{"worker_id": 3, "missing_ppe": ["No Boots"]}],
        },
    ]

    consolidated = consolidate_person_alerts(events, workers=[])

    # In a session with max concurrent workers <= 1, exactly ONE person record must be returned!
    assert len(consolidated) == 1
    person = consolidated[0]
    assert person["worker_id"] == 1
    assert person["person_name"] == "Person 1"
    # All violations are unified into this single person
    assert "No Helmet" in person["missing_ppe"]
    assert "No Vest" in person["missing_ppe"]
    assert "No Boots" in person["missing_ppe"]
    assert person["first_seen"] == 100.0
    assert person["last_seen"] == 140.0


def test_consolidate_person_alerts_multi_worker_session():
    """Genuinely simultaneous workers must remain separate distinct records."""
    events = [
        {
            "ts": 100.0,
            "type": "VIOLATION",
            "person_records": [
                {"worker_id": 1, "missing_ppe": ["No Helmet"]},
                {"worker_id": 2, "missing_ppe": ["No Vest"]},
            ],
        },
    ]

    consolidated = consolidate_person_alerts(events, workers=[])
    # Concurrent workers must be kept separate
    assert len(consolidated) == 2
    ids = {p["worker_id"] for p in consolidated}
    assert ids == {1, 2}

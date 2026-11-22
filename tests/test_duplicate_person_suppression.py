"""Regression tests for the one-person-showing-as-two defect.

Operator report: the Evidence Log showed two personnel cards for a single
worker. Root cause was that detector NMS runs per class, so one human could
survive as two boxes (full-body plus a tighter second-pass crop), each becoming
its own track and its own person card.

These tests pin the two properties that matter:
1. one human is never split into two identities;
2. genuinely distinct people are never merged, and box order is untouched.
"""

from __future__ import annotations

import unittest

from src.core.ppe_associator import WorkerTracker
from src.core.worker_tracker import suppress_duplicate_person_boxes
from src.ui.components.alerts import consolidate_person_alerts


class Wk:
    """Minimal worker stand-in matching the attributes the alert layer reads."""

    def __init__(self, worker_id: int, helmet_status: str = "VIOLATION") -> None:
        self.worker_id = worker_id
        self.zone = "Assembly Line A"
        self.dwell_seconds = 4.0
        self.helmet_status = helmet_status
        self.vest_status = "COMPLIANT"
        self.boots_status = "COMPLIANT"
        self.gloves_status = "COMPLIANT"
        self.goggles_status = "COMPLIANT"
        self.is_restricted_zone = False
        self.violations = ["no helmet"] if helmet_status == "VIOLATION" else []
        self.required_ppe = None
        self.has_active_violation = helmet_status == "VIOLATION"


class TestDuplicateBoxSuppression(unittest.TestCase):
    def test_nested_duplicate_collapses_to_one(self) -> None:
        """A tighter crop of the same body must not survive as a second person."""
        result = suppress_duplicate_person_boxes([(100, 100, 300, 500), (110, 110, 290, 480)])
        self.assertEqual(result, [(100, 100, 300, 500)])

    def test_identical_boxes_collapse(self) -> None:
        self.assertEqual(suppress_duplicate_person_boxes([(0, 0, 100, 300), (0, 0, 100, 300)]), [(0, 0, 100, 300)])

    def test_larger_box_wins(self) -> None:
        """The full-body box drives better tracking and dwell time."""
        result = suppress_duplicate_person_boxes([(110, 110, 190, 290), (100, 100, 205, 300)])
        self.assertEqual(result, [(100, 100, 205, 300)])

    def test_two_real_people_are_preserved(self) -> None:
        boxes = [(105, 100, 205, 300), (405, 100, 505, 300)]
        self.assertEqual(suppress_duplicate_person_boxes(boxes), boxes)

    def test_adjacent_people_are_not_merged(self) -> None:
        """Workers standing shoulder to shoulder are separate people."""
        boxes = [(0, 0, 100, 300), (110, 0, 210, 300)]
        self.assertEqual(suppress_duplicate_person_boxes(boxes), boxes)

    def test_order_is_preserved(self) -> None:
        """Callers keep results index-aligned with the boxes they passed in."""
        forward = [(105, 100, 205, 300), (405, 100, 505, 300)]
        reverse = [(405, 100, 505, 300), (105, 100, 205, 300)]
        self.assertEqual(suppress_duplicate_person_boxes(forward), forward)
        self.assertEqual(suppress_duplicate_person_boxes(reverse), reverse)

    def test_order_preserved_while_dropping_a_duplicate(self) -> None:
        result = suppress_duplicate_person_boxes([(405, 100, 505, 300), (105, 100, 205, 300), (110, 110, 190, 290)])
        self.assertEqual(result, [(405, 100, 505, 300), (105, 100, 205, 300)])

    def test_single_and_empty_inputs_pass_through(self) -> None:
        self.assertEqual(suppress_duplicate_person_boxes([]), [])
        self.assertEqual(suppress_duplicate_person_boxes([(0, 0, 10, 10)]), [(0, 0, 10, 10)])

    def test_degenerate_zero_area_box_is_dropped(self) -> None:
        self.assertEqual(suppress_duplicate_person_boxes([(10, 10, 10, 10), (0, 0, 50, 50)]), [(0, 0, 50, 50)])

    def test_input_is_not_mutated(self) -> None:
        boxes = [(100, 100, 300, 500), (110, 110, 290, 480)]
        snapshot = list(boxes)
        suppress_duplicate_person_boxes(boxes)
        self.assertEqual(boxes, snapshot)


class TestTrackerIdentityStability(unittest.TestCase):
    def test_one_human_with_duplicate_box_keeps_one_identity(self) -> None:
        tracker = WorkerTracker()
        tracker.update([(100, 100, 300, 500)], now=1.0)
        tracker.update([(100, 100, 300, 500), (110, 110, 290, 480)], now=2.0)

        self.assertEqual(len(tracker.tracks), 1)
        self.assertEqual(sorted(tracker.tracks), [1])

    def test_two_humans_keep_two_identities(self) -> None:
        tracker = WorkerTracker()
        tracker.update([(105, 100, 205, 300), (405, 100, 505, 300)], now=1.0)
        tracker.update([(105, 100, 205, 300), (405, 100, 505, 300)], now=2.0)

        self.assertEqual(len(tracker.tracks), 2)

    def test_identity_survives_a_duplicate_frame(self) -> None:
        """A duplicate detection must not renumber the existing worker."""
        tracker = WorkerTracker()
        first = tracker.update([(100, 100, 300, 500)], now=1.0)[0][0]
        after = tracker.update([(100, 100, 300, 500), (108, 108, 296, 486)], now=2.0)
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0][0], first)


class TestEvidenceLogCardCount(unittest.TestCase):
    """End-to-end: one worker must yield exactly one personnel card."""

    @staticmethod
    def _event(worker_ids: list[int], ts: float = 100.0) -> dict:
        return {
            "ts": ts,
            "type": "VIOLATION",
            "violations": len(worker_ids),
            "person_reports": [f"Person {i} - no helmet" for i in worker_ids],
            "person_records": [
                {"worker_id": i, "missing_ppe": ["No Helmet"], "zone": "Assembly Line A", "dwell_seconds": 4.0}
                for i in worker_ids
            ],
            "labels": [f"Person {i} - no helmet" for i in worker_ids],
        }

    def test_one_worker_yields_one_card(self) -> None:
        cards = consolidate_person_alerts([self._event([1])], workers=[Wk(1)])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["person_name"], "Person 1")

    def test_two_workers_yield_two_cards(self) -> None:
        cards = consolidate_person_alerts([self._event([1, 2])], workers=[Wk(1), Wk(2)])
        self.assertEqual(len(cards), 2)
        self.assertEqual([c["person_name"] for c in cards], ["Person 1", "Person 2"])

    def test_generic_label_is_not_misattributed_in_a_crowd(self) -> None:
        """An identity-less label must not be pinned onto Person 1.

        Worker 2 is the only one actually violating, so the single card must
        name Person 2. Previously the bare label was attributed to Person 1,
        falsely incriminating the wrong individual.
        """
        event = {
            "ts": 100.0,
            "type": "VIOLATION",
            "violations": 1,
            "person_reports": [],
            "person_records": [],
            "labels": ["no helmet"],
        }
        cards = consolidate_person_alerts([event], workers=[Wk(1, helmet_status="COMPLIANT"), Wk(2)])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["person_name"], "Person 2")

    def test_generic_label_creates_no_card_for_an_absent_person(self) -> None:
        """With no violating worker and no identity, nothing may be invented."""
        event = {
            "ts": 100.0,
            "type": "VIOLATION",
            "violations": 1,
            "person_reports": [],
            "person_records": [],
            "labels": ["no helmet"],
        }
        cards = consolidate_person_alerts([event], workers=[Wk(1, helmet_status="COMPLIANT"), Wk(2, "COMPLIANT")])
        self.assertEqual(cards, [])

    def test_generic_label_is_kept_for_a_lone_worker(self) -> None:
        """With one person in scope the label is unambiguous, so keep it."""
        event = {
            "ts": 100.0,
            "type": "VIOLATION",
            "violations": 1,
            "person_reports": [],
            "person_records": [],
            "labels": ["no helmet"],
        }
        cards = consolidate_person_alerts([event], workers=[Wk(1)])
        self.assertEqual(len(cards), 1)
        self.assertIn("No Helmet", cards[0]["missing_ppe"])


if __name__ == "__main__":
    unittest.main()

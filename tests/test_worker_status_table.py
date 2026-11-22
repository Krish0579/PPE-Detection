"""Tests for the per-worker PPE status table.

``build_workers_status_dataframe`` backs the on-screen compliance checklist on
three pages, so its wording is operator-facing and safety-relevant: a missing
helmet must not be able to render as anything but an explicit failure.
"""

from __future__ import annotations

import unittest

from src.core.ppe_associator import WorkerStatus
from src.ui.components.workers import build_workers_status_dataframe


def _worker(worker_id: int = 1, **kwargs: object) -> WorkerStatus:
    return WorkerStatus(worker_id=worker_id, box=(0, 0, 10, 20), **kwargs)


class TestWorkerStatusTable(unittest.TestCase):
    def test_compliant_worker_reports_every_category_worn(self) -> None:
        worker = _worker(
            helmet_status="COMPLIANT",
            vest_status="COMPLIANT",
            boots_status="COMPLIANT",
            gloves_status="COMPLIANT",
            goggles_status="COMPLIANT",
        )
        row = build_workers_status_dataframe([worker]).iloc[0]

        self.assertEqual(row["Status"], "✅ COMPLIANT")
        self.assertIn("Helmet Worn", row["⛑️ Helmet"])
        self.assertIn("Vest Worn", row["🦺 Vest"])
        self.assertIn("Boots Worn", row["🥾 Boots"])
        self.assertIn("Gloves Worn", row["🧤 Gloves"])
        self.assertIn("Goggles Worn", row["🥽 Goggles"])

    def test_missing_helmet_is_explicit(self) -> None:
        worker = _worker(
            helmet_status="VIOLATION",
            vest_status="COMPLIANT",
            violations=["no helmet"],
        )
        row = build_workers_status_dataframe([worker]).iloc[0]

        self.assertEqual(row["Status"], "❌ VIOLATION")
        self.assertIn("NO HELMET", row["⛑️ Helmet"])
        self.assertIn("no helmet", row["Active Violations"])

    def test_optional_ppe_is_marked_rather_than_failed(self) -> None:
        """PPE switched off in policy must not be reported as missing."""
        worker = _worker(
            helmet_status="UNKNOWN",
            vest_status="COMPLIANT",
            required_ppe={"helmet": False, "vest": True},
        )
        row = build_workers_status_dataframe([worker]).iloc[0]

        self.assertIn("Optional", row["⛑️ Helmet"])
        self.assertNotIn("NO HELMET", row["⛑️ Helmet"])

    def test_unobserved_ppe_is_not_reported_as_a_breach(self) -> None:
        """UNKNOWN status must not be rendered as a confirmed violation."""
        worker = _worker(helmet_status="UNKNOWN", vest_status="COMPLIANT")
        row = build_workers_status_dataframe([worker]).iloc[0]

        self.assertNotIn("NO HELMET", row["⛑️ Helmet"])

    def test_compliant_worker_lists_no_violations(self) -> None:
        worker = _worker(helmet_status="COMPLIANT", vest_status="COMPLIANT")
        row = build_workers_status_dataframe([worker]).iloc[0]

        self.assertIn("Compliant", row["Active Violations"])

    def test_empty_input_yields_empty_table_with_schema(self) -> None:
        frame = build_workers_status_dataframe([])
        self.assertTrue(frame.empty)
        # Columns must still exist so downstream st.dataframe renders headers.
        self.assertIn("⛑️ Helmet", frame.columns)
        self.assertIn("Active Violations", frame.columns)

    def test_worker_id_is_zero_padded(self) -> None:
        worker = _worker(worker_id=7, helmet_status="COMPLIANT")
        row = build_workers_status_dataframe([worker]).iloc[0]
        self.assertEqual(row["Personnel"], "Worker #07")

    def test_one_row_per_worker(self) -> None:
        workers = [
            _worker(worker_id=1, helmet_status="COMPLIANT"),
            _worker(worker_id=2, helmet_status="VIOLATION"),
        ]
        self.assertEqual(len(build_workers_status_dataframe(workers)), 2)


if __name__ == "__main__":
    unittest.main()

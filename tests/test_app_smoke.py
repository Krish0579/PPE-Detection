"""Smoke coverage for the Streamlit application shell."""
from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
NAVIGATION_ITEMS = (
    "Live operations",
    "Review footage",
    "Analyze image",
    "Incident evidence",
    "System policy",
)


class TestApplicationSmoke(unittest.TestCase):
    def test_all_workspace_pages_load_without_runtime_exceptions(self) -> None:
        """Every top-level workflow should render before a user uploads media."""
        for navigation_item in NAVIGATION_ITEMS:
            with self.subTest(navigation_item=navigation_item):
                app = AppTest.from_file(str(APP_PATH))
                app.session_state["workspace_navigation"] = navigation_item
                app.run(timeout=60)

                self.assertFalse(app.exception)

    def test_app_defaults_to_live_operations(self) -> None:
        app = AppTest.from_file(str(APP_PATH))
        app.run(timeout=60)

        self.assertFalse(app.exception)
        self.assertEqual(app.sidebar.radio[0].value, "Live operations")

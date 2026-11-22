"""Smoke coverage for the Streamlit application shell."""

from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.ui.navigation import NAV_SECTIONS
from src.ui.navigation import NAVIGATION_ITEMS as NAV_ITEMS

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"
NAVIGATION_ITEMS = tuple(item.key for item in NAV_ITEMS)
NAVIGATION_LABELS = tuple(item.label for item in NAV_ITEMS)


class TestApplicationSmoke(unittest.TestCase):
    def test_all_workspace_pages_load_without_runtime_exceptions(self) -> None:
        """Every top-level workflow should render before a user uploads media."""
        for navigation_item in NAVIGATION_ITEMS:
            with self.subTest(navigation_item=navigation_item):
                app = AppTest.from_file(str(APP_PATH))
                app.session_state["workspace_navigation"] = navigation_item
                app.run(timeout=60)

                self.assertFalse(app.exception)

    def test_app_defaults_to_command_center(self) -> None:
        """Operators should land on the situation overview, not a raw feed."""
        app = AppTest.from_file(str(APP_PATH))
        app.run(timeout=60)

        self.assertFalse(app.exception)
        self.assertEqual(app.sidebar.radio[0].value, "Overview")

    def test_nav_radio_exposes_every_page(self) -> None:
        """NAVIGATION_ITEMS must not drift from the app's navigation map."""
        app = AppTest.from_file(str(APP_PATH))
        app.run(timeout=60)

        self.assertFalse(app.exception)
        options = list(app.sidebar.radio[0].options)
        self.assertEqual(options, list(NAVIGATION_LABELS))

    def test_navigation_is_grouped_into_operator_sections(self) -> None:
        self.assertEqual([name for name, _items in NAV_SECTIONS], ["Monitor", "Review", "Configure"])
        grouped_keys = [item.key for _name, items in NAV_SECTIONS for item in items]
        self.assertEqual(grouped_keys, list(NAVIGATION_ITEMS))

    def test_no_hotkey_buttons_are_rendered(self) -> None:
        """Keyboard shortcuts were removed, so no hidden nav buttons should exist."""
        app = AppTest.from_file(str(APP_PATH), default_timeout=120)
        app.run()

        self.assertFalse(app.exception)
        keys = {getattr(el, "key", None) for el in app.button}
        self.assertFalse([k for k in keys if k and k.startswith("hk_")])
        self.assertFalse([k for k in keys if k and k.startswith("__hk")])

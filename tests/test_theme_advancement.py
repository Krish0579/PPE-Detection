"""Phase 5 regression tests: theme advancement, keyboard shortcuts, and UX upgrades.

Covers:
- X1: keyboard-shortcut handler restored (``render_keyboard_shortcuts_script``)
  with hidden hotkey buttons and input-safe/modifier-safe guards.
- X2: live dark/light theme switch — ``get_safesight_css`` honors the
  ``theme_mode`` session key; no hardcoded light-only colors remain in the
  dark stylesheet.
- X3: themed empty-state helper replaces flat cv2.putText placeholders.
- X5: responsive sidebar media queries for tablets/narrow windows.
- X7: ``prefers-reduced-motion`` support in the theme CSS.
"""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.ui.components import render_empty_state, render_keyboard_shortcuts_script
from src.ui.theme import get_safesight_css

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"


class TestThemeStylesheetAdvancement(unittest.TestCase):
    def test_dark_mode_uses_dark_tokens(self) -> None:
        css = get_safesight_css("dark")
        self.assertIn("#121b1e", css)  # dark bg token
        self.assertNotIn("#f7f9fa", css)  # light bg must not leak into dark mode

    def test_light_mode_unchanged(self) -> None:
        css = get_safesight_css("light")
        self.assertIn("#f7f9fa", css)
        self.assertNotIn("#121b1e", css)

    def test_nav_labels_are_theme_var_driven(self) -> None:
        # X2: the sidebar nav label color used to be hardcoded #475569 (light-only)
        for mode in ("light", "dark"):
            css = get_safesight_css(mode)
            self.assertNotIn("#475569", css, f"hardcoded nav label color leaked in {mode} mode")
            self.assertIn("var(--secondary)", css)

    def test_demo_banner_is_theme_var_driven(self) -> None:
        # X2: the demo banner gradient used a hardcoded light-only stop (#fff8e1)
        for mode in ("light", "dark"):
            css = get_safesight_css(mode)
            self.assertNotIn("#fff8e1", css, f"light-only banner gradient leaked in {mode} mode")
            self.assertIn(".demo-banner", css)

    def test_scrollbar_thumb_is_tokenized(self) -> None:
        for mode in ("light", "dark"):
            css = get_safesight_css(mode)
            self.assertIn("var(--scrollbar-thumb)", css)
        self.assertNotEqual(
            get_safesight_css("light"),
            get_safesight_css("dark"),
        )

    def test_baseweb_popovers_follow_theme(self) -> None:
        for mode in ("light", "dark"):
            css = get_safesight_css(mode)
            self.assertIn('[data-baseweb="popover"]', css)
            self.assertIn('div[role="listbox"]', css)

    def test_reduced_motion_css_present(self) -> None:
        # X7: entrance/pulse animations must respect prefers-reduced-motion
        for mode in ("light", "dark"):
            css = get_safesight_css(mode)
            self.assertIn("prefers-reduced-motion", css)

    def test_responsive_sidebar_media_queries(self) -> None:
        # X5: the pinned 320px sidebar must relax on tablets/narrow windows
        css = get_safesight_css("light")
        self.assertIn("@media (max-width: 1280px)", css)
        self.assertIn("@media (max-width: 900px)", css)
        self.assertIn("min-width: 272px", css)
        self.assertIn("min-width: 232px", css)


class TestKeyboardShortcuts(unittest.TestCase):
    def test_shortcut_script_handler_is_installed(self) -> None:
        source = inspect.getsource(render_keyboard_shortcuts_script)
        self.assertIn("keydown", source)
        self.assertIn("'INPUT'", source)
        self.assertIn("'TEXTAREA'", source)
        self.assertIn("'SELECT'", source)
        self.assertIn("ctrlKey", source)
        self.assertIn("metaKey", source)

    def test_shortcut_script_targets_hidden_hotkey_buttons(self) -> None:
        source = inspect.getsource(render_keyboard_shortcuts_script)
        self.assertIn("__hk_nav_", source)
        self.assertIn("__hk_cam", source)
        self.assertIn("__hk_help", source)

    def test_shortcut_script_binds_parent_document(self) -> None:
        # Keydown events inside component iframes never propagate, so the
        # handler must bind to the parent document where the operator types.
        source = inspect.getsource(render_keyboard_shortcuts_script)
        self.assertIn("window.parent", source)
        self.assertIn("top.document", source)

    def test_hotkey_buttons_drive_navigation_without_session_loss(self) -> None:
        app = AppTest.from_file(str(APP_PATH), default_timeout=120)
        app.run()
        self.assertFalse(app.exception)
        btn = app.button(key="hk_nav_2")
        self.assertIsNotNone(btn)

        # Click sets `_pending_nav` and triggers st.rerun(); the second run()
        # consumes the pending value before the radio widget is instantiated.
        btn.click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["workspace_navigation"], "Review footage")
        self.assertEqual(app.sidebar.radio[0].value, "Review footage")

    def test_help_dialog_opens_from_hotkey(self) -> None:
        app = AppTest.from_file(str(APP_PATH), default_timeout=120)
        app.run()
        self.assertFalse(app.exception)

        # Streamlit < 1.50 AppTest lacks `.dialog`; verify the button is
        # present and clicking it does not raise an exception (the @st.dialog
        # decorator opens the modal server-side).
        btn = app.button(key="hk_help")
        self.assertIsNotNone(btn)
        btn.click().run()
        self.assertFalse(app.exception)


class TestThemeToggle(unittest.TestCase):
    def test_theme_mode_session_default_is_light(self) -> None:
        app = AppTest.from_file(str(APP_PATH), default_timeout=120)
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["theme_mode"], "light")

    def test_dark_mode_toggle_switches_theme(self) -> None:
        app = AppTest.from_file(str(APP_PATH), default_timeout=120)
        app.run()
        self.assertFalse(app.exception)

        # Explicitly set the toggle value to True (dark) — bare `.run()` does
        # not flip the widget value; `.set_value(True)` drives the desired
        # state change through the app's `st.session_state["theme_mode"]` wiring.
        app.toggle(key="theme_mode_toggle").set_value(True).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["theme_mode"], "dark")


class TestThemedEmptyState(unittest.TestCase):
    def test_empty_state_uses_theme_variables(self) -> None:
        source = inspect.getsource(render_empty_state)
        self.assertIn("var(--panel)", source)
        self.assertIn("var(--line)", source)
        self.assertIn("var(--heading)", source)

    def test_empty_state_escapes_user_text(self) -> None:
        source = inspect.getsource(render_empty_state)
        self.assertIn("escape(", source)


if __name__ == "__main__":
    unittest.main()

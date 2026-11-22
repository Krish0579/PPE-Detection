"""Phase 5 regression tests: theme advancement, keyboard shortcuts, and UX upgrades.

Covers:
- Removed: dark-mode toggle and keyboard-shortcut layer (see TestRemovedChrome)
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

from src.ui.components import render_empty_state
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


class TestRemovedChrome(unittest.TestCase):
    """Dark mode and keyboard shortcuts were removed per operator feedback.

    These assert the removal actually took effect, so the features cannot
    creep back in through a stray import or leftover widget.
    """

    @staticmethod
    def _app_source() -> str:
        return APP_PATH.read_text(encoding="utf-8")

    def test_shortcut_component_is_gone(self) -> None:
        from src.ui import components

        self.assertFalse(hasattr(components, "render_keyboard_shortcuts_script"))
        self.assertNotIn("render_keyboard_shortcuts_script", components.__all__)

    def test_app_renders_no_hotkey_buttons(self) -> None:
        source = self._app_source()
        for token in ("__hk_nav_", "__hk_cam", "__hk_help", "hk_nav_", "_pending_nav"):
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_app_renders_no_shortcut_cheatsheet(self) -> None:
        source = self._app_source()
        self.assertNotIn("ops-kbd", source)
        self.assertNotIn("Keyboard Shortcuts", source)

    @staticmethod
    def _rendered_keys(app: AppTest, kind: str) -> set[str]:
        return {getattr(el, "key", None) for el in getattr(app, kind)}

    def test_no_shortcut_hotkey_buttons_render(self) -> None:
        app = AppTest.from_file(str(APP_PATH), default_timeout=120)
        app.run()
        self.assertFalse(app.exception)

        keys = self._rendered_keys(app, "button")
        self.assertFalse([k for k in keys if k and k.startswith("hk_")])
        self.assertFalse([k for k in keys if k and k.startswith("__hk")])

    def test_dark_mode_toggle_does_not_render(self) -> None:
        app = AppTest.from_file(str(APP_PATH), default_timeout=120)
        app.run()
        self.assertFalse(app.exception)

        toggle_keys = self._rendered_keys(app, "toggle")
        self.assertNotIn("theme_mode_toggle", toggle_keys)
        labels = [t.label for t in app.toggle]
        self.assertFalse([lbl for lbl in labels if lbl and "dark" in lbl.lower()])

    def test_dark_control_room_theme_is_default_and_switchable(self) -> None:
        app = AppTest.from_file(str(APP_PATH), default_timeout=120)
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["theme_mode"], "dark")
        theme = next(select for select in app.selectbox if select.label == "Display theme")
        self.assertEqual(theme.value, "dark")
        theme.select("light").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["theme_mode"], "light")


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

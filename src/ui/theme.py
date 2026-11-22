"""SAFE SIGHT AI UI theme system façade.

Exposes tokenized styling, typography, cards, and responsive palettes
with WCAG AA contrast compliance across both dark and light operating themes.
"""

from __future__ import annotations

from src.ui.theme_css import get_safesight_css

__all__ = ["get_safesight_css"]

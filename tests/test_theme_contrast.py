"""WCAG 2.1 AA contrast regression tests for both UI themes (plan item U5)."""
from __future__ import annotations

import pytest

from src.config.settings import THEME_DARK, THEME_LIGHT

TEXT_TOKENS = ("text", "heading", "muted", "secondary", "green", "red", "amber", "blue")
SURFACES = ("bg", "panel")


def _relative_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linearize(c) for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    lum_fg, lum_bg = _relative_luminance(fg), _relative_luminance(bg)
    hi, lo = max(lum_fg, lum_bg), min(lum_fg, lum_bg)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("theme_name", ["light", "dark"])
def test_text_tokens_meet_wcag_aa(theme_name: str) -> None:
    theme = THEME_LIGHT if theme_name == "light" else THEME_DARK
    failures = []
    for fg in TEXT_TOKENS:
        for surface in SURFACES:
            ratio = contrast_ratio(theme[fg], theme[surface])
            if ratio < 4.5:
                failures.append(f"{fg} on {surface}: {ratio:.2f}")
    assert not failures, f"{theme_name} theme contrast failures: {failures}"

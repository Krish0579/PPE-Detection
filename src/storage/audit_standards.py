"""OSHA and ISO 45001 Regulatory Standards and Canvas Helpers for SafeSight Audits."""
from __future__ import annotations

from typing import Any

from reportlab.lib import colors
from reportlab.pdfgen import canvas

PPE_REGULATORY_MAP: dict[str, dict[str, str]] = {
    "helmet": {
        "standard": "OSHA 29 CFR 1910.135",
        "title": "Head Protection",
        "severity": "CRITICAL",
        "color": "#b91c1c",
    },
    "hardhat": {
        "standard": "OSHA 29 CFR 1910.135",
        "title": "Head Protection",
        "severity": "CRITICAL",
        "color": "#b91c1c",
    },
    "vest": {
        "standard": "ANSI/ISEA 107-2020",
        "title": "High-Visibility Safety Apparel",
        "severity": "HIGH",
        "color": "#d97706",
    },
    "goggle": {
        "standard": "OSHA 29 CFR 1910.133",
        "title": "Eye & Face Protection",
        "severity": "HIGH",
        "color": "#d97706",
    },
    "glass": {
        "standard": "OSHA 29 CFR 1910.133",
        "title": "Eye & Face Protection",
        "severity": "HIGH",
        "color": "#d97706",
    },
    "eye": {
        "standard": "OSHA 29 CFR 1910.133",
        "title": "Eye & Face Protection",
        "severity": "HIGH",
        "color": "#d97706",
    },
    "glove": {
        "standard": "OSHA 29 CFR 1910.138",
        "title": "Hand Protection",
        "severity": "MODERATE",
        "color": "#2563eb",
    },
    "boot": {
        "standard": "OSHA 29 CFR 1910.136",
        "title": "Occupational Foot Protection",
        "severity": "MODERATE",
        "color": "#2563eb",
    },
    "shoe": {
        "standard": "OSHA 29 CFR 1910.136",
        "title": "Occupational Foot Protection",
        "severity": "MODERATE",
        "color": "#2563eb",
    },
    "mask": {
        "standard": "OSHA 29 CFR 1910.134",
        "title": "Respiratory Protection",
        "severity": "HIGH",
        "color": "#d97706",
    },
}

DEFAULT_REGULATORY_INFO: dict[str, str] = {
    "standard": "OSHA 29 CFR 1910.132",
    "title": "General PPE Requirements",
    "severity": "MODERATE",
    "color": "#475569",
}


def get_regulatory_info(gear_name: str) -> dict[str, str]:
    """Retrieve OSHA/ANSI standard and severity rating for a given PPE gear item."""
    gear_lower = gear_name.lower().replace("no ", "").strip()
    for key, info in PPE_REGULATORY_MAP.items():
        if key in gear_lower:
            return info
    return DEFAULT_REGULATORY_INFO


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas that computes total pages and renders running header/footer."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        """Render running top header and bottom footer with dynamic total page count."""
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Top Header (Page 2+)
        if self._pageNumber > 1:
            self.drawString(36, 762, "SAFE SIGHT AI VISION | Certified Safety Audit Report")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(36, 756, 576, 756)

        # Running Bottom Footer (All Pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 28, 576, 28)
        self.drawString(36, 18, "CONFIDENTIAL & PROPRIETARY — ISO 45001 / OSHA 1910 AUDIT COMPLIANT")
        self.drawRightString(576, 18, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()

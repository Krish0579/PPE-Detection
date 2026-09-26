"""Status Badge widget matching original Streamlit design."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel


class StatusBadge(QLabel):
    """Compact rounded status pill badge with clean Streamlit color coding."""

    STYLES = {
        "safe": ("#eaf7f1", "#047857", "#a7f3d0", "● SAFE"),
        "violation": ("#fef2f2", "#b91c1c", "#fecaca", "▲ VIOLATION"),
        "warning": ("#fcf4e5", "#92400e", "#fde68a", "■ WARNING"),
        "info": ("#f0f9ff", "#0369a1", "#bae6fd", "ℹ INFO"),
        "live": ("#eaf7f1", "#047857", "#a7f3d0", "● SYSTEM OPERATIONAL"),
        "standby": ("#f1f5f9", "#475569", "#e2e8f0", "○ STANDBY"),
        "offline": ("#f1f5f9", "#64748b", "#e2e8f0", "○ OFFLINE"),
        "simulated": ("#fcf4e5", "#92400e", "#fde68a", "⚡ SIMULATED"),
    }

    def __init__(self, status: str = "standby", text: str | None = None, parent=None):
        super().__init__(parent)
        self.set_status(status, text)

    def set_status(self, status: str, text: str | None = None) -> None:
        bg, fg, border, default_text = self.STYLES.get(status.lower(), ("#f1f5f9", "#475569", "#e2e8f0", status.upper()))
        display_text = text if text is not None else default_text
        self.setText(display_text)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                font-size: 11px;
                font-weight: 700;
                padding: 4px 12px;
                border-radius: 6px;
                letter-spacing: 0.3px;
            }}
        """)

"""Reusable workspace metric card widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


class MetricCard(QFrame):
    """Clean white card widget displaying key safety telemetry metrics."""

    COLOR_STYLES = {
        "blue": {"soft": "#eaf1fb", "icon_col": "#1d4ed8", "icon": "👥"},
        "green": {"soft": "#eaf7f1", "icon_col": "#047857", "icon": "🛡️"},
        "red": {"soft": "#fef2f2", "icon_col": "#b91c1c", "icon": "⚠️"},
        "amber": {"soft": "#fcf4e5", "icon_col": "#92400e", "icon": "📊"},
    }

    def __init__(
        self,
        title: str,
        value: str = "0",
        subtitle: str = "",
        color: str = "blue",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setProperty("class", "metricCard")

        cfg = self.COLOR_STYLES.get(color, self.COLOR_STYLES["blue"])
        self.color_cfg = cfg

        self.setStyleSheet("""
            QFrame#metricCard {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 14px 16px;
            }
            QFrame#metricCard:hover {
                border-color: #cbd5e1;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Top row: Title + Icon Badge
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #4b5563; letter-spacing: 0.5px;")
        top_row.addWidget(self.lbl_title)
        top_row.addStretch()

        self.lbl_icon = QLabel(cfg["icon"])
        self.lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_icon.setStyleSheet(f"""
            background-color: {cfg["soft"]};
            color: {cfg["icon_col"]};
            border-radius: 8px;
            padding: 4px 8px;
            font-size: 15px;
        """)
        top_row.addWidget(self.lbl_icon)
        layout.addLayout(top_row)

        # Value
        val_color = "#b91c1c" if color == "red" and value not in ("0", "0%") else "#111827"
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"font-size: 34px; font-weight: 800; color: {val_color}; margin-top: 2px;")
        layout.addWidget(self.lbl_value)

        # Subtitle / Foot note
        self.lbl_subtitle = QLabel(subtitle)
        self.lbl_subtitle.setStyleSheet(
            "font-size: 11.5px; color: #64748b; border-top: 1px solid #f1f5f9; padding-top: 6px; margin-top: 2px;"
        )
        layout.addWidget(self.lbl_subtitle)

    def set_value(self, value: str, subtitle: str | None = None) -> None:
        """Update value and optional subtitle dynamically."""
        self.lbl_value.setText(str(value))
        if subtitle is not None:
            self.lbl_subtitle.setText(subtitle)

"""Worker compliance and PPE gear checklist panel matching Streamlit design."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class DetectionPanel(QFrame):
    """Real-time worker compliance checklist panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panelCard")
        self.setProperty("class", "panelCard")
        self.setStyleSheet("""
            QFrame#panelCard {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 10px;
                padding: 14px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("OBSERVED PERSONNEL & GEAR AUDIT")
        title.setStyleSheet("font-size: 11px; font-weight: 800; color: #475569; letter-spacing: 0.6px;")
        header_layout.addWidget(title)

        self.lbl_count = QLabel("0 Active")
        self.lbl_count.setStyleSheet("font-size: 11px; font-weight: 700; color: #047857;")
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_count)
        layout.addLayout(header_layout)

        # Scrollable container for worker cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(8)
        self.container_layout.addStretch()

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def update_workers(self, workers: list[Any]) -> None:
        """Dynamically refresh the worker list."""
        self.lbl_count.setText(f"{len(workers)} Active")

        # Clear existing items
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not workers:
            empty_lbl = QLabel("No workers currently in camera viewport.")
            empty_lbl.setStyleSheet("color: #64748b; font-size: 12px; padding: 16px 0;")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.container_layout.insertWidget(0, empty_lbl)
            return

        for w in workers:
            w_id = getattr(w, "worker_id", 1)
            is_comp = getattr(w, "is_compliant", True)
            zone = getattr(w, "zone", "Production Floor")
            dwell = getattr(w, "dwell_seconds", 0.0)

            w_card = QFrame()
            card_border = "#047857" if is_comp else "#ef4444"
            w_card.setStyleSheet(f"""
                QFrame {{
                    background-color: #ffffff;
                    border: 1px solid #e5e7eb;
                    border-left: 4px solid {card_border};
                    border-radius: 8px;
                    padding: 10px 12px;
                }}
            """)
            c_layout = QVBoxLayout(w_card)
            c_layout.setContentsMargins(8, 6, 8, 6)
            c_layout.setSpacing(4)

            # Top info
            top_layout = QHBoxLayout()
            w_title = QLabel(f"Person {w_id}")
            w_title.setStyleSheet("font-size: 13px; font-weight: 800; color: #0f172a;")
            top_layout.addWidget(w_title)

            w_status = QLabel("● SAFE" if is_comp else "▲ UNSAFE")
            w_status.setStyleSheet(
                "font-size: 11px; font-weight: 700; color: " + ("#047857;" if is_comp else "#b91c1c;")
            )
            top_layout.addStretch()
            top_layout.addWidget(w_status)
            c_layout.addLayout(top_layout)

            # Sub meta
            meta_lbl = QLabel(f"Zone: {zone} · Dwell: {int(dwell)}s")
            meta_lbl.setStyleSheet("font-size: 11px; color: #64748b;")
            c_layout.addWidget(meta_lbl)

            # Gear pills
            gear_layout = QHBoxLayout()
            gear_layout.setSpacing(4)
            for gear in ("helmet", "vest", "boots", "gloves", "goggles"):
                status = getattr(w, f"{gear}_status", "UNKNOWN")
                bg = "#eaf7f1" if status == "COMPLIANT" else ("#fef2f2" if status == "VIOLATION" else "#f1f5f9")
                fg = "#047857" if status == "COMPLIANT" else ("#b91c1c" if status == "VIOLATION" else "#64748b")
                border = "#a7f3d0" if status == "COMPLIANT" else ("#fecaca" if status == "VIOLATION" else "#e2e8f0")
                pill = QLabel(f"{gear.title()[:4]}")
                pill.setStyleSheet(f"background-color: {bg}; color: {fg}; border: 1px solid {border}; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;")
                pill.setToolTip(f"{gear.title()}: {status}")
                gear_layout.addWidget(pill)
            gear_layout.addStretch()
            c_layout.addLayout(gear_layout)

            self.container_layout.insertWidget(self.container_layout.count() - 1, w_card)

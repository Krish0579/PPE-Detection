"""Consolidated incident alerts and safety violation cards matching Streamlit design."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class AlertPanel(QFrame):
    """Real-time active violation alert banner and incident list widget."""

    incident_acknowledged = Signal(str)

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
        title = QLabel("ACTIVE SAFETY ALERTS")
        title.setStyleSheet("font-size: 11px; font-weight: 800; color: #b91c1c; letter-spacing: 0.6px;")
        header_layout.addWidget(title)

        self.lbl_count = QLabel("0 Issues")
        self.lbl_count.setStyleSheet("font-size: 11px; font-weight: 700; color: #047857;")
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_count)
        layout.addLayout(header_layout)

        # Scroll area
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

    def update_alerts(self, incidents: list[dict]) -> None:
        """Update active incidents."""
        active_count = len(incidents)
        self.lbl_count.setText(f"{active_count} Critical" if active_count > 0 else "0 Issues")
        color = "#b91c1c" if active_count > 0 else "#047857"
        self.lbl_count.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {color};")

        # Clear existing items
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if not incidents:
            clean_box = QFrame()
            clean_box.setStyleSheet(
                "background-color: #eaf7f1; border: 1px solid #a7f3d0; border-radius: 8px; padding: 12px;"
            )
            cb_layout = QHBoxLayout(clean_box)
            clean_lbl = QLabel("🎉 All caught up! No active safety violations.")
            clean_lbl.setStyleSheet("color: #047857; font-size: 12.5px; font-weight: 600;")
            clean_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb_layout.addWidget(clean_lbl)
            self.container_layout.insertWidget(0, clean_box)
            return

        for inc in incidents:
            p_name = inc.get("person_name", "Worker")
            missing = inc.get("missing_ppe", set())
            zone = inc.get("zone", "Production Area")

            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background-color: #fef2f2;
                    border: 1px solid #fecaca;
                    border-left: 4px solid #ef4444;
                    border-radius: 8px;
                    padding: 10px 12px;
                }
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(8, 6, 8, 6)
            c_layout.setSpacing(4)

            top = QHBoxLayout()
            w_name = QLabel(p_name)
            w_name.setStyleSheet("font-size: 13px; font-weight: 800; color: #991b1b;")
            top.addWidget(w_name)

            btn_ack = QPushButton("Dismiss")
            btn_ack.setStyleSheet(
                "padding: 2px 8px; font-size: 10.5px; background-color: #ffffff; border: 1px solid #fca5a5; color: #991b1b;"
            )
            btn_ack.clicked.connect(lambda _, n=p_name: self.incident_acknowledged.emit(n))
            top.addStretch()
            top.addWidget(btn_ack)
            c_layout.addLayout(top)

            missing_str = ", ".join(sorted(missing)) if missing else "Safety Violation"
            m_lbl = QLabel(f"⚠️ Missing: {missing_str}")
            m_lbl.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #b91c1c;")
            c_layout.addWidget(m_lbl)

            meta = QLabel(f"Zone: {zone}")
            meta.setStyleSheet("font-size: 11px; color: #64748b;")
            c_layout.addWidget(meta)

            self.container_layout.insertWidget(self.container_layout.count() - 1, card)

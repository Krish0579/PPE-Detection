"""Executive Safety Operations Dashboard view."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.widgets.metric_card import MetricCard
from src.desktop.widgets.status_badge import StatusBadge
from src.storage.evidence import EvidenceManager
from src.video.pipeline import VideoPipeline


class DashboardView(QWidget):
    """High-level industrial safety metrics and system telemetry dashboard."""

    def __init__(
        self,
        pipeline: VideoPipeline,
        evidence_mgr: EvidenceManager,
        device_label: str = "CPU",
        model_name: str = "Custom YOLOv8",
        parent=None,
    ):
        super().__init__(parent)
        self.pipeline = pipeline
        self.evidence_mgr = evidence_mgr
        self.device_label = device_label
        self.model_name = model_name

        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Page Header
        header_layout = QHBoxLayout()
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        lbl_title = QLabel("Safety Operations Executive Dashboard")
        lbl_title.setObjectName("headerTitle")
        lbl_title.setStyleSheet("font-size: 20px; font-weight: 800; color: #f8fafc;")
        title_vbox.addWidget(lbl_title)

        lbl_sub = QLabel("Real-time shopfloor compliance telemetry, incident records, and computer vision status.")
        lbl_sub.setObjectName("headerSubtitle")
        lbl_sub.setStyleSheet("font-size: 12px; color: #94a3b8;")
        title_vbox.addWidget(lbl_sub)

        header_layout.addLayout(title_vbox)
        header_layout.addStretch()

        self.badge_sys = StatusBadge(status="live", text="SYSTEM OPERATIONAL")
        header_layout.addWidget(self.badge_sys)
        main_layout.addLayout(header_layout)

        # Row 1: KPI Metric Cards
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(12)

        self.card_workers = MetricCard("Monitored Workers", "0", "Observed personnel", color="blue")
        self.card_compliant = MetricCard("Compliant Personnel", "0", "Full PPE equipped", color="green")
        self.card_violations = MetricCard("Active Violations", "0", "Immediate attention required", color="red")
        self.card_score = MetricCard("Compliance Rate", "100%", "Facility safety index", color="amber")

        metrics_layout.addWidget(self.card_workers)
        metrics_layout.addWidget(self.card_compliant)
        metrics_layout.addWidget(self.card_violations)
        metrics_layout.addWidget(self.card_score)
        main_layout.addLayout(metrics_layout)

        # Row 2: Two-column split (Recent Events & System Health)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left Column: Recent Violations Table Card
        left_card = QFrame()
        left_card.setObjectName("panelCard")
        left_card.setStyleSheet(
            "background-color: #131d31; border: 1px solid #1e293b; border-radius: 10px; padding: 14px;"
        )
        left_vbox = QVBoxLayout(left_card)
        left_vbox.setSpacing(10)

        table_head = QHBoxLayout()
        t_title = QLabel("RECENT SAFETY INCIDENT LOG")
        t_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #94a3b8; letter-spacing: 0.5px;")
        table_head.addWidget(t_title)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setStyleSheet("padding: 3px 10px; font-size: 11px;")
        btn_refresh.clicked.connect(self.refresh_recent_events)
        table_head.addStretch()
        table_head.addWidget(btn_refresh)
        left_vbox.addLayout(table_head)

        self.table_events = QTableWidget(0, 4)
        self.table_events.setHorizontalHeaderLabels(["Time", "Personnel", "Violation Type", "Severity"])
        self.table_events.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_events.verticalHeader().setVisible(False)
        self.table_events.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_events.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_events.setStyleSheet(
            "QTableWidget { background-color: #0f172a; border: 1px solid #1e293b; border-radius: 6px; }"
        )
        left_vbox.addWidget(self.table_events)

        content_layout.addWidget(left_card, 2)

        # Right Column: System & Hardware Status
        right_card = QFrame()
        right_card.setObjectName("panelCard")
        right_card.setStyleSheet(
            "background-color: #131d31; border: 1px solid #1e293b; border-radius: 10px; padding: 14px;"
        )
        right_vbox = QVBoxLayout(right_card)
        right_vbox.setSpacing(12)

        sys_title = QLabel("SYSTEM & ENGINE HEALTH")
        sys_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #94a3b8; letter-spacing: 0.5px;")
        right_vbox.addWidget(sys_title)

        grid = QGridLayout()
        grid.setSpacing(10)

        # Model Info
        grid.addWidget(QLabel("Neural Model:"), 0, 0)
        lbl_mod = QLabel(self.model_name)
        lbl_mod.setStyleSheet("font-weight: 700; color: #38bdf8;")
        grid.addWidget(lbl_mod, 0, 1)

        # Accelerator
        grid.addWidget(QLabel("Accelerator:"), 1, 0)
        lbl_dev = QLabel(f"⚡ {self.device_label}")
        lbl_dev.setStyleSheet("font-weight: 700; color: #22c55e;")
        grid.addWidget(lbl_dev, 1, 1)

        # Engine Architecture
        grid.addWidget(QLabel("Architecture:"), 2, 0)
        grid.addWidget(QLabel("YOLOv8 Nano"), 2, 1)

        # Re-ID System
        grid.addWidget(QLabel("Re-ID Engine:"), 3, 0)
        grid.addWidget(QLabel("Multi-Zone Spatial Re-ID Gallery"), 3, 1)

        # Database Status
        grid.addWidget(QLabel("Audit Trail:"), 4, 0)
        grid.addWidget(QLabel("SQLite (WAL Active)"), 4, 1)

        right_vbox.addLayout(grid)
        right_vbox.addStretch()

        content_layout.addWidget(right_card, 1)
        main_layout.addLayout(content_layout)

        self.refresh_recent_events()

    def update_telemetry(self, telemetry: dict) -> None:
        """Update live metric cards from background telemetry signal."""
        total = telemetry.get("total_workers", 0)
        safe = telemetry.get("safe_workers", 0)
        violating = telemetry.get("violating_workers", 0)
        score = telemetry.get("safety_score")

        self.card_workers.set_value(str(total))
        self.card_compliant.set_value(str(safe))
        self.card_violations.set_value(str(violating))

        if score is not None:
            self.card_score.set_value(f"{score:.1f}%")
        else:
            self.card_score.set_value("100%")

    def refresh_recent_events(self) -> None:
        """Query recent SQLite events and populate table."""
        events = self.evidence_mgr.query_events(limit=10)
        self.table_events.setRowCount(0)

        for row_idx, ev in enumerate(events):
            self.table_events.insertRow(row_idx)

            # Time
            try:
                dt_str = datetime.fromtimestamp(ev["timestamp"]).strftime("%H:%M:%S")
            except Exception:
                dt_str = "--:--:--"
            self.table_events.setItem(row_idx, 0, QTableWidgetItem(dt_str))

            # Personnel
            p_id = ev.get("person_id")
            p_str = f"Person {p_id}" if p_id is not None else "Worker"
            self.table_events.setItem(row_idx, 1, QTableWidgetItem(p_str))

            # Violation
            v_type = ev.get("violation_type") or "Safety Violation"
            self.table_events.setItem(row_idx, 2, QTableWidgetItem(v_type))

            # Severity
            sev = ev.get("severity") or "WARNING"
            sev_item = QTableWidgetItem(sev)
            if sev == "CRITICAL":
                sev_item.setForeground(Qt.GlobalColor.red)
            else:
                sev_item.setForeground(Qt.GlobalColor.yellow)
            self.table_events.setItem(row_idx, 3, sev_item)

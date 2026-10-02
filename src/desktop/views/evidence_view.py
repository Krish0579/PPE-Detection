"""Forensic safety evidence log viewer matching Screenshot 4."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.desktop.widgets.metric_card import MetricCard
from src.desktop.widgets.status_badge import StatusBadge
from src.storage.evidence import EvidenceManager

logger = logging.getLogger(__name__)


class SnapshotDialog(QDialog):
    """Lightbox modal dialog for viewing full-size incident snapshot and details."""

    def __init__(self, event_data: dict, parent=None):
        super().__init__(parent)
        self.event_data = event_data
        self.setWindowTitle(f"Evidence Incident: {event_data.get('id', 'N/A')}")
        self.setMinimumSize(700, 520)
        self.setStyleSheet("background-color: #ffffff; color: #111827;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header Info
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel(f"Incident {event_data.get('id', 'N/A')}")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: 800; color: #0f172a;")
        title_box.addWidget(lbl_title)

        ts = event_data.get("timestamp", 0)
        try:
            dt_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            dt_str = "Unknown time"
        lbl_sub = QLabel(f"Recorded: {dt_str}  ·  Person ID: {event_data.get('person_id', 'N/A')}")
        lbl_sub.setStyleSheet("font-size: 11.5px; color: #64748b;")
        title_box.addWidget(lbl_sub)
        header.addLayout(title_box)
        header.addStretch()

        sev = event_data.get("severity", "WARNING")
        lbl_sev = QLabel(f" {sev} ")
        sev_color = "#b91c1c" if sev == "CRITICAL" else "#d97706"
        sev_bg = "#fef2f2" if sev == "CRITICAL" else "#fcf4e5"
        lbl_sev.setStyleSheet(
            f"background-color: {sev_bg}; color: {sev_color}; border: 1px solid {sev_color}; border-radius: 4px; font-weight: 800; padding: 4px 10px; font-size: 11px;"
        )
        header.addWidget(lbl_sev)

        layout.addLayout(header)

        # Image Canvas
        self.lbl_image = QLabel()
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setStyleSheet("background-color: #090d16; border: 1px solid #e2e8f0; border-radius: 8px;")
        self.lbl_image.setMinimumSize(640, 360)
        layout.addWidget(self.lbl_image, 1)

        # Load snapshot image
        snap_path = event_data.get("snapshot_path")
        pix = None
        if snap_path and Path(snap_path).exists():
            pix = QPixmap(str(snap_path))
        if pix and not pix.isNull():
            self.lbl_image.setPixmap(
                pix.scaled(640, 360, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self.lbl_image.setText("No snapshot frame archived for this incident")
            self.lbl_image.setStyleSheet("color: #94a3b8; font-size: 13px; font-style: italic;")

        # Details Strip
        details = QHBoxLayout()
        v_type = event_data.get("violation_type") or "Safety Violation"
        lbl_v = QLabel(f"<b>Violation:</b> {v_type}")
        lbl_v.setStyleSheet("font-size: 12.5px; color: #1e293b;")
        details.addWidget(lbl_v)
        details.addStretch()
        lbl_s = QLabel(f"<b>Status:</b> {event_data.get('status', 'ACTIVE')}")
        lbl_s.setStyleSheet("font-size: 12.5px; color: #1e293b;")
        details.addWidget(lbl_s)
        layout.addLayout(details)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)


class EvidenceView(QWidget):
    """Forensic evidence table viewer matching Screenshot 4."""

    def __init__(self, evidence_mgr: EvidenceManager, parent=None):
        super().__init__(parent)
        self.evidence_mgr = evidence_mgr
        self._all_events: list[dict] = []

        self._init_ui()
        self.refresh_events()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 16, 24, 20)
        main_layout.setSpacing(14)

        # Header Container
        header_container = QWidget()
        hc_layout = QHBoxLayout(header_container)
        hc_layout.setContentsMargins(0, 0, 0, 0)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(3)

        lbl_eyebrow = QLabel("● IMMUTABLE AUDIT TRAIL / EVIDENCE DATABASE")
        lbl_eyebrow.setObjectName("pageEyebrow")
        title_vbox.addWidget(lbl_eyebrow)

        lbl_title = QLabel("Evidence Archive & Incident Log")
        lbl_title.setObjectName("pageTitle")
        title_vbox.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Permanent SQLite audit trail, violation snapshots, incident resolution, and certified compliance exports."
        )
        lbl_sub.setObjectName("pageSubtitle")
        title_vbox.addWidget(lbl_sub)

        hc_layout.addLayout(title_vbox)
        hc_layout.addStretch()

        # Header Action Badges
        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)

        lbl_shift = QLabel("🗓️ TODAY, SHIFT 1")
        lbl_shift.setStyleSheet(
            "background-color: #f1f5f9; border: 1px solid #e2e8f0; color: #475569; font-size: 11px; font-weight: 700; padding: 5px 12px; border-radius: 6px;"
        )
        pills_row.addWidget(lbl_shift)

        self.badge_status = StatusBadge(status="live", text="● AI VISION ACTIVE")
        pills_row.addWidget(self.badge_status)
        hc_layout.addLayout(pills_row)

        main_layout.addWidget(header_container)

        # 4 Flagship KPI Cards matching Screenshot 4
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(14)

        self.card_total_p = MetricCard("TOTAL PERSONNEL", "0", "Monitored workers", color="blue")
        self.card_active_v = MetricCard("ACTIVE VIOLATIONS", "0", "Action required", color="red")
        self.card_resolved = MetricCard("RESOLVED INCIDENTS", "0", "Cleared / Acknowledged", color="green")
        self.card_primary = MetricCard(
            "PRIMARY VIOLATION", "None (Fully Compliant)", "Highest frequency check", color="amber"
        )

        metrics_layout.addWidget(self.card_total_p)
        metrics_layout.addWidget(self.card_active_v)
        metrics_layout.addWidget(self.card_resolved)
        metrics_layout.addWidget(self.card_primary)
        main_layout.addLayout(metrics_layout)

        # Filters Bar matching Screenshot 4
        filter_bar = QFrame()
        filter_bar.setObjectName("observationStrip")
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(10, 6, 10, 6)
        f_layout.setSpacing(10)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search violation, person ID, or event key...")
        self.txt_search.textChanged.connect(self._apply_filters)
        f_layout.addWidget(self.txt_search, 2)

        self.cmb_severity = QComboBox()
        self.cmb_severity.addItems(["All Severities", "CRITICAL", "WARNING"])
        self.cmb_severity.currentIndexChanged.connect(self._apply_filters)
        f_layout.addWidget(self.cmb_severity)

        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["All Statuses", "ACTIVE", "ACKNOWLEDGED", "RESOLVED"])
        self.cmb_status.currentIndexChanged.connect(self._apply_filters)
        f_layout.addWidget(self.cmb_status)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh_events)
        f_layout.addWidget(btn_refresh)

        self.btn_resolve = QPushButton("✔ Mark Resolved")
        self.btn_resolve.clicked.connect(self._on_mark_resolved)
        f_layout.addWidget(self.btn_resolve)

        self.btn_export = QPushButton("📥 Export Shift Audit (CSV)")
        self.btn_export.setStyleSheet("""
            QPushButton {
                background-color: #047857;
                color: #ffffff;
                font-weight: 700;
                padding: 6px 14px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #065f46; }
        """)
        self.btn_export.clicked.connect(self._on_export_csv)
        f_layout.addWidget(self.btn_export)

        main_layout.addWidget(filter_bar)

        # Table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Event ID", "Time", "Person", "Violation Type", "Severity", "Status", "Evidence Snapshot"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        main_layout.addWidget(self.table, 1)

    def refresh_events(self) -> None:
        """Fetch all events from database and re-render."""
        try:
            self._all_events = self.evidence_mgr.query_events(limit=300)
            self._update_kpis()
            self._apply_filters()
        except Exception as exc:
            logger.error("Failed to query events: %s", exc)

    def _update_kpis(self) -> None:
        total = len(self._all_events)
        active = sum(1 for e in self._all_events if (e.get("status") or "ACTIVE") == "ACTIVE")
        resolved = sum(1 for e in self._all_events if (e.get("status") or "") == "RESOLVED")

        # Compute unique persons
        persons = {e.get("person_id") for e in self._all_events if e.get("person_id") is not None}
        self.card_total_p.set_value(str(len(persons) if persons else (1 if total > 0 else 0)))
        self.card_active_v.set_value(str(active))
        self.card_resolved.set_value(str(resolved))

        # Primary violation
        v_counts = {}
        for e in self._all_events:
            vt = e.get("violation_type")
            if vt:
                v_counts[vt] = v_counts.get(vt, 0) + 1
        if v_counts:
            top_v = max(v_counts.items(), key=lambda x: x[1])[0]
            self.card_primary.set_value(str(top_v)[:26])
        else:
            self.card_primary.set_value("None (Fully Compliant)")

    def _apply_filters(self) -> None:
        search_term = self.txt_search.text().strip().lower()
        sev_filter = self.cmb_severity.currentText()
        status_filter = self.cmb_status.currentText()

        filtered = []
        for ev in self._all_events:
            if sev_filter != "All Severities" and ev.get("severity") != sev_filter:
                continue
            if status_filter != "All Statuses" and ev.get("status") != status_filter:
                continue
            if search_term:
                match_id = search_term in str(ev.get("id", "")).lower()
                match_v = search_term in str(ev.get("violation_type", "")).lower()
                match_p = search_term in str(ev.get("person_id", "")).lower()
                if not (match_id or match_v or match_p):
                    continue
            filtered.append(ev)

        self._populate_table(filtered)

    def _populate_table(self, events: list[dict]) -> None:
        self.table.setRowCount(0)
        for row_idx, ev in enumerate(events):
            self.table.insertRow(row_idx)

            item_id = QTableWidgetItem(str(ev.get("id", "")))
            item_id.setData(Qt.ItemDataRole.UserRole, ev)
            self.table.setItem(row_idx, 0, item_id)

            ts = ev.get("timestamp", 0)
            try:
                dt_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                dt_str = "--"
            self.table.setItem(row_idx, 1, QTableWidgetItem(dt_str))

            p_id = ev.get("person_id")
            p_text = f"Worker #{p_id}" if p_id is not None else "General"
            self.table.setItem(row_idx, 2, QTableWidgetItem(p_text))

            v_type = ev.get("violation_type") or "Violation"
            self.table.setItem(row_idx, 3, QTableWidgetItem(v_type))

            sev = ev.get("severity") or "WARNING"
            sev_item = QTableWidgetItem(sev)
            if sev == "CRITICAL":
                sev_item.setForeground(QColor("#b91c1c"))
            else:
                sev_item.setForeground(QColor("#d97706"))
            self.table.setItem(row_idx, 4, sev_item)

            stat = ev.get("status") or "ACTIVE"
            stat_item = QTableWidgetItem(stat)
            if stat == "RESOLVED":
                stat_item.setForeground(QColor("#047857"))
            elif stat == "ACKNOWLEDGED":
                stat_item.setForeground(QColor("#0284c7"))
            else:
                stat_item.setForeground(QColor("#b91c1c"))
            self.table.setItem(row_idx, 5, stat_item)

            btn_view = QPushButton("🔍 Inspect Frame")
            btn_view.setStyleSheet("padding: 3px 8px; font-size: 11px;")
            btn_view.clicked.connect(lambda _, e=ev: self._show_lightbox(e))
            self.table.setCellWidget(row_idx, 6, btn_view)

    def _show_lightbox(self, event_data: dict) -> None:
        dlg = SnapshotDialog(event_data, parent=self)
        dlg.exec()

    @Slot()
    def _on_row_double_clicked(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
            if item:
                ev = item.data(Qt.ItemDataRole.UserRole)
                if ev:
                    self._show_lightbox(ev)

    @Slot()
    def _on_mark_resolved(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Resolve Incident", "Please select an incident row first.")
            return

        item = self.table.item(row, 0)
        if not item:
            return
        ev = item.data(Qt.ItemDataRole.UserRole)
        evt_id = ev.get("id")

        if evt_id:
            ok = self.evidence_mgr.update_event_status(evt_id, "RESOLVED")
            if ok:
                self.refresh_events()
            else:
                QMessageBox.warning(self, "Update Failed", "Could not update event status in SQLite.")

    @Slot()
    def _on_export_csv(self) -> None:
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Shift Compliance Audit Report",
            f"ppe_shift_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv)",
        )
        if save_path:
            csv_content = self.evidence_mgr.export_shift_audit_csv()
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(csv_content)
                QMessageBox.information(self, "Export Complete", f"Audit report exported successfully to:\n{save_path}")
            except Exception as exc:
                QMessageBox.critical(self, "Export Error", f"Failed to save CSV file:\n{exc}")

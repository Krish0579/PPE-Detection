"""Real-time camera feed and live neural inference view matching original Streamlit design."""

from __future__ import annotations

import logging
import time
from typing import Any

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.desktop.widgets.alert_panel import AlertPanel
from src.desktop.widgets.camera_selector import CameraSelector
from src.desktop.widgets.detection_panel import DetectionPanel
from src.desktop.widgets.metric_card import MetricCard
from src.desktop.widgets.status_badge import StatusBadge
from src.desktop.widgets.video_display import VideoDisplayWidget
from src.desktop.workers.video_worker import VideoWorker
from src.storage.evidence import EvidenceManager
from src.video.pipeline import VideoPipeline

logger = logging.getLogger(__name__)


def extract_missing_ppe_from_worker(w: Any) -> set[str]:
    """Extract human-readable missing PPE gear names from WorkerStatus data."""
    missing = set()

    # 1. Inspect gear statuses
    if getattr(w, "helmet_status", "") == "VIOLATION":
        missing.add("Helmet")
    if getattr(w, "vest_status", "") == "VIOLATION":
        missing.add("Vest")
    if getattr(w, "boots_status", "") == "VIOLATION":
        missing.add("Boots")
    if getattr(w, "gloves_status", "") == "VIOLATION":
        missing.add("Gloves")
    if getattr(w, "goggles_status", "") == "VIOLATION":
        missing.add("Goggles")
    if getattr(w, "is_restricted_zone", False):
        missing.add("Restricted Zone")

    # 2. Inspect violations list
    for v in getattr(w, "violations", []):
        cleaned = str(v).replace("_", " ").title().strip()
        if cleaned.lower().startswith("no "):
            cleaned = cleaned[3:].strip()
        if cleaned.lower() not in ("restricted zone", "safety violation", "none", ""):
            missing.add(cleaned)

    return missing


class LiveFeedView(QWidget):
    """Primary live inspection viewport matching the flagship Streamlit Live Feed design."""

    def __init__(
        self,
        pipeline: VideoPipeline,
        video_worker: VideoWorker,
        evidence_mgr: EvidenceManager,
        parent=None,
    ):
        super().__init__(parent)
        self.pipeline = pipeline
        self.worker = video_worker
        self.evidence_mgr = evidence_mgr
        self._last_frame_bgr = None

        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 16, 24, 20)
        main_layout.setSpacing(14)

        # ----------------- PAGE HEADER -----------------
        header_container = QWidget()
        hc_layout = QHBoxLayout(header_container)
        hc_layout.setContentsMargins(0, 0, 0, 0)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(3)

        lbl_eyebrow = QLabel("● CAMERA REVIEW / CAM-01 READY")
        lbl_eyebrow.setObjectName("pageEyebrow")
        title_vbox.addWidget(lbl_eyebrow)

        lbl_title = QLabel("Live camera review")
        lbl_title.setObjectName("pageTitle")
        title_vbox.addWidget(lbl_title)

        lbl_sub = QLabel("Real-time camera feed with continuous multi-person PPE tracking and zone safety monitoring.")
        lbl_sub.setObjectName("pageSubtitle")
        title_vbox.addWidget(lbl_sub)

        hc_layout.addLayout(title_vbox)
        hc_layout.addStretch()

        # Header Action Badges
        pills_vbox = QVBoxLayout()
        pills_vbox.setSpacing(6)
        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)

        lbl_shift = QLabel("🗓️ TODAY, SHIFT 1")
        lbl_shift.setStyleSheet(
            "background-color: #f1f5f9; border: 1px solid #e2e8f0; color: #475569; font-size: 11px; font-weight: 700; padding: 5px 12px; border-radius: 6px;"
        )
        pills_row.addWidget(lbl_shift)

        self.badge_status = StatusBadge(status="standby", text="● Workspace ready")
        pills_row.addWidget(self.badge_status)

        pills_vbox.addLayout(pills_row)
        pills_vbox.addStretch()
        hc_layout.addLayout(pills_vbox)

        main_layout.addWidget(header_container)

        # ----------------- COMPACT FEED SOURCE & QUICK TIP STRIP -----------------
        source_strip = QFrame()
        source_strip.setObjectName("observationStrip")
        source_strip.setStyleSheet("""
            QFrame#observationStrip {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 6px 14px;
            }
        """)
        s_layout = QHBoxLayout(source_strip)
        s_layout.setContentsMargins(10, 4, 10, 4)
        s_layout.setSpacing(14)

        lbl_source = QLabel("FEED SOURCE:")
        lbl_source.setStyleSheet("font-size: 11px; font-weight: 800; color: #475569; letter-spacing: 0.5px;")
        s_layout.addWidget(lbl_source)

        self.radio_browser = QRadioButton("Direct Camera")
        self.radio_webrtc = QRadioButton("Continuous 30 FPS Stream")
        self.radio_usb = QRadioButton("Demo source")

        self.radio_webrtc.setChecked(True)
        self.btn_group_source = QButtonGroup(self)
        self.btn_group_source.addButton(self.radio_browser, 0)
        self.btn_group_source.addButton(self.radio_webrtc, 1)
        self.btn_group_source.addButton(self.radio_usb, 2)

        s_layout.addWidget(self.radio_browser)
        s_layout.addWidget(self.radio_webrtc)
        s_layout.addWidget(self.radio_usb)
        s_layout.addStretch()

        lbl_tip = QLabel("💡 Tip: Adjust confidence or inference skip in Settings for instant zero-delay")
        lbl_tip.setStyleSheet("font-size: 11px; color: #0284c7; font-weight: 500;")
        s_layout.addWidget(lbl_tip)

        main_layout.addWidget(source_strip)

        # ----------------- MAIN VIEWPORT SPLIT (ENLARGED CAMERA) -----------------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(10)
        splitter.setStyleSheet("QSplitter::handle { background-color: #f1f5f9; border-radius: 2px; }")

        # Left Container: Enlarged Video Viewport + Controls + Observation Strip
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.video_display = VideoDisplayWidget(
            placeholder_text="Camera Standby · Click START below to begin real-time streaming"
        )
        left_layout.addWidget(self.video_display, 1)

        # Controls Bar (Red START button, Camera selector, Snapshot, Reset IDs)
        ctrl_bar = QWidget()
        cb_layout = QHBoxLayout(ctrl_bar)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        cb_layout.setSpacing(10)

        # Red START button matching original Streamlit design
        self.btn_start = QPushButton("START")
        self.btn_start.setObjectName("primaryRedButton")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 13px;
                font-weight: 800;
                letter-spacing: 0.5px;
            }
            QPushButton:hover { background-color: #dc2626; }
            QPushButton:disabled { background-color: #e5e7eb; color: #9ca3af; }
        """)
        self.btn_start.clicked.connect(self._on_start_clicked)
        cb_layout.addWidget(self.btn_start)

        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 12.5px;
                font-weight: 700;
            }
            QPushButton:hover { background-color: #f9fafb; border-color: #9ca3af; }
            QPushButton:disabled { background-color: #f3f4f6; color: #9ca3af; border-color: #e5e7eb; }
        """)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        cb_layout.addWidget(self.btn_stop)

        cb_layout.addSpacing(8)

        self.cam_selector = CameraSelector()
        cb_layout.addWidget(self.cam_selector)

        cb_layout.addStretch()

        self.btn_snapshot = QPushButton("📷 Save Snapshot")
        self.btn_snapshot.clicked.connect(self._on_snapshot_clicked)
        cb_layout.addWidget(self.btn_snapshot)

        self.btn_reset_ids = QPushButton("🔄 Reset IDs")
        self.btn_reset_ids.setToolTip("Clear tracked person identities and color gallery")
        self.btn_reset_ids.clicked.connect(self._on_reset_ids_clicked)
        cb_layout.addWidget(self.btn_reset_ids)

        left_layout.addWidget(ctrl_bar)

        # Observation / Telemetry Strip matching Streamlit screenshot
        obs_strip = QFrame()
        obs_strip.setObjectName("observationStrip")
        obs_layout = QHBoxLayout(obs_strip)
        obs_layout.setContentsMargins(14, 8, 14, 8)
        obs_layout.setSpacing(14)

        self.badge_obs = QLabel("LIVE CAMERA INFERENCE")
        self.badge_obs.setStyleSheet(
            "background-color: #eaf7f1; border: 1px solid #a7f3d0; color: #047857; font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 4px;"
        )
        obs_layout.addWidget(self.badge_obs)

        self.lbl_counts_strip = QLabel("0 detections  ·  0 personnel  ·  0 violations")
        self.lbl_counts_strip.setStyleSheet("font-size: 12px; font-weight: 600; color: #475569;")
        obs_layout.addWidget(self.lbl_counts_strip)

        obs_layout.addStretch()

        self.lbl_fps_strip = QLabel("⚡ 0.0 FPS | 0 ms")
        self.lbl_fps_strip.setStyleSheet("font-size: 12px; font-weight: 700; color: #047857;")
        obs_layout.addWidget(self.lbl_fps_strip)

        left_layout.addWidget(obs_strip)
        splitter.addWidget(left_widget)

        # Right Container: DetectionPanel (Top) & AlertPanel (Bottom)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        self.detection_panel = DetectionPanel()
        self.alert_panel = AlertPanel()

        right_layout.addWidget(self.detection_panel, 3)
        right_layout.addWidget(self.alert_panel, 2)
        splitter.addWidget(right_widget)

        # Give generous 4:1 width ratio to video canvas (~80% width)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([960, 320])

        main_layout.addWidget(splitter, 1)

        # ----------------- ROW OF 4 FLAGSHIP KPI CARDS AT BOTTOM -----------------
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(14)

        self.card_workers = MetricCard("People in view", "0", "● Current camera view", color="blue")
        self.card_compliant = MetricCard("Safe workers", "0", "Full PPE equipped personnel", color="green")
        self.card_violations = MetricCard("Active violations", "0", "Immediate attention required", color="red")
        self.card_score = MetricCard("Safety score", "100.0%", "Compliant ÷ required checks", color="amber")

        metrics_layout.addWidget(self.card_workers)
        metrics_layout.addWidget(self.card_compliant)
        metrics_layout.addWidget(self.card_violations)
        metrics_layout.addWidget(self.card_score)

        main_layout.addLayout(metrics_layout)

    def _connect_signals(self) -> None:
        self.worker.frame_ready.connect(self._on_frame_ready)
        self.worker.telemetry_updated.connect(self._on_telemetry)
        self.worker.workers_updated.connect(self._on_workers)
        self.worker.status_changed.connect(self._on_status_changed)
        self.worker.error_occurred.connect(self._on_error)

    @Slot()
    def _on_start_clicked(self) -> None:
        dev_idx = self.cam_selector.current_device()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.cam_selector.setEnabled(False)
        self.video_display.set_placeholder("Initializing camera capture & neural weights...")
        self.worker.start_camera(dev_idx)

    @Slot()
    def _on_stop_clicked(self) -> None:
        self.worker.stop_camera()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.cam_selector.setEnabled(True)
        self.badge_status.set_status("offline", "○ CAMERA OFFLINE")
        self.video_display.clear()
        self.lbl_fps_strip.setText("⚡ 0.0 FPS | 0 ms")
        self.lbl_counts_strip.setText("0 detections  ·  0 personnel  ·  0 violations")

    @Slot(QImage)
    def _on_frame_ready(self, q_img: QImage) -> None:
        self.video_display.set_image(q_img)

    @Slot(dict)
    def _on_telemetry(self, t: dict) -> None:
        fps = t.get("fps", 0.0)
        ms = t.get("inference_ms", 0.0)
        total_w = t.get("total_workers", 0)
        safe_w = t.get("safe_workers", 0)
        violating_w = t.get("violating_workers", 0)
        score = t.get("safety_score", 100.0)
        is_sim = t.get("is_simulated", False)

        # Update Observation Strip
        self.lbl_fps_strip.setText(f"⚡ {fps:.1f} FPS | {ms:.0f} ms")
        self.lbl_counts_strip.setText(f"{total_w} personnel  ·  {violating_w} active violations")

        # Update bottom KPI Metric Cards
        self.card_workers.set_value(str(total_w))
        self.card_compliant.set_value(str(safe_w))
        self.card_violations.set_value(str(violating_w))
        if score is not None:
            self.card_score.set_value(f"{score:.1f}%")
        else:
            self.card_score.set_value("100.0%")

        if is_sim:
            self.badge_status.set_status("simulated", "⚡ SIMULATED FEED")
        else:
            self.badge_status.set_status("live", "● Camera review active")

    @Slot(list)
    def _on_workers(self, workers: list[Any]) -> None:
        self.detection_panel.update_workers(workers)

        # FIXED ALERT ISSUE: Extract actual missing PPE from WorkerStatus
        incidents = []
        for w in workers:
            if getattr(w, "has_active_violation", False):
                missing_set = extract_missing_ppe_from_worker(w)
                incidents.append(
                    {
                        "person_name": f"Person #{getattr(w, 'worker_id', 1)}",
                        "missing_ppe": missing_set,
                        "zone": getattr(w, "zone", "Production Area"),
                    }
                )
        self.alert_panel.update_alerts(incidents)

    @Slot(bool, str)
    def _on_status_changed(self, is_running: bool, message: str) -> None:
        if not is_running:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.cam_selector.setEnabled(True)
            self.badge_status.set_status("offline", "○ CAMERA OFFLINE")

    @Slot(str)
    def _on_error(self, err_msg: str) -> None:
        logger.error("Live feed error: %s", err_msg)
        QMessageBox.warning(self, "Camera Pipeline Alert", f"Streaming anomaly: {err_msg}")

    @Slot()
    def _on_snapshot_clicked(self) -> None:
        state = self.pipeline.state.snapshot_ui()
        latest = state.get("latest_frame")
        if latest is None:
            QMessageBox.information(self, "Snapshot", "No video frame currently available to capture.")
            return

        violating_labels = [
            d.get("label", "violation") for d in state.get("detections", []) if "no_" in d.get("label", "")
        ]
        workers = state.get("workers", [])
        active_person_id = 1
        for w in workers:
            if getattr(w, "has_active_violation", False):
                active_person_id = getattr(w, "worker_id", 1)
                break
        else:
            if workers:
                active_person_id = getattr(workers[0], "worker_id", 1)

        rec = self.evidence_mgr.save_snapshot(
            frame=latest,
            violating_labels=violating_labels or ["manual_snapshot"],
            timestamp=time.time(),
            person_id=active_person_id,
            log_to_db=True,
        )
        if rec:
            QMessageBox.information(
                self,
                "Snapshot Saved",
                f"Snapshot archived successfully for Worker #{active_person_id}:\n{rec.get('filename')}",
            )
        else:
            QMessageBox.warning(self, "Snapshot Failed", "Failed to compress or write snapshot to disk.")

    @Slot()
    def _on_reset_ids_clicked(self) -> None:
        self.pipeline.reset_tracker()
        QMessageBox.information(self, "Re-ID Reset", "Worker tracking identities and color gallery have been reset.")

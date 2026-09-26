"""Static image inspection and single-frame audit view matching Screenshot 3."""
from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
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

from src.desktop.widgets.detection_panel import DetectionPanel
from src.desktop.widgets.status_badge import StatusBadge
from src.desktop.widgets.video_display import VideoDisplayWidget
from src.video.pipeline import VideoPipeline

logger = logging.getLogger(__name__)


class ImageView(QWidget):
    """Static image audit interface matching Screenshot 3."""

    def __init__(self, pipeline: VideoPipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self._current_annotated: np.ndarray | None = None
        self._current_file: Path | None = None

        self._init_ui()

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

        lbl_eyebrow = QLabel("● PRECISION AUDIT / STATIC ANALYSIS")
        lbl_eyebrow.setObjectName("pageEyebrow")
        title_vbox.addWidget(lbl_eyebrow)

        lbl_title = QLabel("High-Resolution Image Inspection")
        lbl_title.setObjectName("pageTitle")
        title_vbox.addWidget(lbl_title)

        lbl_sub = QLabel("Precision spatial PPE inspection on individual photographs and quality inspection captures.")
        lbl_sub.setObjectName("pageSubtitle")
        title_vbox.addWidget(lbl_sub)

        hc_layout.addLayout(title_vbox)
        hc_layout.addStretch()

        # Header Action Badges
        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)

        lbl_shift = QLabel("🗓️ TODAY, SHIFT 1")
        lbl_shift.setStyleSheet("background-color: #f1f5f9; border: 1px solid #e2e8f0; color: #475569; font-size: 11px; font-weight: 700; padding: 5px 12px; border-radius: 6px;")
        pills_row.addWidget(lbl_shift)

        self.badge_status = StatusBadge(status="live", text="● AI VISION ACTIVE")
        pills_row.addWidget(self.badge_status)
        hc_layout.addLayout(pills_row)

        main_layout.addWidget(header_container)

        # Source Toggle Radio Buttons matching Screenshot 3
        lbl_src_title = QLabel("Image Inspection Source")
        lbl_src_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #1e293b;")
        main_layout.addWidget(lbl_src_title)

        src_row = QHBoxLayout()
        src_row.setSpacing(20)

        self.radio_upload = QRadioButton("📁 Upload Image File")
        self.radio_camera = QRadioButton("📷 Live Camera Capture")
        self.radio_upload.setChecked(True)

        self.btn_group_src = QButtonGroup(self)
        self.btn_group_src.addButton(self.radio_upload, 0)
        self.btn_group_src.addButton(self.radio_camera, 1)

        src_row.addWidget(self.radio_upload)
        src_row.addWidget(self.radio_camera)
        src_row.addStretch()
        main_layout.addLayout(src_row)

        # File Uploader Box matching Screenshot 3
        lbl_upload_title = QLabel("Upload Image File (JPG, PNG, WEBP)")
        lbl_upload_title.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #374151;")
        main_layout.addWidget(lbl_upload_title)

        upload_card = QFrame()
        upload_card.setObjectName("uploaderCard")
        uc_layout = QHBoxLayout(upload_card)
        uc_layout.setContentsMargins(20, 16, 20, 16)
        uc_layout.setSpacing(16)

        cloud_icon = QLabel("☁️")
        cloud_icon.setStyleSheet("font-size: 32px;")
        uc_layout.addWidget(cloud_icon)

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)
        lbl_drop = QLabel("Drag and drop file here")
        lbl_drop.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #1e293b;")
        text_vbox.addWidget(lbl_drop)

        lbl_limit = QLabel("Limit 500MB per file · JPG, JPEG, PNG, WEBP")
        lbl_limit.setStyleSheet("font-size: 11.5px; color: #64748b;")
        text_vbox.addWidget(lbl_limit)
        uc_layout.addLayout(text_vbox)
        uc_layout.addStretch()

        self.btn_open = QPushButton("Browse files")
        self.btn_open.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #111827;
                border: 1px solid #d1d5db;
                font-weight: 700;
                padding: 8px 18px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #f9fafb; border-color: #9ca3af; }
        """)
        self.btn_open.clicked.connect(self._on_open_file)
        uc_layout.addWidget(self.btn_open)

        main_layout.addWidget(upload_card)

        # Light blue Info Banner
        tip_frame = QFrame()
        tip_frame.setObjectName("tipBanner")
        tf_layout = QHBoxLayout(tip_frame)
        tf_layout.setContentsMargins(12, 8, 12, 8)
        lbl_tip = QLabel("Upload a high-resolution JPG, PNG, or WEBP image to execute automated PPE inspection.")
        lbl_tip.setObjectName("tipBannerText")
        tf_layout.addWidget(lbl_tip)
        main_layout.addWidget(tip_frame)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)

        # Left: Video / Image Viewport
        left_box = QWidget()
        lb_layout = QVBoxLayout(left_box)
        lb_layout.setContentsMargins(0, 0, 0, 0)
        lb_layout.setSpacing(8)

        self.display = VideoDisplayWidget(placeholder_text="No image loaded · Click 'Browse files' above to run audit")
        lb_layout.addWidget(self.display, 1)

        # Save Button bar
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        self.btn_save = QPushButton("💾 Save Result")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._on_save_annotated)
        btn_bar.addWidget(self.btn_save)
        lb_layout.addLayout(btn_bar)

        splitter.addWidget(left_box)

        # Right: Audit Summary Panel
        right_container = QWidget()
        r_layout = QVBoxLayout(right_container)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(10)

        # Observation Strip
        stat_box = QFrame()
        stat_box.setObjectName("observationStrip")
        stat_layout = QVBoxLayout(stat_box)
        stat_layout.setContentsMargins(12, 10, 12, 10)
        stat_layout.setSpacing(6)

        self.lbl_file_name = QLabel("File: None")
        self.lbl_file_name.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e293b;")
        stat_layout.addWidget(self.lbl_file_name)

        self.lbl_infer_time = QLabel("Inference Latency: 0.0 ms")
        self.lbl_infer_time.setStyleSheet("font-size: 11.5px; font-weight: 700; color: #047857;")
        stat_layout.addWidget(self.lbl_infer_time)

        self.badge_compliance = StatusBadge(status="offline", text="○ NO AUDIT")
        stat_layout.addWidget(self.badge_compliance)

        r_layout.addWidget(stat_box)

        # Worker Checklist
        self.detection_panel = DetectionPanel()
        r_layout.addWidget(self.detection_panel, 1)

        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)

    @Slot()
    def _on_open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image to Audit",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff)",
        )
        if not file_path:
            return

        self.audit_image(Path(file_path))

    def audit_image(self, path: Path) -> None:
        """Load image file, execute inference, and display results."""
        if not path.exists():
            QMessageBox.warning(self, "File Not Found", f"Image file not found: {path}")
            return

        raw_bgr = cv2.imread(str(path))
        if raw_bgr is None:
            QMessageBox.critical(self, "Invalid Image", f"Could not decode image at:\n{path}")
            return

        self._current_file = path
        self.lbl_file_name.setText(f"File: {path.name}")

        t0 = time.perf_counter()
        annotated = self.pipeline.process_numpy_frame(raw_bgr, force_infer=True)
        infer_ms = (time.perf_counter() - t0) * 1000.0

        self._current_annotated = annotated
        self.btn_save.setEnabled(True)
        self.lbl_infer_time.setText(f"Inference Latency: {infer_ms:.1f} ms")

        h, w, ch = annotated.shape
        bytes_per_line = ch * w
        q_img = QImage(annotated.data, w, h, bytes_per_line, QImage.Format.Format_BGR888).copy()
        self.display.set_image(q_img)

        state = self.pipeline.state.snapshot_ui()
        workers = state.get("workers", [])
        self.detection_panel.update_workers(workers)

        has_violations = any(getattr(w, "has_active_violation", False) for w in workers)
        if not workers:
            self.badge_compliance.set_status("offline", "○ NO PERSONNEL FOUND")
        elif has_violations:
            self.badge_compliance.set_status("violation", "▲ VIOLATIONS DETECTED")
        else:
            self.badge_compliance.set_status("safe", "● 100% COMPLIANT")

    @Slot()
    def _on_save_annotated(self) -> None:
        if self._current_annotated is None:
            return

        default_name = f"audited_{self._current_file.name if self._current_file else 'frame.jpg'}"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Annotated Audit Result",
            default_name,
            "JPEG (*.jpg);;PNG (*.png)",
        )
        if save_path:
            cv2.imwrite(save_path, self._current_annotated)
            QMessageBox.information(self, "Saved", f"Annotated image saved to:\n{save_path}")

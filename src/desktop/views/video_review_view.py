"""Recorded video file playback and forensic review view matching original Streamlit design."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.desktop.widgets.detection_panel import DetectionPanel
from src.desktop.widgets.status_badge import StatusBadge
from src.desktop.widgets.video_display import VideoDisplayWidget
from src.desktop.workers.video_file_worker import VideoFileWorker
from src.video.pipeline import VideoPipeline

logger = logging.getLogger(__name__)


class VideoReviewView(QWidget):
    """Recorded video analysis view matching Screenshot 2."""

    def __init__(self, pipeline: VideoPipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.worker = VideoFileWorker(pipeline=self.pipeline, parent=self)
        self._user_seeking = False
        self._total_frames = 0
        self._fps = 30.0

        self._init_ui()
        self._connect_signals()
        self.worker.start()

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

        lbl_eyebrow = QLabel("● OFFLINE AUDIT ENGINE / VIDEO ANALYSIS")
        lbl_eyebrow.setObjectName("pageEyebrow")
        title_vbox.addWidget(lbl_eyebrow)

        lbl_title = QLabel("Recorded Video Inspection")
        lbl_title.setObjectName("pageTitle")
        title_vbox.addWidget(lbl_title)

        lbl_sub = QLabel(
            "High-throughput video file audit with frame scrubbing, PPE detection, and safety violation logging."
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

        # Upload Box Container matching Streamlit Screenshot 2
        lbl_upload_title = QLabel("Upload Video File (MP4, MOV, AVI, WEBM)")
        lbl_upload_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #1e293b;")
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

        lbl_limit = QLabel("Limit 500MB per file · MP4, MOV, AVI, WEBM, MPEG4")
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
        lbl_tip = QLabel(
            "Upload an MP4, MOV, or AVI video clip to scrub through frames and execute automated PPE inspection."
        )
        lbl_tip.setObjectName("tipBannerText")
        tf_layout.addWidget(lbl_tip)
        main_layout.addWidget(tip_frame)

        # Main Splitter (Left: Video Player, Right: Gear Inspection Checklist)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)

        # Left Container: Video Canvas + Timeline Bar + Playback Controls
        left_box = QWidget()
        l_layout = QVBoxLayout(left_box)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.setSpacing(8)

        self.display = VideoDisplayWidget(
            placeholder_text="No video loaded · Click 'Browse files' above to begin inspection"
        )
        l_layout.addWidget(self.display, 1)

        # Playback Controls Bar
        ctrl_card = QFrame()
        ctrl_card.setObjectName("observationStrip")
        c_layout = QVBoxLayout(ctrl_card)
        c_layout.setContentsMargins(12, 8, 12, 8)
        c_layout.setSpacing(6)

        # Timeline seek slider
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        self.seek_slider.valueChanged.connect(self._on_seek_value_changed)
        c_layout.addWidget(self.seek_slider)

        # Buttons + Position Time
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_play = QPushButton("▶ Play")
        self.btn_play.setEnabled(False)
        self.btn_play.setStyleSheet("font-weight: 700; padding: 4px 14px;")
        self.btn_play.clicked.connect(self.worker.toggle_play)
        btn_row.addWidget(self.btn_play)

        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("padding: 4px 10px;")
        self.btn_stop.clicked.connect(self._on_stop_playback)
        btn_row.addWidget(self.btn_stop)

        self.lbl_time = QLabel("00:00 / 00:00 (Frame 0/0)")
        self.lbl_time.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #475569;")
        btn_row.addWidget(self.lbl_time)

        btn_row.addStretch()

        self.lbl_file = QLabel("No file loaded")
        self.lbl_file.setStyleSheet("font-size: 11.5px; color: #64748b;")
        btn_row.addWidget(self.lbl_file)

        c_layout.addLayout(btn_row)
        l_layout.addWidget(ctrl_card)

        splitter.addWidget(left_box)

        # Right Container: Inspection Checklist
        right_box = QWidget()
        r_layout = QVBoxLayout(right_box)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(10)

        # Telemetry Card
        stat_card = QFrame()
        stat_card.setObjectName("observationStrip")
        s_layout = QHBoxLayout(stat_card)
        s_layout.setContentsMargins(12, 8, 12, 8)
        self.lbl_status = QLabel("STATUS: IDLE")
        self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b;")
        s_layout.addWidget(self.lbl_status)
        s_layout.addStretch()
        self.lbl_fps = QLabel("FPS: 0.0")
        self.lbl_fps.setStyleSheet("font-size: 11px; font-weight: 700; color: #047857;")
        s_layout.addWidget(self.lbl_fps)
        r_layout.addWidget(stat_card)

        self.detection_panel = DetectionPanel()
        r_layout.addWidget(self.detection_panel, 1)

        splitter.addWidget(right_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)

    def _connect_signals(self) -> None:
        self.worker.frame_ready.connect(self._on_frame_ready)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.telemetry_updated.connect(self._on_telemetry)
        self.worker.workers_updated.connect(self.detection_panel.update_workers)
        self.worker.state_changed.connect(self._on_play_state_changed)
        self.worker.error_occurred.connect(self._on_error)

    @Slot()
    def _on_open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.m4v)",
        )
        if not file_path:
            return

        ok = self.worker.load_video(file_path)
        if ok:
            path = Path(file_path)
            self.lbl_file.setText(path.name)
            self._total_frames = self.worker._total_frames
            self._fps = self.worker._fps
            self.seek_slider.setRange(0, max(0, self._total_frames - 1))
            self.seek_slider.setValue(0)
            self.btn_play.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self.lbl_status.setText("STATUS: READY")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #047857;")

    @Slot(QImage)
    def _on_frame_ready(self, q_img: QImage) -> None:
        self.display.set_image(q_img)

    @Slot(int, int)
    def _on_progress(self, current: int, total: int) -> None:
        if not self._user_seeking:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(current)
            self.seek_slider.blockSignals(False)

        cur_sec = int(current / self._fps) if self._fps > 0 else 0
        tot_sec = int(total / self._fps) if self._fps > 0 else 0
        cur_str = f"{cur_sec // 60:02d}:{cur_sec % 60:02d}"
        tot_str = f"{tot_sec // 60:02d}:{tot_sec % 60:02d}"
        self.lbl_time.setText(f"{cur_str} / {tot_str} (Frame {current}/{total})")

    @Slot(dict)
    def _on_telemetry(self, t: dict) -> None:
        fps = t.get("fps", 0.0)
        self.lbl_fps.setText(f"FPS: {fps:.1f}")

    @Slot(bool)
    def _on_play_state_changed(self, is_playing: bool) -> None:
        if is_playing:
            self.btn_play.setText("⏸ Pause")
            self.lbl_status.setText("STATUS: PLAYING")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #047857;")
        else:
            self.btn_play.setText("▶ Play")
            self.lbl_status.setText("STATUS: PAUSED")
            self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #d97706;")

    @Slot()
    def _on_stop_playback(self) -> None:
        self.worker.pause()
        self.worker.seek(0)
        self.seek_slider.setValue(0)
        self.lbl_status.setText("STATUS: STOPPED")
        self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #64748b;")

    @Slot()
    def _on_seek_pressed(self) -> None:
        self._user_seeking = True

    @Slot()
    def _on_seek_released(self) -> None:
        self._user_seeking = False
        self.worker.seek(self.seek_slider.value())

    @Slot(int)
    def _on_seek_value_changed(self, val: int) -> None:
        if self._user_seeking:
            self.worker.seek(val)

    @Slot(str)
    def _on_error(self, err: str) -> None:
        QMessageBox.warning(self, "Video Playback Error", err)

    def closeEvent(self, event) -> None:
        self.worker.stop()
        super().closeEvent(event)

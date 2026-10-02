"""Main application window for SAFE SIGHT AI desktop platform."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.config.settings import DB_PATH, EVIDENCE_DIR, MODEL_PATH
from src.core.model_manager import best_device, device_label, load_model
from src.desktop.views.dashboard_view import DashboardView
from src.desktop.views.evidence_view import EvidenceView
from src.desktop.views.image_view import ImageView
from src.desktop.views.live_feed_view import LiveFeedView
from src.desktop.views.settings_view import SettingsView
from src.desktop.views.video_review_view import VideoReviewView
from src.desktop.workers.video_worker import VideoWorker
from src.storage.evidence import EvidenceManager
from src.video.pipeline import TelemetryState, VideoPipeline

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """SAFE SIGHT AI primary desktop window matching the original Streamlit application."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SAFE SIGHT AI · Industrial PPE Compliance Platform")
        self.setMinimumSize(1200, 750)
        self.resize(1440, 920)

        # Initialize AI engine and backend subsystems
        self._init_backend()

        # Build UI layout and views
        self._init_ui()
        self._connect_signals()

        # Clock timer for top bar
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(1000)
        self._update_clock()

    def _init_backend(self) -> None:
        """Initialize core AI pipeline, models, and evidence storage."""
        self.device_str = best_device()
        self.dev_label = device_label(self.device_str)

        try:
            self.model = load_model(str(MODEL_PATH), device=self.device_str)
            logger.info("Loaded YOLO model from %s on %s", MODEL_PATH, self.device_str)
        except Exception as exc:
            logger.warning("Could not load weights from %s: %s (running fallback mode)", MODEL_PATH, exc)
            self.model = None

        self.telemetry_state = TelemetryState()
        self.pipeline = VideoPipeline(
            model=self.model,
            state=self.telemetry_state,
            device=self.device_str,
        )
        self.evidence_mgr = EvidenceManager(storage_dir=EVIDENCE_DIR, db_path=DB_PATH)
        self.video_worker = VideoWorker(pipeline=self.pipeline, parent=self)

    def _init_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ----------------- SIDEBAR -----------------
        sidebar_frame = QWidget()
        sidebar_frame.setObjectName("sidebarContainer")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(14, 18, 14, 16)
        sidebar_layout.setSpacing(14)

        # Brand / Logo Header matching Streamlit render_sidebar_header
        brand_box = QHBoxLayout()
        brand_box.setSpacing(12)
        brand_box.setContentsMargins(4, 0, 4, 8)

        shield_icon = QLabel("🛡️")
        shield_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shield_icon.setStyleSheet("""
            background-color: #eaf7f1;
            font-size: 24px;
            border-radius: 10px;
            min-width: 44px;
            max-width: 44px;
            min-height: 44px;
            max-height: 44px;
        """)
        brand_box.addWidget(shield_icon)

        brand_titles = QVBoxLayout()
        brand_titles.setSpacing(1)
        lbl_brand_name = QLabel("SAFE SIGHT <span style='color: #047857;'>AI</span>")
        lbl_brand_name.setTextFormat(Qt.TextFormat.RichText)
        lbl_brand_name.setStyleSheet("font-size: 18px; font-weight: 800; color: #111827; letter-spacing: -0.5px;")
        brand_titles.addWidget(lbl_brand_name)

        lbl_brand_tag = QLabel("VISION THAT PROTECTS.")
        lbl_brand_tag.setStyleSheet("font-size: 9.5px; font-weight: 700; color: #64748b; letter-spacing: 1.5px;")
        brand_titles.addWidget(lbl_brand_tag)
        brand_box.addLayout(brand_titles)

        sidebar_layout.addLayout(brand_box)

        # Navigation List (5 pages matching original Streamlit NAV_PAGES)
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navSidebar")

        nav_items = [
            ("📹  Live Feed", "Live shopfloor camera stream & real-time PPE tracking"),
            ("🎬  Video File", "Recorded video analysis & timeline scrub"),
            ("🖼️  Image Analysis", "Static photo inspection & single-frame audit"),
            ("📋  Evidence Log", "Forensic violation history & evidence archive"),
            ("⚙️  System Settings", "Neural thresholds, mandatory PPE & zones"),
        ]

        for title, tooltip in nav_items:
            item = QListWidgetItem(title)
            item.setToolTip(tooltip)
            self.nav_list.addItem(item)

        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_navigation_changed)
        sidebar_layout.addWidget(self.nav_list, 1)

        # User Profile Card matching Streamlit render_sidebar_profile
        profile_frame = QFrame()
        profile_frame.setStyleSheet("""
            QFrame {
                background-color: #f8fafc;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 8px 12px;
            }
        """)
        pf_layout = QHBoxLayout(profile_frame)
        pf_layout.setContentsMargins(4, 4, 4, 4)
        pf_layout.setSpacing(10)

        avatar = QLabel("JD")
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet("""
            background-color: #047857;
            color: #ffffff;
            font-size: 11px;
            font-weight: 800;
            border-radius: 15px;
            min-width: 30px;
            max-width: 30px;
            min-height: 30px;
            max-height: 30px;
        """)
        pf_layout.addWidget(avatar)

        p_info = QVBoxLayout()
        p_info.setSpacing(1)
        lbl_pname = QLabel("Jamie Davis")
        lbl_pname.setStyleSheet("font-size: 12px; font-weight: 700; color: #111827;")
        p_info.addWidget(lbl_pname)
        lbl_prole = QLabel("Safety Director · Admin")
        lbl_prole.setStyleSheet("font-size: 10px; color: #64748b; font-weight: 500;")
        p_info.addWidget(lbl_prole)
        pf_layout.addLayout(p_info)

        sidebar_layout.addWidget(profile_frame)
        main_layout.addWidget(sidebar_frame)

        # ----------------- CONTENT AREA -----------------
        content_frame = QWidget()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Floating Top Navigation Header Bar matching render_safesight_topbar
        top_header = QFrame()
        top_header.setObjectName("safesightTopBar")
        top_header.setStyleSheet("""
            QFrame#safesightTopBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e5e7eb;
                padding: 10px 24px;
            }
        """)
        th_layout = QHBoxLayout(top_header)
        th_layout.setContentsMargins(0, 0, 0, 0)

        tb_brand = QHBoxLayout()
        tb_brand.setSpacing(8)
        tb_logo = QLabel("🛡️")
        tb_logo.setStyleSheet("font-size: 18px;")
        tb_brand.addWidget(tb_logo)

        tb_text = QVBoxLayout()
        tb_text.setSpacing(0)
        tb_name = QLabel("SAFE SIGHT <span style='color: #047857;'>AI</span>")
        tb_name.setTextFormat(Qt.TextFormat.RichText)
        tb_name.setStyleSheet("font-size: 14px; font-weight: 800; color: #111827; letter-spacing: -0.3px;")
        tb_text.addWidget(tb_name)
        tb_tag = QLabel("VISION THAT PROTECTS.")
        tb_tag.setStyleSheet("font-size: 8.5px; font-weight: 700; color: #64748b; letter-spacing: 1.2px;")
        tb_text.addWidget(tb_tag)
        tb_brand.addLayout(tb_text)
        th_layout.addLayout(tb_brand)

        th_layout.addStretch()

        self.lbl_clock = QLabel("")
        self.lbl_clock.setStyleSheet("font-size: 12px; font-weight: 600; color: #64748b; margin-right: 12px;")
        th_layout.addWidget(self.lbl_clock)

        self.badge_global = QLabel("● System operational")
        self.badge_global.setStyleSheet("""
            background-color: #eaf7f1;
            color: #047857;
            font-size: 11.5px;
            font-weight: 700;
            padding: 5px 12px;
            border-radius: 12px;
            border: 1px solid #a7f3d0;
        """)
        th_layout.addWidget(self.badge_global)

        content_layout.addWidget(top_header)

        # Stacked Views (5 pages matching original Streamlit NAV_PAGES)
        self.stack = QStackedWidget()

        self.view_live = LiveFeedView(
            pipeline=self.pipeline,
            video_worker=self.video_worker,
            evidence_mgr=self.evidence_mgr,
            parent=self,
        )
        self.view_video = VideoReviewView(pipeline=self.pipeline, parent=self)
        self.view_image = ImageView(pipeline=self.pipeline, parent=self)
        self.view_evidence = EvidenceView(evidence_mgr=self.evidence_mgr, parent=self)
        self.view_settings = SettingsView(
            pipeline=self.pipeline,
            evidence_mgr=self.evidence_mgr,
            parent=self,
        )
        # Keep dashboard view available for standalone/programmatic access
        self.view_dashboard = DashboardView(
            pipeline=self.pipeline,
            evidence_mgr=self.evidence_mgr,
            device_label=self.dev_label,
            parent=self,
        )

        self.stack.addWidget(self.view_live)  # 0: Live Feed
        self.stack.addWidget(self.view_video)  # 1: Video File
        self.stack.addWidget(self.view_image)  # 2: Image Analysis
        self.stack.addWidget(self.view_evidence)  # 3: Evidence Log
        self.stack.addWidget(self.view_settings)  # 4: System Settings

        content_layout.addWidget(self.stack, 1)

        # Enterprise Footer Bar matching Streamlit app.py lines 1314-1326
        footer_bar = QFrame()
        footer_bar.setObjectName("appFooter")
        footer_bar.setStyleSheet("""
            QFrame#appFooter {
                background-color: #ffffff;
                border-top: 1px solid #e5e7eb;
                padding: 8px 24px;
            }
        """)
        fb_layout = QHBoxLayout(footer_bar)
        fb_layout.setContentsMargins(0, 0, 0, 0)

        lbl_foot_left = QLabel(
            "<span style='color: #047857; font-weight: 800;'>SAFE SIGHT AI</span>  ·  <span style='color: #64748b; font-weight: 500;'>Shopfloor Vision & Safety Intelligence Platform</span>"
        )
        lbl_foot_left.setTextFormat(Qt.TextFormat.RichText)
        lbl_foot_left.setStyleSheet("font-size: 11px;")
        fb_layout.addWidget(lbl_foot_left)

        fb_layout.addStretch()

        lbl_foot_right = QLabel(
            "Model: <strong style='color: #111827;'>Custom PPE Neural Checkpoint</strong> · <span style='color: #047857; font-weight: 600;'>Production Certified</span>"
        )
        lbl_foot_right.setTextFormat(Qt.TextFormat.RichText)
        lbl_foot_right.setStyleSheet("font-size: 11px; color: #64748b;")
        fb_layout.addWidget(lbl_foot_right)

        content_layout.addWidget(footer_bar)
        main_layout.addWidget(content_frame, 1)

    def _connect_signals(self) -> None:
        # Keep dashboard KPI cards synchronized even when user views other tabs
        self.video_worker.telemetry_updated.connect(self.view_dashboard.update_telemetry)

    @Slot(int)
    def _on_navigation_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)

        # If navigating to evidence view, auto-refresh recent database rows
        if index == 3:
            self.view_evidence.refresh_events()

        # Stop hardware camera when navigating away from Live Feed (index 0)
        if index != 0 and self.video_worker.isRunning():
            self.view_live._on_stop_clicked()

    @Slot()
    def _update_clock(self) -> None:
        now_str = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        self.lbl_clock.setText(now_str)

    def closeEvent(self, event) -> None:
        """Gracefully terminate background inference threads and camera hardware."""
        logger.info("Shutting down SAFE SIGHT AI desktop application...")
        if self.video_worker.isRunning():
            self.video_worker.stop_camera()
        if hasattr(self.view_video, "worker") and self.view_video.worker.isRunning():
            self.view_video.worker.stop()
        super().closeEvent(event)

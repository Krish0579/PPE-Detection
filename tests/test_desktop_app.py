"""Comprehensive test suite for SAFE SIGHT AI PySide6 Desktop Application."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QMessageBox

# Ensure headless Qt offscreen platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from src.core.ppe_associator import WorkerStatus
from src.desktop.main_window import MainWindow
from src.desktop.views.dashboard_view import DashboardView
from src.desktop.views.evidence_view import EvidenceView
from src.desktop.views.image_view import ImageView
from src.desktop.views.settings_view import SettingsView
from src.desktop.widgets.alert_panel import AlertPanel
from src.desktop.widgets.camera_selector import CameraSelector
from src.desktop.widgets.detection_panel import DetectionPanel
from src.desktop.widgets.metric_card import MetricCard
from src.desktop.widgets.status_badge import StatusBadge
from src.desktop.widgets.video_display import VideoDisplayWidget
from src.storage.evidence import EvidenceManager
from src.video.pipeline import TelemetryState, VideoPipeline


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single persistent QApplication instance in offscreen mode."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["--platform", "offscreen"])
    return app


@pytest.fixture(autouse=True)
def mock_message_boxes(monkeypatch):
    """Prevent modal popups from blocking or crashing in headless tests."""
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)


@pytest.fixture
def dummy_pipeline():
    """Create a headless VideoPipeline with mock YOLO."""
    mock_model = MagicMock()
    mock_model.predict.return_value = []
    mock_model.names = {0: "Person", 1: "helmet", 2: "vest"}
    state = TelemetryState()
    return VideoPipeline(model=mock_model, state=state, device="cpu")


@pytest.fixture
def temp_evidence_mgr(tmp_path):
    """Create an isolated EvidenceManager backed by a temporary directory."""
    db_file = tmp_path / "test_ppe_events.db"
    return EvidenceManager(storage_dir=tmp_path / "evidence", db_path=db_file)


class TestDesktopWidgets:
    """Test custom UI components in src/desktop/widgets/."""

    def test_metric_card(self, qapp):
        card = MetricCard("Compliant Workers", "42", "Full gear", color="green")
        assert card.lbl_title.text() == "COMPLIANT WORKERS"
        assert card.lbl_value.text() == "42"
        card.set_value("99")
        assert card.lbl_value.text() == "99"

    def test_status_badge(self, qapp):
        badge = StatusBadge(status="safe", text="COMPLIANT")
        assert "SAFE" in badge.text() or "COMPLIANT" in badge.text()
        badge.set_status("violation", "ALERT")
        assert "ALERT" in badge.text()
        badge.set_status("live", "MONITORING")
        assert "MONITORING" in badge.text()

    def test_camera_selector(self, qapp):
        selector = CameraSelector()
        assert selector.combo.count() >= 1
        curr = selector.current_device()
        assert isinstance(curr, int)

    def test_video_display_widget(self, qapp):
        display = VideoDisplayWidget(placeholder_text="Standby")
        assert display.placeholder_text == "Standby"
        q_img = QImage(320, 240, QImage.Format.Format_RGB888)
        q_img.fill(Qt.GlobalColor.black)
        display.set_image(q_img)
        assert display._image is not None
        display.clear()
        assert display._image is None

    def test_detection_panel(self, qapp):
        panel = DetectionPanel()
        assert panel.lbl_count.text() == "0 Active"

        w1 = WorkerStatus(worker_id=1, box=(0, 0, 100, 200), helmet_status="COMPLIANT", zone="Zone A")
        w2 = WorkerStatus(worker_id=2, box=(10, 10, 100, 200), helmet_status="VIOLATION", zone="Zone B", violations=["no_helmet"])

        panel.update_workers([w1, w2])
        assert panel.lbl_count.text() == "2 Active"

        panel.update_workers([])
        assert panel.lbl_count.text() == "0 Active"

    def test_alert_panel(self, qapp):
        panel = AlertPanel()
        assert panel.lbl_count.text() == "0 Issues"

        incidents = [
            {"person_name": "Worker #2", "missing_ppe": {"helmet", "vest"}, "zone": "Zone B"}
        ]
        panel.update_alerts(incidents)
        assert "1 Critical" in panel.lbl_count.text()

        panel.update_alerts([])
        assert "0 Issues" in panel.lbl_count.text()


class TestDesktopViews:
    """Test desktop views and interactions."""

    def test_dashboard_view(self, qapp, dummy_pipeline, temp_evidence_mgr):
        view = DashboardView(dummy_pipeline, temp_evidence_mgr, device_label="CPU Test")
        assert view.card_workers.lbl_value.text() == "0"

        # Update telemetry
        view.update_telemetry({
            "total_workers": 5,
            "safe_workers": 4,
            "violating_workers": 1,
            "safety_score": 80.0,
        })
        assert view.card_workers.lbl_value.text() == "5"
        assert view.card_compliant.lbl_value.text() == "4"
        assert view.card_violations.lbl_value.text() == "1"
        assert view.card_score.lbl_value.text() == "80.0%"

    def test_evidence_view(self, qapp, temp_evidence_mgr):
        # Insert dummy event into SQLite
        dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        temp_evidence_mgr.save_snapshot(dummy_frame, violating_labels=["no_helmet"], person_id=7)

        view = EvidenceView(temp_evidence_mgr)
        assert view.table.rowCount() >= 1

        # Test search filter
        view.txt_search.setText("no_helmet")
        assert view.table.rowCount() >= 1

        view.txt_search.setText("non_existent_query_xyz")
        assert view.table.rowCount() == 0

    def test_settings_view(self, qapp, dummy_pipeline, temp_evidence_mgr):
        view = SettingsView(dummy_pipeline, temp_evidence_mgr)
        view.slider_conf.setValue(40)
        view.slider_iou.setValue(50)
        view.chk_ppe["helmet"].setChecked(True)
        view.chk_ppe["vest"].setChecked(False)

        # Apply settings without modal dialog
        view._on_apply_settings(notify=False)

        conf, iou, _, _, _, _, _, _, req = dummy_pipeline.state.get_config()
        assert conf == pytest.approx(0.40, abs=0.01)
        assert iou == pytest.approx(0.50, abs=0.01)
        assert req["helmet"] is True
        assert req["vest"] is False

    def test_image_view_audit(self, qapp, dummy_pipeline, tmp_path):
        view = ImageView(dummy_pipeline)
        img_path = tmp_path / "test_frame.png"
        test_img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.imwrite(str(img_path), test_img)

        view.audit_image(img_path)
        assert view._current_annotated is not None
        assert view.btn_save.isEnabled()


class TestMainWindowIntegration:
    """Test full MainWindow assembly and view switching."""

    def test_main_window_startup_and_navigation(self, qapp, tmp_path):
        window = MainWindow()
        assert window.stack.count() == 5
        assert window.nav_list.count() == 5

        # Switch through all 5 pages matching original Streamlit NAV_PAGES
        for idx in range(5):
            window.nav_list.setCurrentRow(idx)
            assert window.stack.currentIndex() == idx

        # Close and teardown cleanly
        window.close()

"""System configuration, PPE safety policy, and neural sensitivity settings view matching Screenshot 5."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.config.settings import (
    ALLOW_EXTERNAL_MODEL_PATH,
    MODEL_DIR,
    MODEL_PATH,
)
from src.core.model_manager import available_devices, device_label, load_model
from src.core.validation import UploadValidationError, validate_model_path
from src.desktop.widgets.status_badge import StatusBadge
from src.storage.evidence import EvidenceManager
from src.video.pipeline import VideoPipeline

logger = logging.getLogger(__name__)


class SettingsView(QWidget):
    """Operator configuration view matching Screenshot 5."""

    def __init__(
        self,
        pipeline: VideoPipeline,
        evidence_mgr: EvidenceManager,
        parent=None,
    ):
        super().__init__(parent)
        self.pipeline = pipeline
        self.evidence_mgr = evidence_mgr
        self._current_weights_path = str(MODEL_PATH)

        self._init_ui()
        self._load_current_values()

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

        lbl_eyebrow = QLabel("● SYSTEM CONFIGURATION / ADMIN CONTROLS")
        lbl_eyebrow.setObjectName("pageEyebrow")
        title_vbox.addWidget(lbl_eyebrow)

        lbl_title = QLabel("Workspace & Vision Engine Settings")
        lbl_title.setObjectName("pageTitle")
        title_vbox.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Configure model weights, hardware compute accelerators, per-class confidence thresholds, and PPE policy."
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

        self.btn_apply = QPushButton("Apply Settings")
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #047857;
                color: #ffffff;
                font-weight: 700;
                padding: 7px 18px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #065f46; }
        """)
        self.btn_apply.clicked.connect(self._on_apply_settings)
        pills_row.addWidget(self.btn_apply)

        hc_layout.addLayout(pills_row)
        main_layout.addWidget(header_container)

        # Scrollable Form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(24)

        # ----------------- LEFT COLUMN: Neural Model Checkpoint -----------------
        left_col = QWidget()
        l_layout = QVBoxLayout(left_col)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.setSpacing(14)

        lbl_sec_model = QLabel("Neural Model Checkpoint")
        lbl_sec_model.setStyleSheet("font-size: 15px; font-weight: 800; color: #0f172a;")
        l_layout.addWidget(lbl_sec_model)

        self.lbl_active_path = QLabel(f"Active model path: {self._current_weights_path}")
        self.lbl_active_path.setStyleSheet("font-size: 11.5px; font-weight: 600; color: #047857;")
        l_layout.addWidget(self.lbl_active_path)

        # Custom Weights Path Input
        lbl_cwp = QLabel("Custom Weights Path (.pt)")
        lbl_cwp.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #374151;")
        l_layout.addWidget(lbl_cwp)

        self.txt_weights = QLineEdit(self._current_weights_path)
        l_layout.addWidget(self.txt_weights)

        btn_apply_weights = QPushButton("Apply Model Weights")
        btn_apply_weights.setStyleSheet("padding: 7px 14px; font-weight: 600;")
        btn_apply_weights.clicked.connect(self._on_apply_custom_path)
        l_layout.addWidget(btn_apply_weights)

        # Upload Trained .pt Weights Box matching Screenshot 5
        lbl_up_title = QLabel("Upload Trained .pt Weights")
        lbl_up_title.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #374151; margin-top: 6px;")
        l_layout.addWidget(lbl_up_title)

        upload_card = QFrame()
        upload_card.setObjectName("uploaderCard")
        uc_layout = QHBoxLayout(upload_card)
        uc_layout.setContentsMargins(16, 12, 16, 12)
        uc_layout.setSpacing(12)

        cloud_icon = QLabel("☁️")
        cloud_icon.setStyleSheet("font-size: 28px;")
        uc_layout.addWidget(cloud_icon)

        text_vbox = QVBoxLayout()
        text_vbox.setSpacing(2)
        lbl_drop = QLabel("Drag and drop file here")
        lbl_drop.setStyleSheet("font-size: 13px; font-weight: 700; color: #1e293b;")
        text_vbox.addWidget(lbl_drop)

        lbl_limit = QLabel("Limit 500MB per file · PT")
        lbl_limit.setStyleSheet("font-size: 11px; color: #64748b;")
        text_vbox.addWidget(lbl_limit)
        uc_layout.addLayout(text_vbox)
        uc_layout.addStretch()

        btn_browse = QPushButton("Browse files")
        btn_browse.clicked.connect(self._on_browse_weights)
        uc_layout.addWidget(btn_browse)
        l_layout.addWidget(upload_card)

        # Hardware Accelerator
        lbl_hw = QLabel("Inference Compute Device")
        lbl_hw.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #374151; margin-top: 6px;")
        l_layout.addWidget(lbl_hw)

        self.cmb_device = QComboBox()
        devs = available_devices()
        for d in devs:
            self.cmb_device.addItem(f"{device_label(d)} ({d})", d)
        l_layout.addWidget(self.cmb_device)

        self.chk_half = QCheckBox("Enable FP16 Half-Precision (GPU acceleration)")
        self.chk_half.setChecked(self.pipeline.half)
        l_layout.addWidget(self.chk_half)

        self.chk_mirror = QCheckBox("Mirror Camera Stream (horizontal flip)")
        self.chk_autocapture = QCheckBox("Auto-Capture Evidence Frames upon Violation Detection")
        self.chk_autocapture.setChecked(True)
        l_layout.addWidget(self.chk_mirror)
        l_layout.addWidget(self.chk_autocapture)

        l_layout.addStretch()
        c_layout.addWidget(left_col, 1)

        # ----------------- RIGHT COLUMN: Calibration & PPE Policy -----------------
        right_col = QWidget()
        r_layout = QVBoxLayout(right_col)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(14)

        lbl_sec_cal = QLabel("Inference Threshold Calibration")
        lbl_sec_cal.setStyleSheet("font-size: 15px; font-weight: 800; color: #0f172a;")
        r_layout.addWidget(lbl_sec_cal)

        # Master Detection Confidence Floor matching Screenshot 5
        lbl_mcf = QLabel("Master Detection Confidence Floor")
        lbl_mcf.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #374151;")
        r_layout.addWidget(lbl_mcf)

        self.lbl_conf_val = QLabel("0.25")
        self.lbl_conf_val.setStyleSheet("font-size: 12px; font-weight: 700; color: #ef4444; margin-left: 2px;")
        r_layout.addWidget(self.lbl_conf_val)

        self.slider_conf = QSlider(Qt.Orientation.Horizontal)
        self.slider_conf.setRange(5, 95)
        self.slider_conf.valueChanged.connect(lambda v: self.lbl_conf_val.setText(f"{v / 100:.2f}"))
        r_layout.addWidget(self.slider_conf)

        # IoU NMS Overlap Floor matching Screenshot 5
        lbl_iou = QLabel("IoU NMS Overlap Floor")
        lbl_iou.setStyleSheet("font-size: 12.5px; font-weight: 600; color: #374151; margin-top: 6px;")
        r_layout.addWidget(lbl_iou)

        self.lbl_iou_val = QLabel("0.45")
        self.lbl_iou_val.setStyleSheet("font-size: 12px; font-weight: 700; color: #ef4444; margin-left: 2px;")
        r_layout.addWidget(self.lbl_iou_val)

        self.slider_iou = QSlider(Qt.Orientation.Horizontal)
        self.slider_iou.setRange(5, 95)
        self.slider_iou.valueChanged.connect(lambda v: self.lbl_iou_val.setText(f"{v / 100:.2f}"))
        r_layout.addWidget(self.slider_iou)

        # Per-class sliders collapsible / card
        lbl_per_class = QLabel("🎛️ Per-Class Confidence Floor Sliders")
        lbl_per_class.setStyleSheet("font-size: 13px; font-weight: 700; color: #475569; margin-top: 10px;")
        r_layout.addWidget(lbl_per_class)

        self.class_sliders: dict[str, tuple[QSlider, QLabel]] = {}
        for gear, default_val in [
            ("helmet", 0.30),
            ("vest", 0.30),
            ("boots", 0.25),
            ("gloves", 0.20),
            ("goggles", 0.20),
        ]:
            row = QHBoxLayout()
            lbl_g = QLabel(f"{gear.title()}:")
            lbl_g.setFixedWidth(70)
            lbl_g.setStyleSheet("font-size: 12px; color: #475569;")
            row.addWidget(lbl_g)

            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setRange(5, 90)
            sl.setValue(int(default_val * 100))
            lbl_v = QLabel(f"{default_val:.2f}")
            lbl_v.setFixedWidth(36)
            lbl_v.setStyleSheet("font-size: 11px; font-weight: 700; color: #ef4444;")
            sl.valueChanged.connect(lambda v, l=lbl_v: l.setText(f"{v / 100:.2f}"))
            row.addWidget(sl)
            row.addWidget(lbl_v)
            r_layout.addLayout(row)
            self.class_sliders[gear] = (sl, lbl_v)

        # Mandatory PPE Policy Checks matching Screenshot 5
        lbl_sec_pol = QLabel("Mandatory PPE Policy Checks")
        lbl_sec_pol.setStyleSheet("font-size: 15px; font-weight: 800; color: #0f172a; margin-top: 12px;")
        r_layout.addWidget(lbl_sec_pol)

        lbl_pol_sub = QLabel("Select which items are mandatory for personnel safety compliance:")
        lbl_pol_sub.setStyleSheet("font-size: 11.5px; color: #64748b;")
        r_layout.addWidget(lbl_pol_sub)

        self.chk_ppe = {}
        for gear, title in [
            ("helmet", "Safety Helmet (Hardhat)"),
            ("vest", "High-Visibility Safety Vest"),
            ("boots", "Steel-Toe Safety Boots"),
            ("gloves", "Protective Gloves"),
            ("goggles", "Safety Goggles (Eye Protection)"),
        ]:
            chk = QCheckBox(title)
            chk.setChecked(True)
            self.chk_ppe[gear] = chk
            r_layout.addWidget(chk)

        # Physical Zones Section matching Screenshot 5
        lbl_sec_zone = QLabel("Shopfloor Physical Zones")
        lbl_sec_zone.setStyleSheet("font-size: 15px; font-weight: 800; color: #0f172a; margin-top: 12px;")
        r_layout.addWidget(lbl_sec_zone)

        zone_card = QFrame()
        zone_card.setObjectName("observationStrip")
        zc_layout = QVBoxLayout(zone_card)
        zc_layout.setContentsMargins(12, 10, 12, 10)
        lbl_z1 = QLabel("● Assembly Line A (Standard) · Capacity: 6 workers")
        lbl_z1.setStyleSheet("font-size: 12px; font-weight: 600; color: #047857;")
        lbl_z2 = QLabel("● Heavy Machinery Bay (Restricted) · Capacity: 2 workers")
        lbl_z2.setStyleSheet("font-size: 12px; font-weight: 600; color: #b91c1c;")
        zc_layout.addWidget(lbl_z1)
        zc_layout.addWidget(lbl_z2)
        r_layout.addWidget(zone_card)

        r_layout.addStretch()
        c_layout.addWidget(right_col, 1)

        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

    def _load_current_values(self) -> None:
        (
            conf,
            iou,
            class_conf,
            _mode_key,
            auto_capture,
            mirror,
            _show_hud,
            _assoc_workers,
            req_ppe,
        ) = self.pipeline.state.get_config()

        self.slider_conf.setValue(int(conf * 100))
        self.lbl_conf_val.setText(f"{conf:.2f}")

        self.slider_iou.setValue(int(iou * 100))
        self.lbl_iou_val.setText(f"{iou:.2f}")

        for gear, (sl, lbl) in self.class_sliders.items():
            val = class_conf.get(gear, 0.25)
            sl.setValue(int(val * 100))
            lbl.setText(f"{val:.2f}")

        for gear, chk in self.chk_ppe.items():
            chk.setChecked(req_ppe.get(gear, True))

        self.chk_mirror.setChecked(mirror)
        self.chk_autocapture.setChecked(auto_capture)

    @Slot()
    def _on_apply_custom_path(self) -> None:
        path_str = self.txt_weights.text().strip()
        if not path_str:
            QMessageBox.warning(self, "Invalid Path", "No model path specified.")
            return

        try:
            validated_path = validate_model_path(path_str, MODEL_DIR, allow_external_paths=ALLOW_EXTERNAL_MODEL_PATH)
        except UploadValidationError as exc:
            QMessageBox.warning(self, "Path Rejected", f"Model path rejected:\n{exc}")
            return

        try:
            new_model = load_model(
                str(validated_path), device=self.cmb_device.currentData(), half=self.chk_half.isChecked()
            )
            self.pipeline.model = new_model
            self._current_weights_path = path_str
            self.lbl_active_path.setText(f"Active model path: {path_str}")
            QMessageBox.information(self, "Model Applied", f"Active weights successfully updated:\n{path_str}")
        except Exception as exc:
            logger.error("Failed to load model weights: %s", exc)
            QMessageBox.critical(self, "Model Load Error", f"Could not load weights:\n{exc}")

    @Slot()
    def _on_browse_weights(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select YOLO Weights Checkpoint",
            "",
            "PyTorch Weights (*.pt)",
        )
        if not file_path:
            return

        self.txt_weights.setText(file_path)
        self._on_apply_custom_path()

    @Slot()
    def _on_apply_settings(self, notify: bool = True) -> None:
        conf = self.slider_conf.value() / 100.0
        iou = self.slider_iou.value() / 100.0

        class_conf = {gear: sl.value() / 100.0 for gear, (sl, _) in self.class_sliders.items()}

        req_ppe = {gear: chk.isChecked() for gear, chk in self.chk_ppe.items()}

        mirror = self.chk_mirror.isChecked()
        auto_capture = self.chk_autocapture.isChecked()

        self.pipeline.state.update_config(
            conf=conf,
            iou=iou,
            class_conf=class_conf,
            auto_capture=auto_capture,
            mirror=mirror,
            required_ppe=req_ppe,
        )

        selected_dev = self.cmb_device.currentData()
        self.pipeline.device = selected_dev
        self.pipeline.half = self.chk_half.isChecked()

        if notify:
            QMessageBox.information(
                self, "Settings Applied", "Safety policies and detection parameters updated successfully."
            )

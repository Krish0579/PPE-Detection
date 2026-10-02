"""Hardware camera device selector with auto-enumeration."""

from __future__ import annotations

import cv2
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget


class CameraSelector(QWidget):
    """Camera device selector widget with live hardware probing."""

    device_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl = QLabel("Video Source:")
        lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #cbd5e1;")
        layout.addWidget(lbl)

        self.combo = QComboBox()
        self.combo.setMinimumWidth(180)
        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo)

        self.btn_refresh = QPushButton("🔄 Scan")
        self.btn_refresh.setToolTip("Scan local USB & built-in video capture devices")
        self.btn_refresh.clicked.connect(self.scan_devices)
        layout.addWidget(self.btn_refresh)

        self.scan_devices()

    def scan_devices(self) -> None:
        """Probe available camera devices (indices 0..3) safely."""
        self.combo.blockSignals(True)
        self.combo.clear()

        found_any = False
        # Quick non-blocking probe of first 3 indices
        for idx in range(3):
            cap = cv2.VideoCapture(idx)
            if cap is not None and cap.isOpened():
                ret, _ = cap.read()
                cap.release()
                if ret:
                    self.combo.addItem(f"Camera {idx} (Hardware USB/Built-in)", idx)
                    found_any = True

        if not found_any:
            # Add index 0 as default option and simulated fallback
            self.combo.addItem("Camera 0 (Default)", 0)

        self.combo.addItem("Synthetic Shopfloor (Simulation)", -1)
        self.combo.blockSignals(False)

    def _on_combo_changed(self, index: int) -> None:
        dev_id = self.combo.currentData()
        if dev_id is not None:
            self.device_changed.emit(int(dev_id))

    def current_device(self) -> int:
        data = self.combo.currentData()
        return int(data) if data is not None else 0

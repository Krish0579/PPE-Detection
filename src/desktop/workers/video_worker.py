"""QThread worker for real-time video capture and neural inference."""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from src.core.metrics import summarise_workers
from src.video.camera import OpenCVCameraManager
from src.video.pipeline import VideoPipeline

logger = logging.getLogger(__name__)


class VideoWorker(QThread):
    """Asynchronous worker that drives camera frame capture, YOLO inference, and UI signal dispatch."""

    frame_ready = Signal(QImage)
    telemetry_updated = Signal(dict)
    workers_updated = Signal(list)
    status_changed = Signal(bool, str)
    error_occurred = Signal(str)

    def __init__(
        self,
        pipeline: VideoPipeline,
        camera_manager: OpenCVCameraManager | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.pipeline = pipeline
        self.camera_manager = camera_manager or OpenCVCameraManager.get_instance()
        self._running = False
        self._device_index = 0
        self._target_fps = 30.0

    def start_camera(self, device_index: int = 0) -> None:
        """Start the worker thread with specified camera device index."""
        self._device_index = device_index
        if not self.isRunning():
            self._running = True
            self.start()

    def stop_camera(self) -> None:
        """Stop worker cleanly and release hardware."""
        self._running = False
        self.wait(1500)
        if self.camera_manager.is_running:
            self.camera_manager.stop()
        self.status_changed.emit(False, "Camera stopped")

    def run(self) -> None:
        """Worker thread main loop."""
        try:
            # Start OpenCVCameraManager
            if self._device_index == -1:
                # Force simulation
                self.camera_manager.start(device_index=0, pipeline_ref=self.pipeline, allow_simulation_fallback=True)
            else:
                self.camera_manager.start(
                    device_index=self._device_index, pipeline_ref=self.pipeline, allow_simulation_fallback=True
                )

            is_sim = self.camera_manager.is_simulated
            status_text = "Simulated feed active" if is_sim else f"Camera {self._device_index} active"
            self.status_changed.emit(True, status_text)

            frame_interval = 1.0 / self._target_fps

            while self._running:
                t0 = time.perf_counter()

                # Get latest frame from camera manager
                raw_frame = self.camera_manager.get_latest_frame()

                if raw_frame is not None and raw_frame.size > 0:
                    # Execute inference pipeline
                    annotated = self.pipeline.process_numpy_frame(raw_frame)

                    # Query telemetry state
                    state_dict = self.pipeline.state.snapshot_ui()
                    workers = state_dict.get("workers", [])
                    fps = self.pipeline.smoothed_fps
                    inf_ms = state_dict.get("inference_ms", 0.0)

                    # Build high-level summary
                    summary = summarise_workers(workers)
                    telemetry = {
                        "fps": fps,
                        "inference_ms": inf_ms,
                        "total_workers": summary.total_workers,
                        "safe_workers": summary.safe_workers,
                        "violating_workers": summary.violating_workers,
                        "safety_score": summary.safety_score,
                        "is_simulated": self.camera_manager.is_simulated,
                    }

                    # Convert BGR numpy array to QImage for thread-safe display
                    h, w, ch = annotated.shape
                    bytes_per_line = ch * w
                    q_img = QImage(annotated.data, w, h, bytes_per_line, QImage.Format.Format_BGR888).copy()

                    # Emit signals to main GUI thread
                    self.frame_ready.emit(q_img)
                    self.telemetry_updated.emit(telemetry)
                    self.workers_updated.emit(workers)

                # Maintain target framerate
                elapsed = time.perf_counter() - t0
                sleep_time = max(0.001, frame_interval - elapsed)
                time.sleep(sleep_time)

        except Exception as exc:
            logger.exception("Error in VideoWorker: %s", exc)
            self.error_occurred.emit(str(exc))
        finally:
            if self.camera_manager.is_running:
                self.camera_manager.stop()
            self.status_changed.emit(False, "Camera offline")

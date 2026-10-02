"""QThread worker for inspecting and scrubbing pre-recorded video files."""

from __future__ import annotations

import logging
import time

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from src.core.metrics import summarise_workers
from src.video.pipeline import VideoPipeline

logger = logging.getLogger(__name__)


class VideoFileWorker(QThread):
    """Playback and frame-by-frame analysis thread for recorded video review."""

    frame_ready = Signal(QImage)
    progress_updated = Signal(int, int)  # current_frame, total_frames
    telemetry_updated = Signal(dict)
    workers_updated = Signal(list)
    state_changed = Signal(bool)  # is_playing
    error_occurred = Signal(str)

    def __init__(self, pipeline: VideoPipeline, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self._video_path: str | None = None
        self._cap: cv2.VideoCapture | None = None
        self._total_frames = 0
        self._fps = 30.0
        self._current_frame = 0
        self._is_playing = False
        self._running = True
        self._seek_target: int | None = None

    def load_video(self, file_path: str) -> bool:
        """Open a video file and initialize metadata."""
        self.pause()
        if self._cap is not None:
            self._cap.release()

        self._video_path = file_path
        self._cap = cv2.VideoCapture(file_path)
        if not self._cap.isOpened():
            self.error_occurred.emit(f"Could not open video file: {file_path}")
            return False

        self._total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self._fps = max(1.0, float(self._cap.get(cv2.CAP_PROP_FPS) or 30.0))
        self._current_frame = 0

        # Show first frame
        self.seek(0)
        return True

    def play(self) -> None:
        """Start playback."""
        if self._cap is not None and self._cap.isOpened():
            self._is_playing = True
            self.state_changed.emit(True)

    def pause(self) -> None:
        """Pause playback."""
        self._is_playing = False
        self.state_changed.emit(False)

    def toggle_play(self) -> None:
        """Toggle play/pause."""
        if self._is_playing:
            self.pause()
        else:
            self.play()

    def seek(self, frame_number: int) -> None:
        """Seek to target frame index."""
        if self._cap is not None and self._cap.isOpened():
            self._seek_target = max(0, min(self._total_frames - 1, frame_number))

    def stop(self) -> None:
        """Clean shutdown."""
        self._running = False
        self._is_playing = False
        self.wait(1000)
        if self._cap is not None:
            self._cap.release()

    def run(self) -> None:
        """Main worker loop."""
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                time.sleep(0.05)
                continue

            # Handle seeking
            if self._seek_target is not None:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, self._seek_target)
                self._current_frame = self._seek_target
                self._seek_target = None
                ret, frame = self._cap.read()
                if ret and frame is not None:
                    self._process_and_emit(frame)
                time.sleep(0.02)
                continue

            # Handle normal playback
            if self._is_playing:
                t0 = time.perf_counter()
                ret, frame = self._cap.read()
                if not ret:
                    # Loop video or pause at end
                    self.pause()
                    continue

                self._current_frame = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
                self._process_and_emit(frame)

                frame_interval = 1.0 / self._fps
                elapsed = time.perf_counter() - t0
                time.sleep(max(0.001, frame_interval - elapsed))
            else:
                time.sleep(0.03)

    def _process_and_emit(self, frame: np.ndarray) -> None:
        """Process frame through pipeline and emit signals."""
        annotated = self.pipeline.process_numpy_frame(frame, force_infer=True)
        state_dict = self.pipeline.state.snapshot_ui()
        workers = state_dict.get("workers", [])
        summary = summarise_workers(workers)

        telemetry = {
            "fps": self.pipeline.smoothed_fps,
            "inference_ms": state_dict.get("inference_ms", 0.0),
            "total_workers": summary.total_workers,
            "safe_workers": summary.safe_workers,
            "violating_workers": summary.violating_workers,
            "safety_score": summary.safety_score,
        }

        h, w, ch = annotated.shape
        bytes_per_line = ch * w
        q_img = QImage(annotated.data, w, h, bytes_per_line, QImage.Format.Format_BGR888).copy()

        self.frame_ready.emit(q_img)
        self.progress_updated.emit(self._current_frame, self._total_frames)
        self.telemetry_updated.emit(telemetry)
        self.workers_updated.emit(workers)

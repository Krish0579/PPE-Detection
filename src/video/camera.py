"""Direct OpenCV camera capture service with decoupled async inference for ultra-smooth 30+ FPS streaming."""

from __future__ import annotations

import logging
import queue
import sys
import threading
import time

import cv2
import numpy as np

from src.core.class_semantics import is_person

logger = logging.getLogger(__name__)


class OpenCVCameraManager:
    """Thread-safe persistent OpenCV camera stream manager with decoupled async neural inference."""

    _instance: OpenCVCameraManager | None = None
    _singleton_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> OpenCVCameraManager:
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self._cap: cv2.VideoCapture | None = None
        self._capture_thread: threading.Thread | None = None
        self._infer_thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_raw_frame: np.ndarray | None = None
        self._latest_annotated_frame: np.ndarray | None = None
        self._infer_queue: queue.Queue = queue.Queue(maxsize=1)
        self._device_index: int = 0
        self._fps: float = 0.0
        self._infer_fps: float = 0.0
        self._frame_count: int = 0
        self._last_error: str = ""
        self._pipeline_ref = None
        self._is_simulated: bool = False
        self._sim_reason: str = ""
        self._allow_simulation_fallback: bool = True
        self._first_frame_event = threading.Event()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running and self._capture_thread is not None and self._capture_thread.is_alive()

    @property
    def is_simulated(self) -> bool:
        with self._lock:
            return self._is_simulated

    @property
    def sim_reason(self) -> str:
        """Human-readable reason why the simulated feed is active (empty if not)."""
        with self._lock:
            return self._sim_reason

    @property
    def fps(self) -> float:
        with self._lock:
            return self._fps

    @property
    def infer_fps(self) -> float:
        with self._lock:
            return self._infer_fps

    @property
    def last_error(self) -> str:
        with self._lock:
            return self._last_error

    def start(self, device_index: int = 0, pipeline_ref=None, allow_simulation_fallback: bool = True) -> bool:
        """Start capturing and processing frames with decoupled async inference."""
        with self._lock:
            if self._running and self._capture_thread is not None and self._capture_thread.is_alive():
                if self._device_index == device_index and (pipeline_ref is None or self._pipeline_ref == pipeline_ref):
                    return True
                self._stop_internal()

            self._device_index = device_index
            self._pipeline_ref = pipeline_ref
            self._allow_simulation_fallback = allow_simulation_fallback
            self._is_simulated = False
            self._sim_reason = ""
            self._last_error = ""
            self._running = True
            self._frame_count = 0
            # Reset FPS counters and drop any frames cached by a previous run —
            # otherwise a failing real-camera attempt would keep displaying the
            # old (possibly simulated) frames as if they were live hardware.
            self._fps = 0.0
            self._infer_fps = 0.0
            self._latest_raw_frame = None
            self._latest_annotated_frame = None
            self._first_frame_event.clear()
            # Drain infer queue
            while not self._infer_queue.empty():
                try:
                    self._infer_queue.get_nowait()
                except Exception:
                    break

            # 1. Start background inference thread
            self._infer_thread = threading.Thread(
                target=self._infer_worker, daemon=True, name=f"OpenCVInferWorker-{device_index}"
            )
            self._infer_thread.start()

            # 2. Start high-frequency camera capture thread
            self._capture_thread = threading.Thread(
                target=self._capture_worker, daemon=True, name=f"OpenCVCameraWorker-{device_index}"
            )
            self._capture_thread.start()
            return True

    def _open_camera(self, index: int) -> cv2.VideoCapture | None:
        """Open camera with Full HD (1080p) or HD (720p) native resolution."""
        backends = [cv2.CAP_AVFOUNDATION, cv2.CAP_ANY] if sys.platform == "darwin" else [cv2.CAP_ANY]
        for backend in backends:
            try:
                cap = cv2.VideoCapture(index, backend) if backend != cv2.CAP_ANY else cv2.VideoCapture(index)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    # Verify camera actually delivers a valid frame
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        return cap
                    cap.release()
            except Exception as e:
                logger.debug("Failed to open camera %d with backend %s: %s", index, backend, e)
        return None

    def _capture_worker(self) -> None:
        """Dedicated high-speed camera acquisition loop running at 30+ FPS."""
        cap = self._open_camera(self._device_index)
        is_simulated = False
        demo_feed = None

        if cap is None:
            if self._allow_simulation_fallback:
                try:
                    from src.video.demo_feed import DemoWorkspaceFeed

                    demo_feed = DemoWorkspaceFeed()
                    is_simulated = True
                    sim_reason = (
                        "macOS denied camera access to the server process (System Settings → Privacy & Security → Camera)"
                        if sys.platform == "darwin"
                        else f"hardware camera {self._device_index} not detected by OpenCV"
                    )
                    with self._lock:
                        self._is_simulated = True
                        self._sim_reason = sim_reason
                        self._last_error = ""
                    logger.info(
                        "Host hardware camera %d not available (%s); falling back to simulated shopfloor stream.",
                        self._device_index,
                        sim_reason,
                    )
                except Exception as exc:
                    with self._lock:
                        self._last_error = f"Camera initialization error: {exc}"
                        self._running = False
                    return
            else:
                hint = (
                    " On macOS this usually means camera permission is denied: System Settings → "
                    "Privacy & Security → Camera → enable the terminal app running Streamlit, then restart, "
                    "or run 'tccutil reset Camera' and start the camera again."
                    if sys.platform == "darwin"
                    else ""
                )
                with self._lock:
                    self._last_error = (
                        f"Hardware Camera {self._device_index} could not be opened by OpenCV on the host.{hint} "
                        "Please use '🌐 Continuous Video Stream (WebRTC)' or '📸 Direct Browser Camera' "
                        "for direct browser camera access."
                    )
                    self._running = False
                return
        else:
            self._cap = cap
            with self._lock:
                self._is_simulated = False
                self._last_error = ""

        last_time = time.perf_counter()

        consecutive_fails = 0
        try:
            while self._running:
                if is_simulated and demo_feed is not None:
                    frame = demo_feed.get_frame()
                else:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        consecutive_fails += 1
                        if consecutive_fails >= 60:  # ~1.5 - 2s of continuous stream drop
                            if self._frame_count == 0:
                                # Device opened but never delivered a frame —
                                # on macOS this is the signature of TCC permission denial.
                                if sys.platform == "darwin":
                                    self._last_error = (
                                        "Camera opened but produced no frames — macOS camera permission is likely "
                                        "denied. Grant access (System Settings → Privacy & Security → Camera) to the "
                                        "terminal app running Streamlit and restart, or run 'tccutil reset Camera' "
                                        "and start the camera again."
                                    )
                                else:
                                    self._last_error = (
                                        f"Camera {self._device_index} opened but produced no frames "
                                        "(driver or permission issue)."
                                    )
                            else:
                                self._last_error = f"Camera {self._device_index} disconnected or signal lost."
                            self._running = False
                            break
                        time.sleep(0.01)
                        continue

                    consecutive_fails = 0

                now = time.perf_counter()
                dt = now - last_time
                last_time = now
                if dt > 0:
                    instant_fps = 1.0 / dt
                    self._fps = 0.90 * self._fps + 0.10 * instant_fps if self._fps > 0 else instant_fps

                self._frame_count += 1

                # Send frame to async inference queue (drop stale frames)
                if self._infer_queue.empty():
                    try:
                        self._infer_queue.put_nowait(frame)
                    except queue.Full:
                        pass

                # Ultra-fast overlay rendering onto current frame using pipeline renderer
                pipe = self._pipeline_ref
                if pipe is not None and hasattr(pipe, "renderer"):
                    try:
                        annotated = pipe.renderer.enhance_visual_clarity(frame.copy(), strength=0.25)
                        state = getattr(pipe, "state", None)
                        show_lbl = getattr(state, "overlay_show_labels", True) if state else True
                        show_brk = getattr(state, "overlay_show_corner_brackets", True) if state else True
                        show_conf = getattr(state, "overlay_show_conf_pct", True) if state else True
                        show_pills = getattr(state, "overlay_show_status_pills", True) if state else True

                        workers_list = pipe.last_workers or []
                        if workers_list:
                            annotated = pipe.renderer.draw_worker_badges(
                                annotated,
                                workers_list,
                                show_labels=show_lbl,
                                show_corner_brackets=show_brk,
                                show_status_pills=show_pills,
                            )
                            # Draw individual PPE boxes
                            ppe_boxes = []
                            ppe_labels = []
                            ppe_scores = []
                            if pipe.last_boxes is not None and len(pipe.last_boxes) > 0:
                                for b, l, s in zip(pipe.last_boxes, pipe.last_labels, pipe.last_scores):
                                    if not is_person(l):
                                        ppe_boxes.append(b)
                                        ppe_labels.append(l)
                                        ppe_scores.append(s)
                            if ppe_boxes:
                                annotated = pipe.renderer.draw_detections(
                                    annotated,
                                    np.array(ppe_boxes, dtype=np.float32),
                                    ppe_labels,
                                    np.array(ppe_scores, dtype=np.float32),
                                    show_conf_pct=show_conf,
                                    show_corner_brackets=show_brk,
                                )
                        else:
                            if pipe.last_boxes is not None and len(pipe.last_boxes) > 0:
                                annotated = pipe.renderer.draw_detections(
                                    annotated,
                                    pipe.last_boxes,
                                    pipe.last_labels,
                                    pipe.last_scores,
                                    show_conf_pct=show_conf,
                                    show_corner_brackets=show_brk,
                                )

                        viol_now = sum(1 for w in workers_list if getattr(w, "has_active_violation", False))
                        work_now = len(workers_list)
                        if not work_now and hasattr(pipe, "last_detections") and pipe.last_detections:
                            viol_now = sum(1 for d in pipe.last_detections if d.get("violation", False))
                            work_now = sum(1 for d in pipe.last_detections if is_person(d.get("label", "")))
                        annotated = pipe.renderer.draw_telemetry_hud(
                            annotated,
                            fps=self._fps,
                            violations_count=viol_now,
                            workers_count=work_now,
                            inference_ms=pipe.state.inference_ms if pipe.state.inference_ms > 0 else 0.0,
                            show_hud=True,
                            simulated=is_simulated,
                        )
                    except Exception:
                        annotated = frame
                else:
                    annotated = frame

                with self._lock:
                    self._latest_raw_frame = frame
                    self._latest_annotated_frame = annotated
                self._first_frame_event.set()

                # Yield to OS scheduler or pace simulated 30 FPS stream
                if is_simulated:
                    time.sleep(0.033)
                else:
                    time.sleep(0.001)

        except Exception as exc:
            with self._lock:
                self._last_error = f"Camera streaming error: {exc}"
            logger.error("Camera capture error: %s", exc)
        finally:
            self._first_frame_event.set()
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            with self._lock:
                self._cap = None
                self._running = False
                self._is_simulated = False
                self._sim_reason = ""

    def _infer_worker(self) -> None:
        """Background asynchronous inference loop running YOLO without blocking camera capture."""
        while self._running:
            try:
                frame = self._infer_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            pipe = self._pipeline_ref
            if pipe is not None and frame is not None:
                t0 = time.perf_counter()
                try:
                    pipe.process_numpy_frame(frame)
                    inf_dt = max(time.perf_counter() - t0, 1e-6)
                    self._infer_fps = (
                        0.85 * self._infer_fps + 0.15 * (1.0 / inf_dt) if self._infer_fps > 0 else (1.0 / inf_dt)
                    )
                except Exception as exc:
                    logger.debug("Inference error: %s", exc)

    def _stop_internal(self) -> None:
        self._running = False
        self._is_simulated = False
        self._sim_reason = ""
        self._first_frame_event.set()
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def stop(self) -> None:
        """Stop camera capture and inference worker threads."""
        with self._lock:
            self._stop_internal()
        if self._capture_thread is not None and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=1.0)
        if self._infer_thread is not None and self._infer_thread.is_alive():
            self._infer_thread.join(timeout=1.0)
        self._capture_thread = None
        self._infer_thread = None

    def get_latest_frame(self) -> np.ndarray | None:
        """Return the latest annotated frame, waiting briefly for first frame if capture just launched."""
        with self._lock:
            frame = self._latest_annotated_frame
            running = self._running
        if frame is None and running:
            self._first_frame_event.wait(timeout=0.25)
            with self._lock:
                frame = self._latest_annotated_frame
        return frame

    def get_raw_frame(self) -> np.ndarray | None:
        """Return the latest raw un-annotated frame, waiting briefly for first frame if capture just launched."""
        with self._lock:
            frame = self._latest_raw_frame
            running = self._running
        if frame is None and running:
            self._first_frame_event.wait(timeout=0.25)
            with self._lock:
                frame = self._latest_raw_frame
        return frame

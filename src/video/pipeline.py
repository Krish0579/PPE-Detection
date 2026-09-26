"""Real-time WebRTC frame processing pipeline and thread-safe telemetry state."""
from __future__ import annotations

import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field

import cv2
import numpy as np
import pandas as pd
from ultralytics import YOLO

from src.config.settings import (
    CAPTURE_COOLDOWN_SEC,
    CONFIDENCE_THRESHOLD,
    DEFAULT_PER_CLASS_CONF,
    EVENT_LOG_LEN,
    HISTORY_LEN,
    IOU_THRESHOLD,
    MAX_SNAPSHOTS,
    PERFORMANCE_MODES,
    VIOLATION_CLEAR_FRAMES,
    VIOLATION_CONFIRM_FRAMES,
)
from src.core.class_semantics import (
    is_boots,
    is_gloves,
    is_goggles,
    is_helmet,
    is_person,
    is_vest,
    is_violation,
)
from src.core.detector import run_inference
from src.core.ppe_associator import WorkerStatus, WorkerTracker, associate_ppe_to_workers
from src.storage.evidence import EvidenceManager
from src.video.renderer import OverlayRenderer


@dataclass
class TelemetryState:
    """Thread-safe state shared between WebRTC worker thread and Streamlit UI."""
    lock: threading.Lock = field(default_factory=threading.Lock)

    # Runtime configuration
    conf: float = CONFIDENCE_THRESHOLD
    iou: float = IOU_THRESHOLD
    class_conf: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PER_CLASS_CONF))
    mode_key: str = "balanced"
    auto_capture: bool = True
    mirror: bool = False
    show_hud: bool = True
    associate_workers: bool = True
    accuracy_boost: bool = False
    crop_refine: bool = False
    required_ppe: dict[str, bool] = field(
        default_factory=lambda: {
            "helmet": True,
            "vest": True,
            "boots": True,
            "gloves": True,
            "goggles": True,
        }
    )
    overlay_show_labels: bool = True
    overlay_show_conf_pct: bool = True
    overlay_show_corner_brackets: bool = True
    overlay_show_status_pills: bool = True

    # Real-time state
    counts: Counter = field(default_factory=Counter)
    detections: list[dict] = field(default_factory=list)
    workers: list[WorkerStatus] = field(default_factory=list)
    fps: float = 0.0
    total_frames: int = 0
    inference_ms: float = 0.0
    last_error: str = ""
    latest_frame: np.ndarray | None = None

    # Alert state machine
    violating: bool = False
    violation_streak: int = 0
    clean_streak: int = 0
    violation_seq: int = 0
    _last_violation_labels: set = field(default_factory=set)

    # History & Evidence
    history: deque = field(default_factory=lambda: deque(maxlen=HISTORY_LEN))
    snapshots: list[dict] = field(default_factory=list)
    last_capture_ts: float = 0.0
    event_log: deque = field(default_factory=lambda: deque(maxlen=EVENT_LOG_LEN))

    def update_config(
        self,
        conf: float,
        iou: float,
        class_conf: dict[str, float] | None = None,
        mode_key: str = "balanced",
        auto_capture: bool = True,
        mirror: bool = False,
        show_hud: bool = True,
        associate_workers: bool = True,
        required_ppe: dict[str, bool] | None = None,
        accuracy_boost: bool | None = None,
        crop_refine: bool | None = None,
    ) -> None:
        with self.lock:
            self.conf = conf
            self.iou = iou
            if class_conf is not None:
                self.class_conf = dict(class_conf)
            self.mode_key = mode_key
            self.auto_capture = auto_capture
            self.mirror = mirror
            self.show_hud = show_hud
            self.associate_workers = associate_workers
            if required_ppe is not None:
                self.required_ppe = dict(required_ppe)
            if accuracy_boost is not None:
                self.accuracy_boost = accuracy_boost
            if crop_refine is not None:
                self.crop_refine = crop_refine

    def get_config(self) -> tuple[float, float, dict[str, float], str, bool, bool, bool, bool, dict[str, bool]]:
        with self.lock:
            return (
                self.conf,
                self.iou,
                dict(self.class_conf),
                self.mode_key,
                self.auto_capture,
                self.mirror,
                self.show_hud,
                self.associate_workers,
                dict(self.required_ppe),
            )

    def publish(
        self,
        counts: Counter,
        detections: list[dict],
        workers: list[WorkerStatus],
        fps: float,
        inference_ms: float,
        violations_count: int,
        frame: np.ndarray | None = None,
    ) -> None:
        now = time.time()
        with self.lock:
            self.counts = Counter(counts)
            self.detections = [dict(d) for d in detections]
            self.workers = list(workers)
            self.fps = fps
            self.inference_ms = inference_ms
            self.total_frames += 1
            self.last_error = ""
            if frame is not None:
                self.latest_frame = frame

            # Metrics for history tracking
            num_workers = sum(n for k, n in counts.items() if is_person(k))
            num_helmets = sum(n for k, n in counts.items() if is_helmet(k) and not is_violation(k))
            num_vests = sum(n for k, n in counts.items() if is_vest(k) and not is_violation(k))
            num_boots = sum(n for k, n in counts.items() if is_boots(k) and not is_violation(k))
            num_gloves = sum(n for k, n in counts.items() if is_gloves(k) and not is_violation(k))
            num_goggles = sum(n for k, n in counts.items() if is_goggles(k) and not is_violation(k))
            self.history.append(
                (now, num_workers, num_helmets, num_vests, num_boots, num_gloves, num_goggles, violations_count)
            )

            # Debounced state machine
            if violations_count > 0:
                self.violation_streak += 1
                self.clean_streak = 0
            else:
                self.clean_streak += 1
                self.violation_streak = 0

            # Group violations per person ID (e.g. "Person 1 - no helmet, no vest")
            person_reports: list[str] = []
            person_records: list[dict] = []
            for w in workers:
                if w.has_active_violation:
                    v_clean = [v.replace("_", " ").title() for v in w.violations]
                    v_str = ", ".join([v.lower() for v in v_clean]) if v_clean else "safety violation"
                    person_reports.append(f"Person {w.worker_id} - {v_str}")
                    person_records.append({
                        "worker_id": w.worker_id,
                        "person_name": f"Person {w.worker_id}",
                        "missing_ppe": v_clean if v_clean else ["Safety Violation"],
                        "zone": getattr(w, "zone", "Production Floor"),
                        "dwell_seconds": getattr(w, "dwell_seconds", 0.0),
                    })

            violating_labels = person_reports if person_reports else sorted({d["label"] for d in detections if d["violation"]})

            was_violating = self.violating
            if not was_violating and self.violation_streak >= VIOLATION_CONFIRM_FRAMES:
                self.violating = True
                self.violation_seq += 1
                self._last_violation_labels = set(violating_labels)
                self.event_log.appendleft({
                    "ts": now,
                    "type": "VIOLATION",
                    "violations": violations_count,
                    "labels": violating_labels,
                    "person_reports": person_reports,
                    "person_records": person_records,
                })
            elif was_violating and violations_count > 0:
                current_labels = set(violating_labels)
                prev_labels = getattr(self, '_last_violation_labels', set())
                new_labels = current_labels - prev_labels
                if new_labels:
                    self._last_violation_labels = current_labels
                    self.event_log.appendleft({
                        "ts": now,
                        "type": "VIOLATION_UPDATE",
                        "violations": violations_count,
                        "labels": list(current_labels),
                        "person_reports": person_reports,
                        "person_records": person_records,
                    })
            elif was_violating and self.clean_streak >= VIOLATION_CLEAR_FRAMES:
                self.violating = False
                self._last_violation_labels = set()
                self.event_log.appendleft({
                    "ts": now,
                    "type": "CLEARED",
                    "violations": 0,
                    "labels": [],
                    "person_reports": [],
                    "person_records": [],
                })

    def publish_error(self, err: str) -> None:
        with self.lock:
            self.last_error = err[:300]

    def add_snapshot(self, record: dict) -> None:
        with self.lock:
            self.snapshots.append(record)
            if len(self.snapshots) > MAX_SNAPSHOTS:
                del self.snapshots[: len(self.snapshots) - MAX_SNAPSHOTS]

    def clear_snapshots(self) -> None:
        with self.lock:
            self.snapshots.clear()

    def clear_events(self) -> None:
        """Clear historical event log and reset violation streaks."""
        with self.lock:
            self.event_log.clear()
            self.history.clear()
            self.violations_count = 0
            self.violation_streak = 0
            self.clean_streak = 0
            self.violating = False

    def snapshot_ui(self) -> dict:
        """Produce a clean, detached state dictionary for UI rendering."""
        with self.lock:
            return {
                "counts": dict(self.counts),
                "detections": [dict(d) for d in self.detections],
                "workers": list(self.workers),
                "fps": self.fps,
                "inference_ms": self.inference_ms,
                "total_frames": self.total_frames,
                "violating": self.violating,
                "violation_seq": self.violation_seq,
                "last_error": self.last_error,
                "snapshots_count": len(self.snapshots),
                "latest_frame": self.latest_frame,
            }

    def get_history_df(self) -> pd.DataFrame:
        cols = ["Workers", "Helmets", "Vests", "Boots", "Gloves", "Goggles", "Violations"]
        with self.lock:
            rows = list(self.history)
        if not rows:
            return pd.DataFrame(columns=cols)
        if len(rows[0]) == 5:
            df = pd.DataFrame(rows, columns=["ts", "Workers", "Helmets", "Vests", "Violations"])
            df["Boots"] = 0
            df["Gloves"] = 0
            df["Goggles"] = 0
        else:
            df = pd.DataFrame(rows, columns=["ts", *cols])
        df["time"] = pd.to_datetime(df["ts"], unit="s")
        return df.set_index("time")[cols]

    def get_snapshots(self) -> list[dict]:
        with self.lock:
            return list(self.snapshots)

    def get_events(self) -> list[dict]:
        with self.lock:
            return list(self.event_log)


class VideoPipeline:
    """Manages frame ingestion, YOLO inference, and overlay rendering."""

    def __init__(self, model: YOLO | None, state: TelemetryState, device: str = "cpu", half: bool = False):
        self.model = model
        self.state = state
        self.device = device
        self.half = half
        self.renderer = OverlayRenderer()
        self.evidence_mgr = EvidenceManager()
        self.tracker = WorkerTracker()
        self.infer_lock = threading.Lock()

        self.frame_idx = 0
        self.smoothed_fps = 0.0
        self.last_boxes = np.empty((0, 4), dtype=np.float32)
        self.last_scores = np.empty((0,), dtype=np.float32)
        self.last_labels: list[str] = []
        self.last_detections: list[dict] = []
        self.last_workers: list[WorkerStatus] = []
        self.last_capture_time = 0.0

    def render_8k_clarity_canvas(self, *args, **kwargs) -> np.ndarray:
        """Forwarder to OverlayRenderer.render_8k_clarity_canvas."""
        if not hasattr(self.renderer, "render_8k_clarity_canvas"):
            self.renderer = OverlayRenderer()
        try:
            return self.renderer.render_8k_clarity_canvas(*args, **kwargs)
        except TypeError:
            import importlib

            import src.video.renderer as _rmod
            _rmod = importlib.reload(_rmod)
            self.renderer = _rmod.OverlayRenderer()
            return self.renderer.render_8k_clarity_canvas(*args, **kwargs)

    def reset_tracker(self) -> None:
        """Reset the internal worker tracker and identity gallery."""
        with self.infer_lock:
            self.tracker = WorkerTracker()

    def process_numpy_frame(self, img: np.ndarray, force_infer: bool = False) -> np.ndarray:
        """Process a raw OpenCV BGR numpy frame through inference and overlay pipeline."""
        (
            conf,
            iou,
            class_conf,
            mode_key,
            auto_capture,
            mirror,
            show_hud,
            assoc_workers,
            req_ppe,
        ) = self.state.get_config()

        if img is None:
            return np.zeros((480, 640, 3), dtype=np.uint8)

        if mirror:
            img = cv2.flip(img, 1)

        if self.model is None:
            self.state.publish(
                counts=Counter(),
                detections=[],
                workers=[],
                fps=0.0,
                inference_ms=0.0,
                violations_count=0,
                frame=img,
            )
            with self.state.lock:
                self.state.last_error = "No model is loaded"
            return img

        self.frame_idx += 1
        profile = PERFORMANCE_MODES.get(mode_key, PERFORMANCE_MODES["balanced"])
        should_infer = force_infer or ((self.frame_idx % max(1, profile.frame_skip)) == 0)

        if should_infer:
            t0 = time.perf_counter()
            try:
                use_augment = getattr(profile, "augment", False) or getattr(self.state, "accuracy_boost", False)
                use_crop_refine = getattr(profile, "crop_refine", False) or getattr(self.state, "crop_refine", False)
                with self.infer_lock:
                    boxes, scores, labels, detections = run_inference(
                        model=self.model,
                        image=img,
                        conf_threshold=conf,
                        iou_threshold=iou,
                        per_class_conf=class_conf,
                        image_size=profile.inference_size,
                        device=self.device,
                        half=self.half,
                        augment=use_augment,
                        enable_crop_refinement=use_crop_refine,
                    )
                dt = max(time.perf_counter() - t0, 1e-6)
                instant_fps = 1.0 / dt
                self.smoothed_fps = 0.85 * self.smoothed_fps + 0.15 * instant_fps if self.smoothed_fps > 0 else instant_fps

                workers = (
                    associate_ppe_to_workers(
                        detections,
                        frame_w=img.shape[1],
                        frame_h=img.shape[0],
                        required_ppe=req_ppe,
                        tracker=self.tracker,
                        timestamp=time.time(),
                        frame_image=img,
                    )
                    if assoc_workers
                    else []
                )
                self.last_workers = workers

                # Preserve all valid detections and compute violations
                counts = Counter(d["label"] for d in detections)
                if workers:
                    violations_count = sum(1 for w in workers if w.has_active_violation)
                else:
                    violations_count = sum(1 for d in detections if d.get("violation", False))

                self.last_boxes = boxes
                self.last_scores = scores
                self.last_labels = labels
                self.last_detections = detections

                self.state.publish(
                    counts=counts,
                    detections=self.last_detections,
                    workers=workers,
                    fps=self.smoothed_fps,
                    inference_ms=dt * 1000.0,
                    violations_count=violations_count,
                )

                # Snapshot rate-limiting
                now = time.time()
                if auto_capture and violations_count > 0 and (now - self.last_capture_time >= CAPTURE_COOLDOWN_SEC):
                    self.last_capture_time = now
                    violating_labels = [d["label"] for d in self.last_detections if d.get("violation", False)]
                    active_person_id = None
                    if workers:
                        for w in workers:
                            if w.has_active_violation:
                                active_person_id = w.worker_id
                                for v in w.violations:
                                    if v not in violating_labels:
                                        violating_labels.append(v)
                    record = self.evidence_mgr.save_snapshot(
                        img, violating_labels, timestamp=now, person_id=active_person_id
                    )
                    if record:
                        self.state.add_snapshot(record)

            except Exception as exc:
                self.state.publish_error(f"{type(exc).__name__}: {exc}")

        # Draw overlays
        try:
            if assoc_workers and self.last_workers:
                # In worker association mode, worker badges cleanly show the worker's status
                img = self.renderer.draw_worker_badges(
                    img,
                    self.last_workers,
                    show_labels=getattr(self.state, "overlay_show_labels", True),
                    show_corner_brackets=getattr(self.state, "overlay_show_corner_brackets", True),
                    show_status_pills=getattr(self.state, "overlay_show_status_pills", True),
                )
                # Only draw compliance/violation badges that belong to workers
                ppe_boxes = []
                ppe_labels = []
                ppe_scores = []
                for b, l, s in zip(self.last_boxes, self.last_labels, self.last_scores):
                    if not is_person(l):
                        ppe_boxes.append(b)
                        ppe_labels.append(l)
                        ppe_scores.append(s)
                if ppe_boxes:
                    img = self.renderer.draw_detections(
                        img,
                        np.array(ppe_boxes, dtype=np.float32),
                        ppe_labels,
                        np.array(ppe_scores, dtype=np.float32),
                        show_conf_pct=getattr(self.state, "overlay_show_conf_pct", True),
                        show_corner_brackets=getattr(self.state, "overlay_show_corner_brackets", True),
                    )
            else:
                img = self.renderer.draw_detections(
                    img,
                    self.last_boxes,
                    self.last_labels,
                    self.last_scores,
                    show_conf_pct=getattr(self.state, "overlay_show_conf_pct", True),
                    show_corner_brackets=getattr(self.state, "overlay_show_corner_brackets", True),
                )

            violations_now = sum(1 for d in self.last_detections if d["violation"])
            workers_now = sum(1 for d in self.last_detections if is_person(d["label"]))
            img = self.renderer.draw_telemetry_hud(
                img,
                self.smoothed_fps,
                violations_now,
                workers_now,
                inference_ms=self.state.inference_ms if self.state.inference_ms > 0 else 0.0,
                show_hud=show_hud,
            )
        except Exception as exc:
            self.state.publish_error(f"Render error: {exc}")

        with self.state.lock:
            self.state.latest_frame = img

        return img



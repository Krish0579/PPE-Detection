"""
===============================================================================
 Real-Time PPE Detection Dashboard  (Streamlit + streamlit-webrtc + Ultralytics)
===============================================================================

HOW TO RUN LOCALLY
------------------
1.  python -m venv .venv && source .venv/bin/activate     (Windows: .venv\\Scripts\\activate)
2.  pip install -r requirements.txt
3.  streamlit run app.py
4.  Open http://localhost:8501 and click "START" on the video widget, then
    allow camera access in the browser.

NOTES
-----
* We deliberately use `streamlit-webrtc` instead of `cv2.VideoCapture(0)`.
  `VideoCapture` runs on the Streamlit script thread, blocks reruns, and in any
  hosted/web environment it would read the *server's* camera (not the user's).
  WebRTC streams the user's camera to a background worker thread instead, which
  keeps the UI responsive and latency low.
* Model inference happens inside the WebRTC worker thread. All shared state
  (latest detection counts, current thresholds) is guarded by a `threading.Lock`
  so the Streamlit main thread can render metrics safely.
* To customise the look & feel: edit the CUSTOM_CSS string below (search for
  "CUSTOMIZE CSS HERE"). All colours are defined once in the `THEME` dict.
===============================================================================
"""

from __future__ import annotations

import base64
import io
import json
import os
import traceback
import queue
import tempfile
import threading
import time
import zipfile
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import av  # provided by streamlit-webrtc (PyAV)
import cv2
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from ultralytics import YOLO

# Number of samples kept in the live history chart (~a few minutes of stream).
HISTORY_LEN = 600
EVENT_LOG_LEN = 200
MODEL_PATH = "/Users/universalimpex/Downloads/final.pt"


# -----------------------------------------------------------------------------
# 1. PAGE CONFIG  (must be the first Streamlit call)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="PPE Vision · Real-Time Safety Monitor",
    page_icon="🦺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# 2. THEME + CUSTOM CSS  ("bright & cool" dashboard)  <-- CUSTOMIZE CSS HERE
# -----------------------------------------------------------------------------
THEME = {
    "bg": "#f4f8ff",
    "surface": "#ffffff",
    "ink": "#0f1e3d",
    "muted": "#5b6b8c",
    "accent": "#2563eb",      # vivid blue
    "accent2": "#06b6d4",     # cyan
    "ok": "#16a34a",          # compliance green
    "warn": "#f59e0b",        # amber
    "bad": "#ef4444",         # violation red
}

CUSTOM_CSS = f"""
<style>
/* ---------- Global canvas ---------- */
.stApp {{
    background:
        radial-gradient(1200px 600px at 10% -10%, #e0ecff 0%, transparent 60%),
        radial-gradient(900px 500px at 110% 0%, #dffaff 0%, transparent 55%),
        {THEME['bg']};
    color: {THEME['ink']};
}}
.block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1500px; }}

/* ---------- Typography ---------- */
h1, h2, h3, h4 {{ color: {THEME['ink']}; letter-spacing: -0.02em; font-weight: 800; }}
p, label, span, div {{ font-variant-numeric: tabular-nums; }}

/* ---------- Hero header ---------- */
.ppe-hero {{
    background: linear-gradient(120deg, {THEME['accent']} 0%, {THEME['accent2']} 100%);
    border-radius: 22px;
    padding: 26px 32px;
    color: #ffffff;
    box-shadow: 0 18px 40px -18px rgba(37, 99, 235, .55);
    margin-bottom: 22px;
}}
.ppe-hero h1 {{ color: #fff; margin: 0; font-size: 2.05rem; }}
.ppe-hero p  {{ color: rgba(255,255,255,.92); margin: .4rem 0 0; font-size: 1rem; }}
.ppe-pill {{
    display:inline-block; margin-top:14px; padding:6px 14px; border-radius:999px;
    background: rgba(255,255,255,.20); border:1px solid rgba(255,255,255,.35);
    font-size:.8rem; font-weight:600; letter-spacing:.04em; text-transform:uppercase;
}}

/* ---------- Cards / panels ---------- */
.ppe-card {{
    background: {THEME['surface']};
    border: 1px solid #e6edfa;
    border-radius: 18px;
    padding: 18px 20px;
    box-shadow: 0 10px 30px -22px rgba(15, 30, 61, .45);
}}
.ppe-card h4 {{ margin: 0 0 .6rem 0; font-size: .95rem; color: {THEME['muted']};
    text-transform: uppercase; letter-spacing: .08em; }}

/* ---------- Metrics ---------- */
div[data-testid="stMetric"] {{
    background: {THEME['surface']};
    border: 1px solid #e6edfa;
    border-left: 6px solid {THEME['accent']};
    border-radius: 16px;
    padding: 16px 18px;
    box-shadow: 0 10px 26px -20px rgba(15, 30, 61, .5);
    transition: transform .15s ease, box-shadow .15s ease;
}}
div[data-testid="stMetric"]:hover {{
    transform: translateY(-2px);
    box-shadow: 0 16px 30px -20px rgba(37, 99, 235, .65);
}}
div[data-testid="stMetricLabel"] p {{
    color: {THEME['muted']} !important; font-weight: 700;
    text-transform: uppercase; letter-spacing: .07em; font-size: .74rem;
}}
div[data-testid="stMetricValue"] {{ color: {THEME['ink']}; font-weight: 800; }}
/* Violation metric gets a red accent bar (applied via nth-of-type helper class) */
.violation-metric div[data-testid="stMetric"] {{ border-left-color: {THEME['bad']}; }}
.compliance-metric div[data-testid="stMetric"] {{ border-left-color: {THEME['ok']}; }}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, #ffffff 0%, #eef4ff 100%);
    border-right: 1px solid #e2eafc;
}}
section[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {{
    color: {THEME['accent']};
}}
/* Sliders */
div[data-baseweb="slider"] div[role="slider"] {{
    background: {THEME['accent']} !important; border-color: #fff !important;
    box-shadow: 0 0 0 4px rgba(37,99,235,.18) !important;
}}
/* Buttons */
.stButton > button {{
    border-radius: 12px; font-weight: 700; border: none;
    background: linear-gradient(120deg, {THEME['accent']}, {THEME['accent2']});
    color: #fff; padding: .55rem 1.1rem;
    box-shadow: 0 10px 22px -12px rgba(37,99,235,.7);
}}
.stButton > button:hover {{ filter: brightness(1.06); }}
/* File uploader */
section[data-testid="stFileUploaderDropzone"] {{
    border: 2px dashed #b9d0ff; background: #f7fbff; border-radius: 14px;
}}

/* ---------- Status banner ---------- */
.ppe-status {{
    border-radius: 14px; padding: 14px 18px; font-weight: 800; letter-spacing: .01em;
    display: flex; align-items: center; gap: 10px; font-size: 1.02rem;
}}
.ppe-status.ok  {{ background: #e8fbef; color: {THEME['ok']};  border: 1px solid #b7f0cb; }}
.ppe-status.bad {{ background: #fdeaea; color: {THEME['bad']}; border: 1px solid #f8c3c3; }}
.ppe-status.idle{{ background: #eef4ff; color: {THEME['muted']}; border: 1px solid #d9e6ff; }}

/* ---------- Full-width violation alert banner ---------- */
.ppe-alert {{
    margin: 6px 0 14px; padding: 16px 22px; border-radius: 16px;
    background: linear-gradient(120deg, {THEME['bad']}, #b91c1c);
    color: #fff; font-weight: 900; font-size: 1.1rem; letter-spacing: .02em;
    box-shadow: 0 16px 34px -18px rgba(239,68,68,.85);
    animation: ppe-flash 1s ease-in-out infinite;
}}
@keyframes ppe-flash {{
    0%, 100% {{ filter: brightness(1); }}
    50%      {{ filter: brightness(1.22); }}
}}

/* ---------- Video frame ---------- */
video {{ border-radius: 18px !important; box-shadow: 0 22px 50px -26px rgba(15,30,61,.6); }}
#MainMenu, footer {{ visibility: hidden; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 3. CLASS SEMANTICS  (which labels are violations vs compliance)
# -----------------------------------------------------------------------------
# Colours are BGR because OpenCV draws in BGR.
BGR_BAD = (68, 68, 239)      # red     -> violations ("no helmet", "no vest", ...)
BGR_OK = (94, 163, 22)       # green   -> compliance ("helmet", "vest", ...)
BGR_NEUTRAL = (219, 119, 6)  # blue    -> person / machinery / other
BGR_TEXT = (255, 255, 255)

# Substrings that flag a *negative* (violation) class in common PPE datasets.
VIOLATION_TOKENS = (
    "no-", "no_", "no ", "without", "missing", "off", "violation",
)
COMPLIANCE_TOKENS = (
    "helmet", "hardhat", "hard-hat", "vest", "mask", "gloves", "goggles",
    "boots", "glasses", "shield", "harness",
)
PERSON_TOKENS = ("person", "worker", "people", "human")


def normalize(label: str) -> str:
    return label.strip().lower().replace("_", "-").replace("  ", " ")


def is_violation(label: str) -> bool:
    """True when the class name expresses a *missing* PPE item."""
    n = normalize(label)
    return any(n.startswith(t.replace("_", "-")) or t in n for t in VIOLATION_TOKENS)


def is_person(label: str) -> bool:
    n = normalize(label)
    return any(t in n for t in PERSON_TOKENS) and not is_violation(n)


def is_compliance(label: str) -> bool:
    n = normalize(label)
    return (not is_violation(n)) and any(t in n for t in COMPLIANCE_TOKENS)


def color_for(label: str) -> Tuple[int, int, int]:
    if is_violation(label):
        return BGR_BAD
    if is_compliance(label):
        return BGR_OK
    return BGR_NEUTRAL


# -----------------------------------------------------------------------------
# 4. MODEL LOADING (cached so the weights load once per session/process)
# -----------------------------------------------------------------------------
DEFAULT_WEIGHTS = [MODEL_PATH]


@st.cache_resource(show_spinner="Detecting compute devices…")
def available_devices() -> List[str]:
    """List selectable inference devices ("cpu", "cuda:0", "mps", …)."""
    devices = ["cpu"]
    try:
        import torch

        if torch.cuda.is_available():
            devices += [f"cuda:{i}" for i in range(torch.cuda.device_count())]
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            devices.append("mps")
    except Exception:  # noqa: BLE001 - torch missing/broken -> CPU only
        pass
    return devices


def device_label(dev: str) -> str:
    if dev.startswith("cuda"):
        try:
            import torch

            return f"GPU · {torch.cuda.get_device_name(int(dev.split(':')[1]))}"
        except Exception:  # noqa: BLE001
            return f"GPU · {dev}"
    if dev == "mps":
        return "GPU · Apple Metal (MPS)"
    return "CPU"


@st.cache_resource(show_spinner="Loading YOLO weights…")
def load_model(weights_path: str, device: str, half: bool) -> YOLO:
    """Load, move to `device` and warm up an Ultralytics YOLO model.

    `st.cache_resource` keeps a single instance alive across reruns, which is
    essential: re-instantiating YOLO on every widget change would stall the app.
    The cache key includes device/half so switching either reloads once only.
    """
    model = YOLO(weights_path)
    try:
        model.to(device)
    except Exception:  # noqa: BLE001 - fall back to whatever Ultralytics picked
        pass
    # Warm-up pass removes the first-inference latency spike inside the
    # WebRTC worker thread (and builds the FP16 kernels when half=True).
    model.predict(
        np.zeros((320, 320, 3), dtype=np.uint8),
        device=device,
        half=half,
        verbose=False,
    )
    return model



# -----------------------------------------------------------------------------
# 5. THREAD-SAFE SHARED STATE
# -----------------------------------------------------------------------------
@dataclass
class DetectionState:
    """Thread-safe shared state between the WebRTC worker and Streamlit UI."""
    lock: threading.Lock = field(default_factory=threading.Lock)
    conf: float = 0.35
    iou: float = 0.45
    class_conf: Dict[str, float] = field(default_factory=dict)
    counts: Counter = field(default_factory=Counter)
    detections: List[dict] = field(default_factory=list)
    fps: float = 0.0
    total_frames: int = 0
    successful_inferences: int = 0
    inference_errors: int = 0
    last_error: str = ""
    last_update: float = 0.0
    history: deque = field(default_factory=lambda: deque(maxlen=HISTORY_LEN))
    snapshots: List[dict] = field(default_factory=list)
    last_capture_ts: float = 0.0
    violation_seq: int = 0
    violating: bool = False
    violation_streak: int = 0
    clean_streak: int = 0
    event_log: deque = field(default_factory=lambda: deque(maxlen=EVENT_LOG_LEN))

    def set_thresholds(self, conf: float, iou: float,
                       class_conf: Optional[Dict[str, float]] = None) -> None:
        with self.lock:
            self.conf, self.iou = conf, iou
            if class_conf is not None:
                self.class_conf = dict(class_conf)

    def snapshot(self) -> Tuple[Dict[str, int], float, int]:
        with self.lock:
            return dict(self.counts), self.fps, self.total_frames

    def detailed_snapshot(self) -> List[dict]:
        with self.lock:
            return [dict(x) for x in self.detections]

    def get_history(self) -> List[tuple]:
        with self.lock:
            return list(self.history)

    def get_snapshots(self) -> List[dict]:
        with self.lock:
            return list(self.snapshots)

    def get_events(self) -> List[dict]:
        with self.lock:
            return list(self.event_log)

    def clear_snapshots(self) -> None:
        with self.lock:
            self.snapshots.clear()

    def clear_events(self) -> None:
        with self.lock:
            self.event_log.clear()

    def get_alert(self) -> Tuple[bool, int]:
        with self.lock:
            return self.violating, self.violation_seq

    def get_status(self) -> Tuple[str, str, int]:
        with self.lock:
            return self.last_error, self.last_update, self.inference_errors

    def get_thresholds(self) -> Tuple[float, float, Dict[str, float]]:
        with self.lock:
            return self.conf, self.iou, dict(self.class_conf)

    def publish(self, counts: Counter, fps: float,
                stats: Tuple[int, int, int, int], violations: int,
                detections: List[dict], violation_confirm_frames: int,
                violation_clear_frames: int) -> None:
        now = time.time()
        with self.lock:
            self.counts = Counter(counts)
            self.detections = [dict(x) for x in detections]
            self.fps = fps
            self.total_frames += 1
            self.successful_inferences += 1
            self.last_error = ""
            self.last_update = now
            self.history.append((now, *stats))

            if violations > 0:
                self.violation_streak += 1
                self.clean_streak = 0
            else:
                self.clean_streak += 1
                self.violation_streak = 0

            was = self.violating
            if not was and self.violation_streak >= max(1, violation_confirm_frames):
                self.violating = True
                self.violation_seq += 1
                self.event_log.appendleft({
                    "ts": now,
                    "type": "VIOLATION_START",
                    "labels": sorted({d["label"] for d in detections if d.get("violation")}),
                    "violations": int(violations),
                })
            elif was and self.clean_streak >= max(1, violation_clear_frames):
                self.violating = False
                self.event_log.appendleft({
                    "ts": now,
                    "type": "VIOLATION_CLEAR",
                    "labels": [],
                    "violations": 0,
                })

    def publish_error(self, message: str) -> None:
        with self.lock:
            self.inference_errors += 1
            self.last_error = message[:500]

    def maybe_capture(self, frame: np.ndarray, labels: List[str], cooldown: float, limit: int) -> None:
        """Store a JPEG snapshot of a violating frame (rate-limited)."""
        now = time.time()
        with self.lock:
            if now - self.last_capture_ts < cooldown:
                return
            self.last_capture_ts = now
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        if not ok:
            return
        item = {
            "ts": now,
            "labels": sorted(set(labels)),
            "jpeg": buf.tobytes(),
        }
        with self.lock:
            self.snapshots.append(item)
            if len(self.snapshots) > limit:
                del self.snapshots[: len(self.snapshots) - limit]


if "state" not in st.session_state:
    st.session_state.state = DetectionState()
STATE: DetectionState = st.session_state.state



# -----------------------------------------------------------------------------
# 6. DRAWING  (robust label rendering — every class gets a box + text)
# -----------------------------------------------------------------------------
def draw_detections(
    frame: np.ndarray,
    boxes: np.ndarray,
    labels: List[str],
    scores: np.ndarray,
) -> np.ndarray:
    """Draw all boxes with filled label chips. Violations are red & bold."""
    h, w = frame.shape[:2]
    base = max(0.45, min(w, h) / 1100.0)  # scale text with resolution

    for (x1, y1, x2, y2), label, score in zip(boxes, labels, scores):
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)

        violation = is_violation(label)
        color = color_for(label)
        thickness = 4 if violation else 2

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        # Emphasise violations with a translucent red wash inside the box.
        if violation:
            overlay = frame.copy()
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
            cv2.addWeighted(overlay, 0.18, frame, 0.82, 0, dst=frame)

        text = f"{'⚠ ' if violation else ''}{label.upper()} {score * 100:.0f}%"
        text = text.replace("⚠ ", "! ")  # OpenCV cannot render emoji glyphs
        scale = base * (1.15 if violation else 1.0)
        font = cv2.FONT_HERSHEY_DUPLEX
        (tw, th), bl = cv2.getTextSize(text, font, scale, 1)

        # Chip above the box; flip below when it would clip the top edge.
        top = y1 - th - bl - 8
        if top < 0:
            top = y1 + 2
        cv2.rectangle(frame, (x1, top), (x1 + tw + 14, top + th + bl + 8), color, -1)
        cv2.putText(
            frame, text, (x1 + 7, top + th + 3), font, scale, BGR_TEXT, 1, cv2.LINE_AA
        )
    return frame


def draw_hud(frame: np.ndarray, counts: Counter, fps: float) -> np.ndarray:
    """Top-left heads-up display with FPS and a compliance verdict."""
    violations = sum(v for k, v in counts.items() if is_violation(k))
    h, w = frame.shape[:2]
    pad = 12
    banner_h = 46
    color = BGR_BAD if violations else BGR_OK
    label = (
        f"VIOLATIONS: {violations}" if violations else "NO VIOLATION CLASSES DETECTED"
    )

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, banner_h), (255, 255, 255), -1)
    cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, dst=frame)
    cv2.rectangle(frame, (0, 0), (w, 5), color, -1)

    cv2.putText(frame, label, (pad, banner_h - 14), cv2.FONT_HERSHEY_DUPLEX,
                0.72, color, 1, cv2.LINE_AA)
    cv2.putText(frame, f"{fps:4.1f} FPS", (w - 140, banner_h - 14),
                cv2.FONT_HERSHEY_DUPLEX, 0.62, (80, 80, 80), 1, cv2.LINE_AA)
    return frame


# -----------------------------------------------------------------------------
# 7. SIDEBAR — model + inference configuration
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🦺 PPE Vision")
    st.caption("Configure the detector. Changes apply live to the stream.")

    # Your trained model is loaded directly from this local path.
    weights_path: str = MODEL_PATH
    if os.path.isfile(weights_path):
        st.success("Using **final.pt**")
        st.caption(f"Model: `{weights_path}`")
    else:
        st.error("Model file not found.")
        st.caption(f"Expected: `{weights_path}`")

    st.markdown("### 2 · Performance / device")
    devices = available_devices()
    device = st.selectbox(
        "Inference device", devices,
        format_func=device_label,
        help="Pick the GPU for real-time FPS; CPU works everywhere.",
    )
    half = st.checkbox(
        "Half precision (FP16)", value=device.startswith("cuda"),
        disabled=not device.startswith("cuda"),
        help="CUDA only — roughly 1.5–2× faster with negligible accuracy loss.",
    )
    if not device.startswith("cuda"):
        half = False
        st.caption("FP16 requires a CUDA GPU. Running full precision on this device.")

    st.markdown("### 3 · Inference thresholds")
    conf = st.slider("Global confidence threshold", 0.0, 1.0, 0.35, 0.01,
                     help="Floor used by YOLO; per-class values refine it below.")
    iou = st.slider("NMS / IoU threshold", 0.0, 1.0, 0.45, 0.01,
                    help="Lower = more aggressive duplicate-box suppression.")
    imgsz = st.select_slider("Inference size", [320, 416, 512, 640, 960], value=640,
                             help="Smaller = faster, larger = more accurate.")
    max_det = st.slider("Max detections / frame", 5, 100, 40, 5)
    skip_n = st.select_slider(
        "Process every Nth frame", [1, 2, 3, 4], value=1,
        help="Raise this on CPU-only machines to keep the stream smooth.",
    )

    st.markdown("### 4 · Overlay & alerts")
    show_hud = st.checkbox("Show on-video HUD banner", value=True)
    mirror = st.checkbox("Mirror (selfie view)", value=True)
    alert_banner = st.checkbox("On-screen violation alert banner", value=True)
    alert_sound = st.checkbox("Play alert sound on violation", value=True)
    alert_cooldown = st.slider("Alert sound cooldown (s)", 1, 30, 5, 1)
    violation_confirm_frames = st.slider(
        "Confirm violation after N frames", 1, 10, 2, 1,
        help="Reduces false alerts from one-frame flicker. The violation must persist for this many processed frames."
    )
    violation_clear_frames = st.slider(
        "Clear violation after N clean frames", 1, 15, 3, 1,
        help="Keeps the alert stable when a person briefly disappears from the detector."
    )

    st.markdown("### 5 · Violation snapshots")
    auto_capture = st.checkbox("Auto-capture violation frames", value=True)
    capture_cooldown = st.slider("Capture every … seconds", 1, 30, 3, 1,
                                 help="Rate limit so one incident isn't saved 25×/s.")
    capture_limit = st.slider("Keep last N snapshots", 5, 100, 25, 5)

# Load the model on the main thread (cached), then hand the reference to the
# callback. Ultralytics predict() is safe to call from the single WebRTC worker.
model: Optional[YOLO] = None
model_error: Optional[str] = None
if weights_path:
    try:
        model = load_model(weights_path, device, half)
    except Exception as exc:  # noqa: BLE001 - surfaced in the UI
        model_error = str(exc)

# -----------------------------------------------------------------------------
# 7b. PER-CLASS CONFIDENCE THRESHOLDS
# -----------------------------------------------------------------------------
# YOLO itself only takes a single `conf`; we therefore run at the global floor
# and post-filter each detection against its own class threshold. Defaults make
# violation classes slightly more sensitive than compliance classes.
class_names: List[str] = []
if model is not None:
    try:
        class_names = [str(n) for n in (model.names.values() if hasattr(model.names, "values") else model.names)]
    except Exception:  # noqa: BLE001
        class_names = []

class_conf: Dict[str, float] = {}
if class_names:
    with st.sidebar:
        st.markdown("### 6 · Per-class sensitivity")
        st.caption("Fine-tune the confidence required for each label.")
        if st.button("Reset per-class thresholds"):
            for n in class_names:
                st.session_state.pop(f"cc_{normalize(n)}", None)
        with st.expander(f"{len(class_names)} classes", expanded=False):
            for name in sorted(class_names, key=lambda s: normalize(s)):
                key = normalize(name)
                default = 0.30 if is_violation(key) else 0.40
                icon = "🔴" if is_violation(key) else ("🟢" if is_compliance(key) else "🔵")
                class_conf[key] = st.slider(
                    f"{icon} {name}", 0.0, 1.0,
                    float(max(default, conf)) if conf > default else default,
                    0.01, key=f"cc_{key}",
                )

# Push the latest thresholds into the shared state for the worker thread.
STATE.set_thresholds(conf, iou, class_conf)



model_size_mb = None
if os.path.isfile(weights_path):
    try:
        model_size_mb = os.path.getsize(weights_path) / (1024 * 1024)
    except OSError:
        model_size_mb = None


# -----------------------------------------------------------------------------
# 8. HEADER
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div class="ppe-hero">
      <h1>Real-Time PPE Detection Dashboard</h1>
      <p>Live safety compliance monitoring powered by Ultralytics YOLO and WebRTC streaming.</p>
      <span class="ppe-pill">Helmet · Vest · Mask · Violation alerts</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if model is not None:
    device_text = device_label(device)
    size_text = f" · {model_size_mb:.1f} MB" if model_size_mb is not None else ""
    st.markdown(
        f"<div class='ppe-card'><h4>System status</h4>✅ Model ready · <b>{device_text}</b>{size_text} · <b>{len(class_names) if class_names else '…'}</b> classes discovered from checkpoint</div>",
        unsafe_allow_html=True,
    )

if model_error:
    st.error(f"Could not load weights: {model_error}")
elif model is None:
    st.info("Select or upload a `.pt` model in the sidebar to begin.")

# -----------------------------------------------------------------------------
# 9. VIDEO FRAME CALLBACK  (runs in the WebRTC worker thread)
# -----------------------------------------------------------------------------
# A small queue lets us pass per-frame counts to the UI without holding locks
# for long. maxsize=1 -> always the freshest frame, never a backlog.
result_q: "queue.Queue[Tuple[Dict[str, int], float]]" = queue.Queue(maxsize=1)

_frame_meta = {"idx": 0, "t": time.time(), "fps": 0.0,
               "boxes": np.empty((0, 4)), "labels": [], "scores": np.empty((0,))}


def aggregate_counts(counts: Dict[str, int]) -> Tuple[int, int, int, int, int, int]:
    """(workers, helmets, vests, no_helmet, no_vest, violations) from raw counts."""
    def total(*tokens: str, negated: bool) -> int:
        out = 0
        for label, n in counts.items():
            if is_violation(label) != negated:
                continue
            if any(t in label for t in tokens):
                out += n
        return out

    workers = sum(n for k, n in counts.items() if is_person(k))
    helmets = total("helmet", "hardhat", "hard-hat", negated=False)
    vests = total("vest", negated=False)
    no_helmet = total("helmet", "hardhat", "hard-hat", negated=True)
    no_vest = total("vest", negated=True)
    violations = sum(n for k, n in counts.items() if is_violation(k))
    return workers, helmets, vests, no_helmet, no_vest, violations



def run_yolo_prediction(
    image: np.ndarray,
    conf_threshold: float,
    iou_threshold: float,
    per_class: Dict[str, float],
    image_size: int,
    max_detections: int,
    inference_device: str,
    use_half: bool,
) -> Tuple[np.ndarray, np.ndarray, List[str], List[dict]]:
    """Single prediction path used by live camera and offline image analysis."""
    floor = min([conf_threshold, *per_class.values()]) if per_class else conf_threshold
    results = model.predict(
        image,
        conf=float(max(0.01, min(0.99, floor))),
        iou=float(max(0.01, min(0.99, iou_threshold))),
        imgsz=int(image_size),
        max_det=int(max_detections),
        device=inference_device,
        half=use_half,
        verbose=False,
    )
    if not results:
        return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.float32), [], []

    r = results[0]
    names = r.names if hasattr(r, "names") else getattr(model, "names", {})
    if r.boxes is None or len(r.boxes) == 0:
        return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.float32), [], []

    boxes = r.boxes.xyxy.detach().cpu().numpy()
    scores = r.boxes.conf.detach().cpu().numpy()
    cls_ids = r.boxes.cls.detach().cpu().numpy().astype(int)
    labels = [str(names.get(int(c), int(c))) if hasattr(names, "get") else str(int(c)) for c in cls_ids]

    keep = [
        i for i, (lab, sc) in enumerate(zip(labels, scores))
        if float(sc) >= float(per_class.get(normalize(lab), conf_threshold))
    ]
    if not keep:
        return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.float32), [], []

    boxes = boxes[keep]
    scores = scores[keep]
    labels = [labels[i] for i in keep]
    detections = []
    for b, lab, score in zip(boxes, labels, scores):
        x1, y1, x2, y2 = [int(round(float(v))) for v in b]
        detections.append({
            "label": normalize(lab),
            "display_label": lab,
            "confidence": round(float(score), 4),
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "violation": bool(is_violation(lab)),
            "status": "VIOLATION" if is_violation(lab) else (
                "COMPLIANT" if is_compliance(lab) else "DETECTED"
            ),
        })
    return boxes, scores, labels, detections


def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
    """Decode -> infer -> annotate -> publish, without blocking Streamlit."""
    img = frame.to_ndarray(format="bgr24")
    if mirror:
        img = cv2.flip(img, 1)

    if model is None:
        return av.VideoFrame.from_ndarray(img, format="bgr24")

    _frame_meta["idx"] += 1
    run_inference = (_frame_meta["idx"] % max(1, skip_n)) == 0

    if run_inference:
        c_thr, i_thr, per_class = STATE.get_thresholds()
        t0 = time.perf_counter()
        try:
            boxes, scores, labels, detections = run_yolo_prediction(
                img, c_thr, i_thr, per_class, imgsz, max_det, device, half
            )
            dt = max(time.perf_counter() - t0, 1e-6)
            _frame_meta["fps"] = 0.85 * _frame_meta["fps"] + 0.15 * (1.0 / dt)
            _frame_meta.update(boxes=boxes, labels=labels, scores=scores)

            counts: Counter = Counter(d["label"] for d in detections)
            workers, _h, vests, no_helmet, no_vest, violations = aggregate_counts(counts)
            STATE.publish(
                counts, _frame_meta["fps"],
                (workers, vests, no_vest, no_helmet), violations, detections,
                violation_confirm_frames, violation_clear_frames,
            )
            if result_q.full():
                try:
                    result_q.get_nowait()
                except queue.Empty:
                    pass
            try:
                result_q.put_nowait((dict(counts), _frame_meta["fps"]))
            except queue.Full:
                pass
        except Exception as exc:  # keep video alive but expose the real problem in UI
            STATE.publish_error(f"{type(exc).__name__}: {exc}")

    img = draw_detections(
        img, _frame_meta["boxes"], _frame_meta["labels"], _frame_meta["scores"]
    )
    if show_hud:
        img = draw_hud(img, Counter(normalize(l) for l in _frame_meta["labels"]), _frame_meta["fps"])

    if run_inference and auto_capture:
        bad_labels = [l for l in _frame_meta["labels"] if is_violation(l)]
        violating_now, _ = STATE.get_alert()
        if bad_labels and violating_now:
            STATE.maybe_capture(img, bad_labels, capture_cooldown, capture_limit)

    return av.VideoFrame.from_ndarray(img, format="bgr24")


# -----------------------------------------------------------------------------
# 10. LAYOUT — video + live dashboard
# -----------------------------------------------------------------------------
video_col, panel_col = st.columns([2.1, 1], gap="large")

with video_col:
    st.markdown("#### 📹 Live camera feed")
    ctx = webrtc_streamer(
        key="ppe-detection",
        mode=WebRtcMode.SENDRECV,
        video_frame_callback=video_frame_callback,
        media_stream_constraints={
            "video": {"width": {"ideal": 1280}, "height": {"ideal": 720},
                      "frameRate": {"ideal": 25}},
            "audio": False,
        },
        rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
        async_processing=True,  # CRITICAL: never block the Streamlit thread
    )
    st.caption(
        "Press **START**, allow camera access, and adjust thresholds in the "
        "sidebar while the stream runs."
    )

with panel_col:
    st.markdown("#### 🧭 Class legend")
    st.markdown(
        f"""
        <div class="ppe-card">
          <div style="display:flex;flex-direction:column;gap:10px;font-weight:600">
            <div><span style="display:inline-block;width:14px;height:14px;border-radius:4px;
                 background:{THEME['ok']};margin-right:8px"></span>Compliant PPE (helmet, vest, mask…)</div>
            <div><span style="display:inline-block;width:14px;height:14px;border-radius:4px;
                 background:{THEME['bad']};margin-right:8px"></span>Violation (no-helmet, no-vest…)</div>
            <div><span style="display:inline-block;width:14px;height:14px;border-radius:4px;
                 background:{THEME['accent']};margin-right:8px"></span>Person / other classes</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    status_ph = st.empty()
    error_ph = st.empty()
    breakdown_ph = st.empty()

st.markdown("#### 📊 Live detection metrics")
m1, m2, m3, m4, m5 = st.columns(5)
ph_workers = m1.empty()
ph_helmet = m2.empty()
ph_vest = m3.empty()
ph_noh = m4.empty()
ph_nov = m5.empty()

st.markdown("#### 📈 Detection history (counts over time)")
chart_ph = st.empty()
st.caption(
    "Rolling window of the last "
    f"{HISTORY_LEN} processed frames — Total Workers, Vests Detected, No Vest, No Helmet."
)

HISTORY_COLS = ["Total Workers", "Vests Detected", "No Vest", "No Helmet"]


def history_frame() -> pd.DataFrame:
    """Shared-state history -> tidy DataFrame indexed by clock time."""
    rows = STATE.get_history()
    if not rows:
        return pd.DataFrame(columns=HISTORY_COLS)
    df = pd.DataFrame(rows, columns=["ts", *HISTORY_COLS])
    df["time"] = pd.to_datetime(df["ts"], unit="s")
    return df.set_index("time")[HISTORY_COLS]


def render_history() -> None:
    df = history_frame()
    if df.empty:
        chart_ph.markdown(
            "<div class='ppe-card'><h4>History</h4><span style='color:#5b6b8c'>"
            "Start the stream to plot counts over time.</span></div>",
            unsafe_allow_html=True,
        )
    else:
        chart_ph.line_chart(
            df,
            height=280,
        )


# -----------------------------------------------------------------------------
# 10b. ALERT SOUND  (short synthesized beep, embedded as a data: URI)
# -----------------------------------------------------------------------------
@st.cache_resource
def alert_sound_uri() -> str:
    """Generate a two-tone alarm WAV once and return it as a base64 data URI."""
    import struct
    import wave

    sr = 22050
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    tone = 0.45 * np.sin(2 * np.pi * np.where(t < 0.25, 880.0, 620.0) * t)
    tone *= np.clip(np.minimum(t * 40, (0.5 - t) * 40), 0, 1)  # fade in/out
    pcm = (tone * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack(f"<{len(pcm)}h", *pcm))
    return "data:audio/wav;base64," + base64.b64encode(buf.getvalue()).decode()


alert_ph = st.empty()
sound_ph = st.empty()
_alert_meta = {"seq": -1, "last_sound": 0.0}


def render_alert() -> None:
    """Big banner + (optionally) one beep per new violation burst."""
    violating, seq = STATE.get_alert()
    if alert_banner:
        if violating:
            alert_ph.markdown(
                '<div class="ppe-alert">🚨 PPE VIOLATION DETECTED — '
                'unprotected worker in the current frame</div>',
                unsafe_allow_html=True,
            )
        else:
            alert_ph.empty()
    else:
        alert_ph.empty()

    now = time.time()
    new_burst = seq != _alert_meta["seq"]
    if (alert_sound and violating and new_burst
            and now - _alert_meta["last_sound"] >= alert_cooldown):
        _alert_meta["last_sound"] = now
        sound_ph.markdown(
            f'<audio autoplay src="{alert_sound_uri()}"></audio>',
            unsafe_allow_html=True,
        )
    _alert_meta["seq"] = seq


def render_runtime_error() -> None:
    message, last_update, error_count = STATE.get_status()
    if message:
        error_ph.error(
            f"Inference warning: {message} | recovered errors this session: {error_count}. "
            "The stream remains active; fix the model/device issue shown above if it repeats."
        )
    else:
        error_ph.empty()


def render_dashboard(counts: Dict[str, int], fps: float) -> None:
    """Render metrics from a counts snapshot (main thread only)."""
    workers, helmets, vests, no_helmet, no_vest, violations = aggregate_counts(counts)

    ph_workers.metric("Total workers", workers)
    ph_helmet.metric("Helmets detected", helmets)
    ph_vest.metric("Vests detected", vests)
    ph_noh.metric("No helmet", no_helmet, delta=None)
    ph_nov.metric("No vest", no_vest, delta=None)

    if not counts:
        status_ph.markdown(
            '<div class="ppe-status idle">⏳ Waiting for detections…</div>',
            unsafe_allow_html=True,
        )
    elif violations:
        status_ph.markdown(
            f'<div class="ppe-status bad">🚨 {violations} PPE violation(s) detected</div>',
            unsafe_allow_html=True,
        )
    else:
        status_ph.markdown(
            '<div class="ppe-status ok">✅ No violation classes currently detected</div>',
            unsafe_allow_html=True,
        )

    if counts:
        rows = "".join(
            f"<tr><td style='padding:4px 10px 4px 0'>"
            f"<span style='color:{'#ef4444' if is_violation(k) else ('#16a34a' if is_compliance(k) else '#2563eb')};"
            f"font-weight:700'>{k}</span></td>"
            f"<td style='text-align:right;font-weight:800'>{v}</td></tr>"
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
        )
        breakdown_ph.markdown(
            f"<div class='ppe-card'><h4>Per-class breakdown · {fps:.1f} FPS</h4>"
            f"<table style='width:100%'>{rows}</table></div>",
            unsafe_allow_html=True,
        )
    else:
        breakdown_ph.markdown(
            "<div class='ppe-card'><h4>Per-class breakdown</h4>"
            "<span style='color:#5b6b8c'>No objects yet.</span></div>",
            unsafe_allow_html=True,
        )


# -----------------------------------------------------------------------------
# 10b. OFFLINE IMAGE INSPECTION (same model + same thresholds)
# -----------------------------------------------------------------------------
st.markdown("#### 🖼️ Inspect a saved image")
with st.expander("Upload an image for a full, repeatable prediction", expanded=False):
    uploaded = st.file_uploader("JPG / JPEG / PNG", type=["jpg", "jpeg", "png"], key="offline_image")
    if uploaded is not None:
        try:
            raw = np.frombuffer(uploaded.getvalue(), dtype=np.uint8)
            offline_img = cv2.imdecode(raw, cv2.IMREAD_COLOR)
            if offline_img is None:
                st.error("The uploaded file could not be decoded as an image.")
            elif model is None:
                st.error("The YOLO model is not available. Check the model path and load status above.")
            else:
                c_thr, i_thr, per_class = STATE.get_thresholds()
                with st.spinner("Running YOLO prediction…"):
                    t0 = time.perf_counter()
                    ob, sc, labs, dets = run_yolo_prediction(
                        offline_img, c_thr, i_thr, per_class, imgsz, max_det, device, half
                    )
                    elapsed = max(time.perf_counter() - t0, 1e-6)
                annotated = draw_detections(offline_img.copy(), ob, labs, sc)
                annotated = draw_hud(annotated, Counter(d["label"] for d in dets), 1.0 / elapsed)
                st.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), use_container_width=True)
                if dets:
                    odf = pd.DataFrame(dets)
                    odf["confidence"] = (odf["confidence"] * 100).round(1).astype(str) + "%"
                    st.dataframe(odf[["display_label", "confidence", "status", "x1", "y1", "x2", "y2"]], use_container_width=True, hide_index=True)
                    ov = sum(1 for d in dets if d["violation"])
                    if ov:
                        st.error(f"{ov} violation detection(s) in this image. The exact classes and confidences are shown above.")
                    else:
                        st.success("No violation classes were detected in this image.")
                else:
                    st.info("No object met the active confidence thresholds.")
        except Exception as exc:
            st.error(f"Image analysis failed: {type(exc).__name__}: {exc}")


# -----------------------------------------------------------------------------
# 10c. DETAILED LIVE PREDICTIONS + SESSION REPORT
# -----------------------------------------------------------------------------
st.markdown("#### 🔎 Detailed predictions")
detail_ph = st.empty()


def render_detailed_predictions() -> None:
    rows = STATE.detailed_snapshot()
    if not rows:
        detail_ph.markdown(
            "<div class='ppe-card'><h4>Per-object results</h4>"
            "<span style='color:#5b6b8c'>No detections available yet.</span></div>",
            unsafe_allow_html=True,
        )
        return
    df = pd.DataFrame(rows)
    df["confidence"] = (df["confidence"] * 100).round(1).astype(str) + "%"
    display = df[["display_label", "confidence", "status", "x1", "y1", "x2", "y2"]].copy()
    display.columns = ["Class", "Confidence", "Status", "X1", "Y1", "X2", "Y2"]
    detail_ph.dataframe(display, use_container_width=True, hide_index=True, height=min(360, 90 + 35 * len(display)))


def current_report_bytes() -> Tuple[bytes, bytes]:
    rows = STATE.detailed_snapshot()
    counts, fps, total_frames = STATE.snapshot()
    events = STATE.get_events()
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model_path": MODEL_PATH,
        "total_processed_frames": total_frames,
        "current_fps": round(float(fps), 2),
        "class_counts": counts,
        "detections": rows,
        "events": events,
        "model_note": "Predictions are limited to classes learned by final.pt; no unsupported class is inferred.",
    }
    json_bytes = json.dumps(report, indent=2, default=str).encode("utf-8")
    csv_df = pd.DataFrame(rows)
    csv_bytes = csv_df.to_csv(index=False).encode("utf-8") if not csv_df.empty else b"label,confidence,status,x1,y1,x2,y2\n"
    return csv_bytes, json_bytes


# -----------------------------------------------------------------------------
# 10d. VIOLATION SNAPSHOT GALLERY
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# VIOLATION SNAPSHOT GALLERY  (preview + download)
# -----------------------------------------------------------------------------
csv_bytes, json_bytes = current_report_bytes()
rc1, rc2, rc3 = st.columns([1, 1, 2])
rc1.download_button("⬇️ Export detections CSV", csv_bytes, file_name="ppe_detections.csv", mime="text/csv", key="export_csv")
rc2.download_button("⬇️ Export session JSON", json_bytes, file_name="ppe_session_report.json", mime="application/json", key="export_json")
rc3.caption("The report contains the current per-object predictions, counts, events, FPS, and model path.")

st.markdown("#### 📸 Violation snapshots")
snap_controls = st.container()
snap_gallery = st.container()


def render_snapshots() -> None:
    shots = STATE.get_snapshots()
    with snap_controls:
        c1, c2, c3 = st.columns([1, 1, 2])
        c1.button("🔄 Refresh gallery", key="snap_refresh")
        if shots:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, s in enumerate(shots, 1):
                    stamp = datetime.fromtimestamp(s["ts"]).strftime("%Y%m%d-%H%M%S")
                    zf.writestr(f"violation_{i:03d}_{stamp}.jpg", s["jpeg"])
            c2.download_button(
                "⬇️ Download all (ZIP)", zip_buf.getvalue(),
                file_name="ppe_violations.zip", mime="application/zip",
                key="snap_zip",
            )
            if c3.button("🗑️ Clear snapshots", key="snap_clear"):
                STATE.clear_snapshots()
                st.rerun()
            c3.caption(f"{len(shots)} snapshot(s) captured this session.")
        else:
            c2.caption("No violation frames captured yet.")

    with snap_gallery:
        if not shots:
            return
        # newest first, 4 per row
        latest = list(reversed(shots))[:16]
        for start in range(0, len(latest), 4):
            cols = st.columns(4)
            for col, s in zip(cols, latest[start:start + 4]):
                stamp = datetime.fromtimestamp(s["ts"]).strftime("%H:%M:%S")
                with col:
                    st.image(s["jpeg"], caption=f"{stamp} · {', '.join(s['labels'])}",
                             use_container_width=True)
                    st.download_button(
                        "Download", s["jpeg"],
                        file_name=f"violation_{stamp.replace(':', '')}.jpg",
                        mime="image/jpeg", key=f"dl_{s['ts']}",
                    )


# -----------------------------------------------------------------------------
# 11. LIVE REFRESH LOOP
# -----------------------------------------------------------------------------
# The WebRTC worker keeps pushing fresh counts; the main thread drains the queue
# and repaints only the metric placeholders. Because we write into `st.empty()`
# containers, no full rerun (and no flicker) is required. The snapshot gallery
# uses real widgets, so it is rendered once per rerun (use "Refresh gallery").
render_dashboard(*STATE.snapshot()[:2])
render_history()
render_alert()
render_detailed_predictions()
render_runtime_error()
render_snapshots()

if ctx.state.playing:
    _last_chart = 0.0
    while ctx.state.playing:
        try:
            counts, fps = result_q.get(timeout=1.0)
        except queue.Empty:
            counts, fps, _ = STATE.snapshot()
        render_dashboard(counts, fps)
        render_alert()
        render_detailed_predictions()
        render_runtime_error()
        now = time.time()
        if now - _last_chart > 1.0:   # redraw the chart ~1×/s (it is heavier)
            render_history()
            _last_chart = now
        time.sleep(0.08)  # ~12 UI updates/sec: smooth without hogging the CPU


st.markdown("#### 🧾 Alert event log")
events = STATE.get_events()
if events:
    edf = pd.DataFrame(events)
    edf["time"] = pd.to_datetime(edf["ts"], unit="s").dt.strftime("%Y-%m-%d %H:%M:%S")
    edf["labels"] = edf["labels"].apply(lambda x: ", ".join(x))
    st.dataframe(edf[["time", "type", "violations", "labels"]], use_container_width=True, hide_index=True)
else:
    st.caption("No confirmed violation events yet.")

st.divider()
with st.expander("ℹ️ Deployment & customisation notes"):
    st.markdown(
        """
**Run locally**

```bash
pip install -r requirements.txt
streamlit run app.py
```

**Model** — the trained YOLO checkpoint is intentionally kept at the existing path:
`/Users/universalimpex/Downloads/final.pt`.
Class names are read straight from the checkpoint. Violation/compliance labels are
classified from their names only; the app does not invent PPE classes that are absent
from the trained model. Detailed predictions include class, confidence and bounding box.

**Performance** — on CPU use `imgsz=320–416` and *Process every Nth frame = 2–3*.
With CUDA available Ultralytics uses the GPU automatically.

**Remote/HTTPS deployment** — browsers only expose cameras over HTTPS or
localhost. Behind NAT, add a TURN server to `rtc_configuration`.

**Styling** — every colour lives in the `THEME` dict; the whole stylesheet is the
`CUSTOM_CSS` string injected with `st.markdown(..., unsafe_allow_html=True)`.
        """
    )
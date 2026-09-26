"""Centralized configuration for SAFE SIGHT AI Platform.

Contains all tuneable constants, hardware performance profiles, color tokens,
zone definitions, and filesystem paths.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Base Directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "ppe_events.db"

# Set Ultralytics config, runs directory, and Matplotlib cache inside workspace
CACHE_DIR = PROJECT_ROOT / ".cache" / "ultralytics"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
MPL_CACHE_DIR = PROJECT_ROOT / ".cache" / "matplotlib"
MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

os.environ["YOLO_CONFIG_DIR"] = str(CACHE_DIR)
os.environ["ULTRALYTICS_CONFIG_DIR"] = str(CACHE_DIR)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))

# Model Settings: Priority to user's custom trained PPE weights
DEFAULT_MODEL_PATH = "models/best.pt"
MODEL_PATH = os.environ.get("PPE_MODEL_PATH", DEFAULT_MODEL_PATH)
FALLBACK_MODEL = "models/best.pt"
MODEL_ROOTS = ["models", "runs/detect/train5/weights", str(PROJECT_ROOT)]

# Inference Threshold Defaults calibrated for custom 11-class PPE model
CONFIDENCE_THRESHOLD = float(os.environ.get("PPE_CONF", "0.08"))
IOU_THRESHOLD = float(os.environ.get("PPE_IOU", "0.45"))
MAX_DETECTIONS = int(os.environ.get("PPE_MAX_DET", "50"))

# Calibrated per-class confidence floors: High recall on all 5 PPE classes (vest, gloves, helmet, boots, goggles)
DEFAULT_PER_CLASS_CONF: dict[str, float] = {
    "person": 0.05,
    "helmet": 0.05,
    "no-helmet": 0.05,
    "no_helmet": 0.05,
    "goggles": 0.04,
    "no-goggle": 0.04,
    "no_goggle": 0.04,
    "no-goggles": 0.04,
    "no_goggles": 0.04,
    "gloves": 0.04,
    "no-gloves": 0.04,
    "no_gloves": 0.04,
    "vest": 0.05,
    "no-vest": 0.05,
    "no_vest": 0.05,
    "boots": 0.05,
    "no-boots": 0.05,
    "no_boots": 0.05,
}

# WebRTC & Camera Feed Defaults (Ultra High Definition Capture)
CAMERA_WIDTH = 3840
CAMERA_HEIGHT = 2160
CAMERA_FPS = 30

# Performance Profiles
@dataclass(frozen=True)
class PerformanceProfile:
    name: str
    inference_size: int
    frame_skip: int
    description: str

PERFORMANCE_MODES: dict[str, PerformanceProfile] = {
    "balanced": PerformanceProfile(
        name="Balanced HD",
        inference_size=640,
        frame_skip=1,
        description="Native 640px YOLO inference optimized for smooth 30 FPS throughput."
    ),
    "performance": PerformanceProfile(
        name="High FPS Turbo",
        inference_size=480,
        frame_skip=2,
        description="High-speed 480px inference skipping alternate frames for zero-lag streaming."
    ),
    "precision": PerformanceProfile(
        name="Ultra Precision",
        inference_size=960,
        frame_skip=1,
        description="Deep 960px high-resolution inference for distant workers and small PPE."
    )
}
DEFAULT_MODE = "balanced"

# 8K & Ultra Clarity Video Rendering Targets
CLARITY_RESOLUTIONS: dict[str, tuple[int, int]] = {
    "8K": (7680, 4320),
    "4K": (3840, 2160),
    "2K": (2560, 1440),
    "1080p": (1920, 1080),
}
DEFAULT_CLARITY_TARGET = "8K"

# Temporal Alert Filters (Debounce)
VIOLATION_CONFIRM_FRAMES = int(os.environ.get("PPE_CONFIRM_FRAMES", "2"))
VIOLATION_CLEAR_FRAMES = int(os.environ.get("PPE_CLEAR_FRAMES", "3"))

# Rate Limiting & Storage
HISTORY_LEN = 600
EVENT_LOG_LEN = 200
MAX_SNAPSHOTS = 50
MAX_DB_EVENTS = 5000
CAPTURE_COOLDOWN_SEC = 3.0
JPEG_QUALITY = 90
DEFAULT_AUDIO_ALERTS_ENABLED = False

# Upload & Model Limits
MAX_VIDEO_UPLOAD_BYTES = 500 * 1024 * 1024
MAX_IMAGE_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_MODEL_UPLOAD_BYTES = 250 * 1024 * 1024
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


# Secure-by-default trust boundary: browser checkpoint uploads and external
# model paths are OFF unless an administrator explicitly opts in for a
# controlled session. Never enable on an internet-exposed operator instance.
ALLOW_EXTERNAL_MODEL_PATH = _env_bool("PPE_ALLOW_EXTERNAL_MODEL_PATH", False)
MODEL_UPLOAD_ENABLED = _env_bool("PPE_ENABLE_MODEL_UPLOAD", False)

# Shopfloor Zone Configuration
@dataclass
class ZoneConfig:
    id: str
    name: str
    type: str = "Standard"  # "Standard" | "Restricted"
    capacity: int = 5
    polygon: list[tuple[float, float]] = field(default_factory=list)  # normalized (0-1)

DEFAULT_ZONES: list[ZoneConfig] = [
    ZoneConfig(
        id="Z-01",
        name="Assembly Line A",
        type="Standard",
        capacity=6,
        polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)]
    ),
    ZoneConfig(
        id="Z-02",
        name="Heavy Machinery Bay",
        type="Restricted",
        capacity=2,
        polygon=[(0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (0.5, 0.5)]
    ),
    ZoneConfig(
        id="Z-03",
        name="Material Staging",
        type="Standard",
        capacity=8,
        polygon=[(0.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0)]
    ),
    ZoneConfig(
        id="Z-04",
        name="Quality Inspection",
        type="Standard",
        capacity=4,
        polygon=[(0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0)]
    ),
]

# Required PPE Defaults
DEFAULT_REQUIRED_PPE = ["helmet", "vest", "boots", "gloves", "goggles"]

# SAFE SIGHT AI Theme Tokens (Dark and Light)
THEME_DARK = {
    "bg": "#121b1e",
    "panel": "#1a2529",
    "sidebar": "#172125",
    "text": "#d2dcdf",
    "heading": "#f0f5f3",
    "muted": "#8b9ca4",
    "secondary": "#a1b0b5",
    "line": "#2c393d",
    "green": "#4bc6a1",
    "green_soft": "#173c32",
    "red": "#ef9292",
    "red_soft": "#442c2b",
    "amber": "#e9b963",
    "amber_soft": "#3e3726",
    "blue": "#93b4e0",
    "blue_soft": "#26384b",
    "hover": "#243137",
    "input": "#172327",
    "ok": "#4bc6a1",
    "bad": "#ef9292",
    "warn": "#e9b963",
    "accent": "#93b4e0",
}

THEME_LIGHT = {
    "bg": "#f7f9fa",
    "panel": "#ffffff",
    "sidebar": "#ffffff",
    "text": "#1f2937",
    "heading": "#111827",
    "muted": "#52606d",
    "secondary": "#4b5563",
    "line": "#e5e7eb",
    "green": "#047857",
    "green_soft": "#eaf7f1",
    "red": "#b91c1c",
    "red_soft": "#fcecec",
    "amber": "#92400e",
    "amber_soft": "#fcf4e5",
    "blue": "#1d4ed8",
    "blue_soft": "#eaf1fb",
    "hover": "#f3f4f6",
    "input": "#ffffff",
    "ok": "#047857",
    "bad": "#b91c1c",
    "warn": "#92400e",
    "accent": "#1d4ed8",
}

# Drawing Colors (BGR format for OpenCV overlays)
BGR_GREEN: tuple[int, int, int] = (161, 198, 75)   # #4bc6a1
BGR_RED: tuple[int, int, int] = (146, 146, 239)    # #ef9292
BGR_AMBER: tuple[int, int, int] = (99, 185, 233)   # #e9b963
BGR_BLUE: tuple[int, int, int] = (224, 180, 147)   # #93b4e0
BGR_WHITE: tuple[int, int, int] = (255, 255, 255)
BGR_DARK: tuple[int, int, int] = (30, 27, 18)      # #121b1e

# Backwards compatibility aliases
BGR_OK = BGR_GREEN
BGR_BAD = BGR_RED
BGR_WARN = BGR_AMBER
BGR_ACCENT = BGR_BLUE

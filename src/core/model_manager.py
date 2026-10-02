"""Hardware acceleration detection, model resolution, and lifecycle management.

Handles device selection (MPS, CUDA, CPU), precision tuning (FP16), and cached
model warm-up passes.
"""

from __future__ import annotations

import os

import numpy as np

from src.config.settings import CACHE_DIR, FALLBACK_MODEL, MODEL_PATH, PROJECT_ROOT

# Ensure Ultralytics config is local before importing YOLO
os.environ["YOLO_CONFIG_DIR"] = str(CACHE_DIR)
from ultralytics import YOLO


def available_devices() -> list[str]:
    """Return all available inference hardware devices."""
    devices = ["cpu"]
    try:
        import torch

        if torch.cuda.is_available():
            devices = [f"cuda:{i}" for i in range(torch.cuda.device_count())] + devices
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() and "mps" not in devices:
            # Place MPS ahead of CPU for Mac
            devices.insert(0, "mps")
    except Exception:
        pass
    return devices


def best_device() -> str:
    """Select the fastest available compute device."""
    devs = available_devices()
    return devs[0] if devs else "cpu"


def device_label(dev: str) -> str:
    """Format device name for display."""
    if dev.startswith("cuda"):
        try:
            import torch

            idx = int(dev.split(":")[1]) if ":" in dev else 0
            name = torch.cuda.get_device_name(idx)
            return f"GPU · {name}"
        except Exception:
            return f"GPU · {dev.upper()}"
    if dev == "mps":
        return "GPU · Apple Silicon (MPS)"
    return "CPU (Standard)"


def resolve_model_path(requested_path: str | None = None) -> tuple[str, bool]:
    """Resolve model weights path. Returns (path, is_fallback)."""
    candidates = []
    if requested_path:
        candidates.append(requested_path)
    if MODEL_PATH:
        candidates.append(MODEL_PATH)
    candidates.extend(
        [
            str(PROJECT_ROOT / "models" / "best.pt"),
            "models/best.pt",
            "runs/detect/train5/weights/best.pt",
            str(PROJECT_ROOT / "runs" / "detect" / "train5" / "weights" / "best.pt"),
            str(PROJECT_ROOT / "models" / "final.pt"),
        ]
    )

    for c in candidates:
        if c and os.path.isfile(c):
            return c, False

    # Return standard YOLO fallback if custom weights not found
    return FALLBACK_MODEL, True


def load_model(weights_path: str, device: str = "cpu", half: bool = False) -> YOLO:
    """Load and warm up Ultralytics YOLO model."""
    if not weights_path or not os.path.isfile(weights_path):
        raise FileNotFoundError(f"Model checkpoint not found on disk: {weights_path}")
    model = YOLO(weights_path)
    try:
        model.to(device)
        if half:
            model.half()
    except Exception:
        pass

    # Warmup inference to eliminate first-frame latency spike
    try:
        dummy = np.zeros((320, 320, 3), dtype=np.uint8)
        model.predict(dummy, device=device, verbose=False)
    except Exception:
        pass

    return model


def get_class_names(model: YOLO) -> list[str]:
    """Extract list of class names from loaded YOLO model."""
    if model is None:
        return []
    names = getattr(model, "names", {})
    if isinstance(names, dict):
        return [str(names[k]) for k in sorted(names.keys())]
    if isinstance(names, (list, tuple)):
        return [str(x) for x in names]
    return []

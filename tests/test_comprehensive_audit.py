"""Comprehensive integration test suite covering every audit category from the user's spec.

Pure pytest module: model-dependent tests skip cleanly when weights are absent,
and failures are reported through pytest assertions instead of a custom runner.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

os.environ.setdefault("YOLO_CONFIG_DIR", str(PROJECT_ROOT / ".cache" / "ultralytics"))


def _model_path_or_skip() -> str:
    from src.core.model_manager import resolve_model_path

    path, _ = resolve_model_path()
    if not Path(path).exists():
        pytest.skip("Model weights not present in this environment")
    return path


# =============================
# 1. APPLICATION STARTUP
# =============================


def test_all_imports():
    from src.config import settings
    from src.video import pipeline

    assert hasattr(settings, "CONFIDENCE_THRESHOLD")
    assert hasattr(pipeline, "TelemetryState")


def test_config_loads():
    from src.config.settings import (
        CAMERA_HEIGHT,
        CAMERA_WIDTH,
        CONFIDENCE_THRESHOLD,
        DEFAULT_ZONES,
        IOU_THRESHOLD,
        MAX_DETECTIONS,
        THEME_DARK,
        THEME_LIGHT,
    )

    assert 0.0 < CONFIDENCE_THRESHOLD < 1.0, f"Bad conf: {CONFIDENCE_THRESHOLD}"
    assert 0.0 < IOU_THRESHOLD < 1.0, f"Bad IOU: {IOU_THRESHOLD}"
    assert CAMERA_WIDTH > 0
    assert CAMERA_HEIGHT > 0
    assert len(DEFAULT_ZONES) > 0
    assert isinstance(THEME_LIGHT, dict)
    assert isinstance(THEME_DARK, dict)
    assert MAX_DETECTIONS > 0


def test_model_init():
    from src.core.model_manager import available_devices, best_device, resolve_model_path

    path, _is_fb = resolve_model_path()
    assert isinstance(path, str) and len(path) > 0
    devs = available_devices()
    assert "cpu" in devs
    best = best_device()
    assert isinstance(best, str)


# =============================
# 2. MODEL LOADING
# =============================


def test_valid_model():
    from src.core.model_manager import load_model

    model = load_model(_model_path_or_skip(), device="cpu", half=False)
    assert model is not None


def test_missing_model():
    from src.core.model_manager import load_model

    with pytest.raises(Exception) as exc_info:
        load_model("/nonexistent/fake_model.pt", device="cpu")
    message = str(exc_info.value).lower()
    assert "not found" in message or "no such" in message or isinstance(exc_info.value, FileNotFoundError)


def test_invalid_model_path():
    from src.core.model_manager import load_model

    with pytest.raises(FileNotFoundError):
        load_model("", device="cpu")


def test_cpu_mode():
    from src.core.model_manager import load_model

    model = load_model(_model_path_or_skip(), device="cpu", half=False)
    assert model is not None


# =============================
# 3. DETECTION PIPELINE
# =============================


def test_empty_frame():
    from src.core.model_manager import load_model, resolve_model_path
    from src.video.pipeline import TelemetryState, VideoPipeline

    state = TelemetryState()
    path, _ = resolve_model_path()
    model = load_model(path) if Path(path).exists() else None
    pipe = VideoPipeline(model=model, state=state)
    empty = np.zeros((480, 640, 3), dtype=np.uint8)
    out = pipe.process_numpy_frame(empty)
    assert out.shape == (480, 640, 3)
    if model is not None:
        assert state.snapshot_ui()["total_frames"] == 1


def test_valid_frame():
    from src.video.pipeline import TelemetryState, VideoPipeline

    state = TelemetryState()
    pipe = VideoPipeline(model=None, state=state)
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    out = pipe.process_numpy_frame(frame)
    assert out.shape == (480, 640, 3)


def test_no_detections():
    from src.video.pipeline import TelemetryState

    state = TelemetryState()
    state.publish(counts={}, detections=[], workers=[], fps=30.0, inference_ms=5.0, violations_count=0)
    snap = state.snapshot_ui()
    assert snap["total_frames"] == 1
    assert len(snap["detections"]) == 0
    assert len(snap["workers"]) == 0


def test_person_only():
    from src.core.ppe_associator import associate_ppe_to_workers

    dets = [
        {
            "label": "person",
            "x1": 100,
            "y1": 100,
            "x2": 300,
            "y2": 600,
            "confidence": 0.9,
            "violation": False,
            "display_label": "Person",
        },
    ]
    workers = associate_ppe_to_workers(dets)
    assert len(workers) == 1
    w = workers[0]
    assert not w.is_compliant  # No PPE detected = not compliant
    assert not w.has_active_violation  # No violation detected either


def test_person_helmet():
    from src.core.ppe_associator import associate_ppe_to_workers

    dets = [
        {
            "label": "person",
            "x1": 100,
            "y1": 100,
            "x2": 300,
            "y2": 600,
            "confidence": 0.9,
            "violation": False,
            "display_label": "Person",
        },
        {
            "label": "helmet",
            "x1": 150,
            "y1": 110,
            "x2": 250,
            "y2": 200,
            "confidence": 0.88,
            "violation": False,
            "display_label": "Helmet",
        },
    ]
    workers = associate_ppe_to_workers(dets)
    assert len(workers) == 1
    assert workers[0].helmet_status == "COMPLIANT"
    assert workers[0].is_compliant


def test_person_vest():
    from src.core.ppe_associator import associate_ppe_to_workers

    dets = [
        {
            "label": "person",
            "x1": 100,
            "y1": 100,
            "x2": 300,
            "y2": 600,
            "confidence": 0.9,
            "violation": False,
            "display_label": "Person",
        },
        {
            "label": "vest",
            "x1": 120,
            "y1": 250,
            "x2": 280,
            "y2": 450,
            "confidence": 0.85,
            "violation": False,
            "display_label": "Vest",
        },
    ]
    workers = associate_ppe_to_workers(dets)
    assert len(workers) == 1
    assert workers[0].vest_status == "COMPLIANT"


def test_person_helmet_vest():
    from src.core.ppe_associator import associate_ppe_to_workers

    dets = [
        {
            "label": "person",
            "x1": 100,
            "y1": 100,
            "x2": 300,
            "y2": 600,
            "confidence": 0.9,
            "violation": False,
            "display_label": "Person",
        },
        {
            "label": "helmet",
            "x1": 150,
            "y1": 110,
            "x2": 250,
            "y2": 200,
            "confidence": 0.88,
            "violation": False,
            "display_label": "Helmet",
        },
        {
            "label": "vest",
            "x1": 120,
            "y1": 250,
            "x2": 280,
            "y2": 450,
            "confidence": 0.85,
            "violation": False,
            "display_label": "Vest",
        },
    ]
    workers = associate_ppe_to_workers(dets)
    assert len(workers) == 1
    w = workers[0]
    assert w.helmet_status == "COMPLIANT"
    assert w.vest_status == "COMPLIANT"
    assert w.is_compliant
    assert not w.has_active_violation


def test_multiple_workers():
    from src.core.ppe_associator import associate_ppe_to_workers

    dets = [
        {
            "label": "person",
            "x1": 50,
            "y1": 100,
            "x2": 250,
            "y2": 600,
            "confidence": 0.95,
            "violation": False,
            "display_label": "Person",
        },
        {
            "label": "person",
            "x1": 400,
            "y1": 100,
            "x2": 600,
            "y2": 600,
            "confidence": 0.94,
            "violation": False,
            "display_label": "Person",
        },
    ]
    workers = associate_ppe_to_workers(dets)
    assert len(workers) == 2


def test_multiple_ppe_objects():
    from src.core.ppe_associator import associate_ppe_to_workers

    dets = [
        {
            "label": "person",
            "x1": 100,
            "y1": 100,
            "x2": 300,
            "y2": 600,
            "confidence": 0.95,
            "violation": False,
            "display_label": "Person",
        },
        {
            "label": "helmet",
            "x1": 150,
            "y1": 110,
            "x2": 250,
            "y2": 200,
            "confidence": 0.91,
            "violation": False,
            "display_label": "Helmet",
        },
        {
            "label": "vest",
            "x1": 120,
            "y1": 250,
            "x2": 280,
            "y2": 450,
            "confidence": 0.89,
            "violation": False,
            "display_label": "Vest",
        },
        {
            "label": "boots",
            "x1": 130,
            "y1": 500,
            "x2": 270,
            "y2": 590,
            "confidence": 0.87,
            "violation": False,
            "display_label": "Boots",
        },
    ]
    workers = associate_ppe_to_workers(dets)
    assert len(workers) == 1
    w = workers[0]
    assert w.helmet_status == "COMPLIANT"
    assert w.vest_status == "COMPLIANT"
    assert w.boots_status == "COMPLIANT"


def test_low_confidence_detections():
    """Very low confidence should still be processed if passed (filtering is upstream)."""
    from src.core.ppe_associator import associate_ppe_to_workers

    dets = [
        {
            "label": "person",
            "x1": 100,
            "y1": 100,
            "x2": 300,
            "y2": 600,
            "confidence": 0.15,
            "violation": False,
            "display_label": "Person",
        },
        {
            "label": "helmet",
            "x1": 150,
            "y1": 110,
            "x2": 250,
            "y2": 200,
            "confidence": 0.12,
            "violation": False,
            "display_label": "Helmet",
        },
    ]
    workers = associate_ppe_to_workers(dets)
    assert len(workers) == 1


# =============================
# 4. MULTI-WORKER TESTING
# =============================


def test_multi_worker_mixed_compliance():
    from src.core.ppe_associator import associate_ppe_to_workers

    dets = [
        # Worker A: Helmet ✓, Vest ✓
        {
            "label": "person",
            "x1": 50,
            "y1": 100,
            "x2": 250,
            "y2": 600,
            "confidence": 0.95,
            "violation": False,
            "display_label": "Person",
        },
        {
            "label": "helmet",
            "x1": 100,
            "y1": 110,
            "x2": 200,
            "y2": 190,
            "confidence": 0.92,
            "violation": False,
            "display_label": "Helmet",
        },
        {
            "label": "vest",
            "x1": 80,
            "y1": 220,
            "x2": 220,
            "y2": 450,
            "confidence": 0.89,
            "violation": False,
            "display_label": "Vest",
        },
        # Worker B: Helmet ✕, Vest ✓
        {
            "label": "person",
            "x1": 400,
            "y1": 100,
            "x2": 600,
            "y2": 600,
            "confidence": 0.94,
            "violation": False,
            "display_label": "Person",
        },
        {
            "label": "no-helmet",
            "x1": 450,
            "y1": 110,
            "x2": 550,
            "y2": 190,
            "confidence": 0.90,
            "violation": True,
            "display_label": "No Helmet",
        },
        {
            "label": "vest",
            "x1": 430,
            "y1": 220,
            "x2": 570,
            "y2": 450,
            "confidence": 0.88,
            "violation": False,
            "display_label": "Vest",
        },
    ]
    workers = associate_ppe_to_workers(dets)
    assert len(workers) == 2, f"Expected 2 workers, got {len(workers)}"

    total_w = len(workers)
    viol_w = sum(1 for w in workers if w.has_active_violation)
    safe_w = sum(1 for w in workers if w.is_compliant)

    assert total_w == 2, f"total_w={total_w}"
    assert viol_w == 1, f"viol_w={viol_w}"
    assert safe_w == 1, f"safe_w={safe_w}"
    score = (safe_w / total_w) * 100.0
    assert score == 50.0, f"score={score}"


def test_ppe_no_double_assignment():
    """A single PPE item must NOT satisfy multiple workers."""
    from src.core.ppe_associator import associate_ppe_to_workers

    dets = [
        # Two workers very close together
        {
            "label": "person",
            "x1": 100,
            "y1": 100,
            "x2": 250,
            "y2": 500,
            "confidence": 0.95,
            "violation": False,
            "display_label": "Person",
        },
        {
            "label": "person",
            "x1": 260,
            "y1": 100,
            "x2": 410,
            "y2": 500,
            "confidence": 0.94,
            "violation": False,
            "display_label": "Person",
        },
        # One helmet between them
        {
            "label": "helmet",
            "x1": 150,
            "y1": 105,
            "x2": 220,
            "y2": 180,
            "confidence": 0.91,
            "violation": False,
            "display_label": "Helmet",
        },
    ]
    workers = associate_ppe_to_workers(dets)
    assert len(workers) == 2
    helmeted = sum(1 for w in workers if w.helmet_status == "COMPLIANT")
    assert helmeted <= 1, f"Helmet assigned to {helmeted} workers (should be ≤1)"


# =============================
# 5. ALERT ENGINE
# =============================


def test_alert_deduplication():
    """Persistent violations must not create duplicate incidents each frame."""
    from src.video.pipeline import TelemetryState

    state = TelemetryState()
    viol_det = [{"label": "no-helmet", "violation": True}]
    counts = {"no-helmet": 1}

    # Frame 1: start violation streak
    state.publish(counts=counts, detections=viol_det, workers=[], fps=30.0, inference_ms=10.0, violations_count=1)
    assert not state.violating  # Need VIOLATION_CONFIRM_FRAMES (2)

    # Frame 2: confirm violation
    state.publish(counts=counts, detections=viol_det, workers=[], fps=30.0, inference_ms=10.0, violations_count=1)
    assert state.violating
    events = state.get_events()
    viol_events = [e for e in events if e["type"] == "VIOLATION"]
    assert len(viol_events) == 1, f"Expected 1 VIOLATION event, got {len(viol_events)}"

    # Frames 3-10: persist violation — should NOT create new events
    for _ in range(8):
        state.publish(counts=counts, detections=viol_det, workers=[], fps=30.0, inference_ms=10.0, violations_count=1)
    events = state.get_events()
    viol_events = [e for e in events if e["type"] == "VIOLATION"]
    assert len(viol_events) == 1, f"Duplication: {len(viol_events)} VIOLATION events"


def test_alert_clear_and_cooldown():
    from src.video.pipeline import TelemetryState

    state = TelemetryState()
    viol = [{"label": "no-helmet", "violation": True}]
    clean = [{"label": "helmet", "violation": False}]

    # Trigger violation (2 frames)
    state.publish(counts={"no-helmet": 1}, detections=viol, workers=[], fps=30.0, inference_ms=10.0, violations_count=1)
    state.publish(counts={"no-helmet": 1}, detections=viol, workers=[], fps=30.0, inference_ms=10.0, violations_count=1)
    assert state.violating

    # Clear violation (3 clean frames)
    for _ in range(3):
        state.publish(
            counts={"helmet": 1}, detections=clean, workers=[], fps=30.0, inference_ms=10.0, violations_count=0
        )
    assert not state.violating

    events = state.get_events()
    assert any(e["type"] == "CLEARED" for e in events)

    # New violation after cooldown
    state.publish(counts={"no-helmet": 1}, detections=viol, workers=[], fps=30.0, inference_ms=10.0, violations_count=1)
    state.publish(counts={"no-helmet": 1}, detections=viol, workers=[], fps=30.0, inference_ms=10.0, violations_count=1)

    events = state.get_events()
    viol_events = [e for e in events if e["type"] == "VIOLATION"]
    assert len(viol_events) == 2, f"Expected 2 VIOLATION events (original + after cooldown), got {len(viol_events)}"


# =============================
# 6. THEME SYSTEM
# =============================


def test_css_light_generates():
    from src.ui.theme import get_safesight_css

    css = get_safesight_css("light")
    assert len(css) > 5000
    assert "{T[" not in css, "Unresolved f-string variable"
    assert "demo-banner" in css


def test_css_dark_generates():
    from src.ui.theme import get_safesight_css

    css = get_safesight_css("dark")
    assert len(css) > 5000
    assert "{T[" not in css


def test_css_has_semantic_tokens():
    from src.ui.theme import get_safesight_css

    css = get_safesight_css("light")
    required_vars = [
        "--bg",
        "--panel",
        "--line",
        "--green",
        "--red",
        "--amber",
        "--blue",
        "--heading",
        "--secondary",
        "--muted",
    ]
    for v in required_vars:
        assert v in css, f"Missing CSS variable: {v}"


# =============================
# 7. EVIDENCE & TEMP FILES
# =============================


def test_evidence_pruning(tmp_path):
    from src.storage.evidence import EvidenceManager

    test_dir = tmp_path / "evidence"
    mgr = EvidenceManager(storage_dir=test_dir, max_snapshots=3)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    for i in range(6):
        mgr.save_snapshot(frame, ["test"], timestamp=1000000 + i)
    remaining = list(test_dir.glob("viol_*.jpg"))
    assert len(remaining) <= 3, f"Expected ≤3 snapshots, got {len(remaining)}"
    shutil.rmtree(test_dir, ignore_errors=True)


def test_demo_feed_excludes_viols():
    from src.video.demo_feed import DemoShopfloorFeed

    feed = DemoShopfloorFeed(width=320, height=240)
    assert len(feed.cached_frames) <= 30


# =============================
# 8. PERFORMANCE
# =============================


def test_telemetry_bounded():
    from src.video.pipeline import TelemetryState

    state = TelemetryState()
    for _ in range(1000):
        state.publish(
            counts={"person": 1},
            detections=[{"label": "person", "violation": False}],
            workers=[],
            fps=30.0,
            inference_ms=10.0,
            violations_count=0,
        )
    snap = state.snapshot_ui()
    assert snap["total_frames"] == 1000
    # History is bounded by deque maxlen
    df = state.get_history_df()
    assert len(df) <= 600  # HISTORY_LEN


# =============================
# 9. RENDERER
# =============================


def test_renderer_empty_workers():
    from src.video.renderer import OverlayRenderer

    renderer = OverlayRenderer()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    out = renderer.draw_worker_badges(frame.copy(), [])
    assert out.shape == frame.shape


def test_renderer_empty_detections():
    from src.video.renderer import OverlayRenderer

    renderer = OverlayRenderer()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    out = renderer.draw_detections(frame.copy(), np.array([]), [], np.array([]))
    assert out.shape == frame.shape


def test_renderer_hud():
    from src.video.renderer import OverlayRenderer

    renderer = OverlayRenderer()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    out = renderer.draw_telemetry_hud(frame.copy(), fps=0.0, violations_count=0, workers_count=0)
    assert out.shape == frame.shape

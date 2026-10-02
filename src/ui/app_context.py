"""Application context & session-state bootstrap for the SAFE SIGHT AI shell.

Centralizes every ``st.session_state`` default (A2: single ``init_state()``
entry point) and builds the immutable-ish :class:`AppContext` consumed by the
page modules under ``src/ui/pages/`` (A1 page split).

Rerun policy (A4): widgets trigger Streamlit's natural rerun; explicit
``st.rerun()`` is reserved for state mutations that change the global layout
or lifecycle — theme switch, device switch, camera start/stop, model change,
and destructive maintenance actions. Periodic refresh is done exclusively via
``st.fragment(run_every=...)`` scoped to the smallest possible DOM subtree.
"""

from __future__ import annotations

import importlib
import inspect
import os
from dataclasses import dataclass
from typing import Any

import streamlit as st

import src.video.renderer as _rend_mod
from src.config.settings import DEFAULT_AUDIO_ALERTS_ENABLED, DEFAULT_MODEL_PATH
from src.core.model_manager import (
    available_devices,
    best_device,
    get_class_names,
    load_model,
    resolve_model_path,
)
from src.storage.evidence import EvidenceManager
from src.video.camera import OpenCVCameraManager
from src.video.demo_feed import DemoShopfloorFeed
from src.video.pipeline import TelemetryState, VideoPipeline

# Hot-reload renderer module if running under a persistent server process with stale bytecode
if (
    not hasattr(_rend_mod.OverlayRenderer, "render_8k_clarity_canvas")
    or "show_labels" not in inspect.signature(_rend_mod.OverlayRenderer.render_8k_clarity_canvas).parameters
):
    _rend_mod = importlib.reload(_rend_mod)

from src.video.renderer import OverlayRenderer

# Bump when VideoPipeline/renderer internals change so stale cached pipelines
# from older code versions are rebuilt instead of monkey-patched.
_PIPELINE_KEY_VERSION = "v8"

_SESSION_DEFAULTS: dict[str, Any] = {
    "theme_mode": "light",
    "cam_stream_active": False,
    "audio_alarms_enabled": DEFAULT_AUDIO_ALERTS_ENABLED,
    "recent_inspections": [],  # List of (image, timestamp, worker_data)
    "overlay_show_labels": True,
    "overlay_show_conf_pct": True,
    "overlay_show_corner_brackets": True,
    "overlay_show_status_pills": True,
    "last_violation_streak": 0,
    "perf_mode_key": "balanced",
    "resolved_person_alerts": None,  # lazily materialized to set() below
    "acknowledged_person_alerts": None,
    "ppe_helmet": True,
    "ppe_vest": True,
    "ppe_boots": True,
    "ppe_gloves": True,
    "ppe_goggles": True,
}


def init_state() -> None:
    """Idempotently initialize every session-state key used by the app."""
    for key, default in _SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = set() if default is None else default

    if "telemetry_state" not in st.session_state:
        st.session_state.telemetry_state = TelemetryState()
    if "evidence_manager" not in st.session_state:
        st.session_state.evidence_manager = EvidenceManager()
    if "demo_feed" not in st.session_state:
        st.session_state.demo_feed = DemoShopfloorFeed()
    if "selected_device" not in st.session_state:
        st.session_state.selected_device = best_device()
    if "custom_model_path" not in st.session_state:
        resolved_path, _is_fallback = resolve_model_path(DEFAULT_MODEL_PATH)
        st.session_state.custom_model_path = resolved_path


@dataclass
class AppContext:
    """Everything a page module needs, built once per script run."""

    state: TelemetryState
    evidence: EvidenceManager
    demo_feed: DemoShopfloorFeed
    camera_manager: OpenCVCameraManager
    pipeline: VideoPipeline
    model: Any
    load_error: str | None
    device: str
    half: bool
    devices: list[str]
    class_names: list[str]
    model_name: str
    active_model_path: str


@st.cache_resource(show_spinner="Loading YOLO neural weights…", max_entries=4)
def _get_model(path: str, dev: str, use_half: bool):
    try:
        return load_model(path, device=dev, half=use_half), None
    except Exception as exc:
        return None, str(exc)


def build_context() -> AppContext:
    """Resolve hardware, load the neural model, and wire the video pipeline."""
    init_state()

    devices = available_devices()
    if st.session_state.selected_device not in devices:
        st.session_state.selected_device = best_device()
    device = st.session_state.selected_device
    half = device.startswith("cuda")

    active_model_path = st.session_state.custom_model_path
    if not active_model_path or not os.path.isfile(str(active_model_path)):
        fallback_path, _ = resolve_model_path(DEFAULT_MODEL_PATH)
        st.session_state.custom_model_path = fallback_path
        active_model_path = fallback_path

    model, load_err = _get_model(active_model_path, device, half)
    if model is None and active_model_path != DEFAULT_MODEL_PATH:
        fallback_path, _ = resolve_model_path(DEFAULT_MODEL_PATH)
        st.session_state.custom_model_path = fallback_path
        active_model_path = fallback_path
        model, load_err = _get_model(active_model_path, device, half)

    class_names = get_class_names(model) if model is not None else []
    model_name = os.path.basename(active_model_path) if active_model_path else "Custom PPE Model"

    state: TelemetryState = st.session_state.telemetry_state
    pipeline_key = f"{active_model_path}_{device}_{half}_{_PIPELINE_KEY_VERSION}"
    current_pipe = st.session_state.get("pipeline")
    renderer_sig = inspect.signature(
        getattr(getattr(current_pipe, "renderer", None), "render_8k_clarity_canvas", lambda: None)
    )
    is_renderer_stale = "show_labels" not in renderer_sig.parameters and not any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in renderer_sig.parameters.values()
    )

    if (
        current_pipe is None
        or st.session_state.get("_pipeline_key") != pipeline_key
        or is_renderer_stale
        or not hasattr(getattr(current_pipe, "renderer", None), "render_8k_clarity_canvas")
        or not hasattr(getattr(current_pipe, "renderer", None), "enhance_visual_clarity")
        or getattr(current_pipe, "model", None) is None
    ):
        st.session_state.pipeline = VideoPipeline(model=model, state=state, device=device, half=half)
        st.session_state._pipeline_key = pipeline_key

    pipeline: VideoPipeline = st.session_state.pipeline
    if model is not None and getattr(pipeline, "model", None) is not model:
        pipeline.model = model

    if (
        not hasattr(pipeline.renderer, "render_8k_clarity_canvas")
        or not hasattr(pipeline.renderer, "enhance_visual_clarity")
        or "show_labels" not in inspect.signature(pipeline.renderer.render_8k_clarity_canvas).parameters
    ):
        pipeline.renderer = OverlayRenderer()

    return AppContext(
        state=state,
        evidence=st.session_state.evidence_manager,
        demo_feed=st.session_state.demo_feed,
        camera_manager=OpenCVCameraManager.get_instance(),
        pipeline=pipeline,
        model=model,
        load_error=load_err,
        device=device,
        half=half,
        devices=devices,
        class_names=class_names,
        model_name=model_name,
        active_model_path=active_model_path,
    )

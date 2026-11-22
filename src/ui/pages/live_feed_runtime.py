"""Streaming runtime handlers for WebRTC, direct browser capture, and OpenCV viewports."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import cv2
import numpy as np
import streamlit as st

try:
    import av
    from streamlit_webrtc import (
        RTCConfiguration,
        WebRtcMode,
        webrtc_streamer,
    )

    HAS_WEBRTC = True
    RTC_CLOUD_CONFIGURATION = RTCConfiguration(
        {
            "iceServers": [
                {"urls": ["stun:stun.l.google.com:19302"]},
                {"urls": ["stun:stun1.l.google.com:19302"]},
                {"urls": ["stun:global.stun.twilio.com:3478"]},
            ]
        }
    )
except ImportError:
    HAS_WEBRTC = False
    RTC_CLOUD_CONFIGURATION = None

from src.config.settings import DEFAULT_ZONES
from src.core.zones import ZonePolicy
from src.ui.app_context import AppContext
from src.ui.components import (
    build_workers_status_dataframe,
    play_violation_chime,
    render_compliance_panel,
    render_empty_state,
    render_html,
    render_metrics_grid,
    render_recent_events_table,
    render_skeleton_block,
    render_trend_chart_panel,
    render_workers_grid,
    render_zone_occupancy_panel,
)
from src.video.renderer import enhance_visual_clarity, render_8k_clarity_canvas


def render_camera_viewport(ctx: AppContext) -> None:
    """Render real-time annotated camera viewport from background OpenCV worker."""
    camera_manager = ctx.camera_manager
    if camera_manager.is_running:
        frame = camera_manager.get_latest_frame()
        if frame is not None:
            st.image(frame, channels="BGR", use_container_width=True)
            if getattr(camera_manager, "is_simulated", False):
                sim_why = getattr(camera_manager, "sim_reason", "") or "hardware camera not detected"
                st.warning(
                    f"**⚠️ SIMULATED FEED — real webcam is not accessible to server process ({sim_why}).**\n"
                    "Detections are synthetic demo personnel. Switch to '📸 Direct Browser Camera' to use your browser camera."
                )
        else:
            render_skeleton_block("Initializing camera…", "Waiting for first frame from capture worker.")
    else:
        render_skeleton_block("Camera standby", "Click Start Camera to begin real-time monitoring.")

    if camera_manager.last_error:
        st.error(f"⚠️ {camera_manager.last_error}")


def render_webrtc_stream(ctx: AppContext, zone: ZonePolicy, inspector_fn: Callable) -> None:
    """Stream continuous 30 FPS video via browser WebRTC."""
    pipeline = ctx.pipeline
    STATE = ctx.state

    st.caption("Continuous browser video review through WebRTC.")

    def webrtc_video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        try:
            if hasattr(pipeline.renderer, "enhance_visual_clarity"):
                img = pipeline.renderer.enhance_visual_clarity(img, strength=0.25)
            else:
                img = enhance_visual_clarity(img, strength=0.25)
            annotated = pipeline.process_numpy_frame(img)
            return av.VideoFrame.from_ndarray(annotated, format="bgr24")
        except Exception:
            return av.VideoFrame.from_ndarray(img, format="bgr24")

    if HAS_WEBRTC:
        webrtc_streamer(
            key="live_ppe_webrtc_feed",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=RTC_CLOUD_CONFIGURATION,
            video_frame_callback=webrtc_video_frame_callback,
            media_stream_constraints={
                "video": {
                    "width": {"min": 1280, "ideal": 1920, "max": 3840},
                    "height": {"min": 720, "ideal": 1080, "max": 2160},
                    "frameRate": {"ideal": 30, "max": 60},
                },
                "audio": False,
            },
            sendback_audio=False,
            video_html_attrs={
                "autoPlay": True,
                "controls": False,
                "style": {"width": "100%", "borderRadius": "10px"},
                "muted": True,
            },
            async_processing=True,
        )
    else:
        st.warning("WebRTC is unavailable in this environment. Switch to '📸 Direct Browser Camera' above.")

    @st.fragment(run_every=0.5)
    def render_webrtc_telemetry_fragment() -> None:
        data = STATE.snapshot_ui()
        workers = data["workers"]
        total_w = len(workers)
        viol_w = sum(1 for w in workers if w.has_active_violation)
        safe_w = sum(1 for w in workers if w.is_compliant)
        score = None if total_w == 0 else max(0.0, min(100.0, (safe_w / float(total_w)) * 100.0))

        if (
            st.session_state.audio_alarms_enabled
            and hasattr(STATE, "violation_streak")
            and STATE.violation_streak == 1
            and st.session_state.last_violation_streak == 0
        ):
            st.session_state.last_violation_streak = 1
            play_violation_chime()
        elif viol_w == 0:
            st.session_state.last_violation_streak = 0

        alert_border = "3px solid var(--red)" if viol_w > 0 else "1px solid var(--line)"
        render_html(
            f"""
            <div style="background:var(--panel);border:{alert_border};border-radius:7px;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;margin:10px 0 12px;">
                <div>
                    <span class="badge badge-green">LIVE WEBRTC INFERENCE</span>
                    <span style="font-size:11px;margin-left:10px;color:var(--secondary);">
                        <strong>{len(data["detections"])}</strong> detections · <strong>{total_w}</strong> personnel · <strong>{viol_w}</strong> violations
                    </span>
                </div>
                <div style="font-size:11px;font-family:monospace;color:var(--green);">
                    ⚡ {data["fps"]:.1f} FPS │ {data["inference_ms"]:.0f} ms
                </div>
            </div>
            """
        )
        render_metrics_grid(total_workers=total_w, safe_workers=safe_w, violations=viol_w, safety_score=score)
        render_compliance_panel(
            data["counts"], score, total_tracked=total_w, workers=workers, required_ppe=STATE.required_ppe
        )

        if workers:
            st.markdown("#### Tracked Personnel Compliance Profile")
            render_workers_grid(workers)
            for w in workers:
                if st.button(f"🔍 Inspect Worker #{w.worker_id:02d}", key=f"btn_insp_webrtc_{w.worker_id}"):
                    inspector_fn(
                        w.worker_id,
                        {
                            "status": "UNSAFE" if w.has_active_violation else "SAFE",
                            "dwell_seconds": getattr(w, "dwell_seconds", 0),
                            "gear": getattr(w, "gear", {}),
                        },
                        zone,
                    )

            with st.expander("📋 Detailed Personnel Safety & PPE Checklist", expanded=True):
                st.dataframe(build_workers_status_dataframe(workers), use_container_width=True, hide_index=True)

        c_tr, c_zn = st.columns([1.8, 1.2], gap="large")
        with c_tr:
            render_trend_chart_panel(STATE.get_history_df())
        with c_zn:
            render_zone_occupancy_panel(workers, DEFAULT_ZONES)

        render_recent_events_table(STATE.get_events(), max_rows=6)

    render_webrtc_telemetry_fragment()


def render_direct_browser_stream(ctx: AppContext, zone: ZonePolicy, inspector_fn: Callable) -> None:
    """Capture instant high-resolution frame directly via HTML5 getUserMedia."""
    pipeline = ctx.pipeline
    STATE = ctx.state

    st.caption("Take a still capture from your browser for a focused review.")
    cam_snap = st.camera_input(
        "Take Live Photo for Inspection", key="camera_input_live_feed", label_visibility="collapsed"
    )

    c_v, c_p = st.columns([1.8, 1.2], gap="large")
    with c_v:
        if cam_snap is not None:
            raw_bytes = np.frombuffer(cam_snap.getvalue(), np.uint8)
            raw_img = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
            clean_img = None
            if raw_img is not None and raw_img.size > 0:
                clean_img = raw_img.copy()
                _ = pipeline.process_numpy_frame(raw_img.copy(), force_infer=True)

            data = STATE.snapshot_ui()
            viol_count = sum(1 for w in data["workers"] if w.has_active_violation)
            if (
                st.session_state.audio_alarms_enabled
                and hasattr(STATE, "violation_streak")
                and STATE.violation_streak == 1
                and st.session_state.last_violation_streak == 0
            ):
                st.session_state.last_violation_streak = 1
                play_violation_chime()
            elif viol_count == 0:
                st.session_state.last_violation_streak = 0

            if clean_img is not None:
                t_mode = "1080p"
                render_fn = getattr(pipeline.renderer, "render_8k_clarity_canvas", render_8k_clarity_canvas)
                render_kwargs = {
                    "workers": data["workers"],
                    "boxes": pipeline.last_boxes,
                    "labels": pipeline.last_labels,
                    "scores": pipeline.last_scores,
                    "target_mode": t_mode,
                    "enhance_sharpness": True,
                    "show_hud": True,
                    "fps": pipeline.smoothed_fps,
                    "violations_count": viol_count,
                    "inference_ms": data["inference_ms"],
                    "show_labels": st.session_state.overlay_show_labels,
                    "show_conf_pct": st.session_state.overlay_show_conf_pct,
                    "show_corner_brackets": st.session_state.overlay_show_corner_brackets,
                    "show_status_pills": st.session_state.overlay_show_status_pills,
                }
                annotated = render_fn(clean_img, **render_kwargs)
                st.session_state["latest_annotated_frame"] = annotated
                st.caption(f"Visual viewport · rendered in {t_mode} ({annotated.shape[1]}×{annotated.shape[0]})")
                st.image(annotated, channels="BGR", use_container_width=True)

                ok_enc, buf_enc = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])
                if ok_enc:
                    st.download_button(
                        f"Download {t_mode} capture (JPG)",
                        data=buf_enc.tobytes(),
                        file_name=f"captured_{t_mode.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg",
                        mime="image/jpeg",
                        use_container_width=True,
                    )
        else:
            render_empty_state(
                "📸",
                "Take a browser camera photo to review",
                "Viewport updates as soon as photo is taken.",
                "Click Take Photo",
            )

        data = STATE.snapshot_ui()
        render_html(
            f"""
            <div style="background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;margin-top:10px;">
                <div>
                    <span class="badge badge-green">SNAPSHOT INFERENCE</span>
                    <span style="font-size:11px;margin-left:10px;color:var(--secondary);">
                        <strong>{len(data["detections"])}</strong> detections · <strong>{len(data["workers"])}</strong> personnel
                    </span>
                </div>
                <div style="font-size:11px;font-family:monospace;color:var(--green);">
                    ⚡ {data["fps"]:.1f} FPS │ {data["inference_ms"]:.0f} ms
                </div>
            </div>
            """
        )

    data = STATE.snapshot_ui()
    workers = data["workers"]
    total_w = len(workers)
    viol_w = sum(1 for w in workers if w.has_active_violation)
    safe_w = sum(1 for w in workers if w.is_compliant)
    score = None if total_w == 0 else max(0.0, min(100.0, (safe_w / float(total_w)) * 100.0))

    with c_p:
        render_compliance_panel(
            data["counts"], score, total_tracked=total_w, workers=workers, required_ppe=STATE.required_ppe
        )

    render_metrics_grid(total_workers=total_w, safe_workers=safe_w, violations=viol_w, safety_score=score)

    if workers:
        st.markdown("#### Tracked Personnel Compliance Profile")
        render_workers_grid(workers)
        for w in workers:
            if st.button(f"🔍 Inspect Worker #{w.worker_id:02d}", key=f"btn_insp_snap_{w.worker_id}"):
                inspector_fn(
                    w.worker_id,
                    {
                        "status": "UNSAFE" if w.has_active_violation else "SAFE",
                        "dwell_seconds": getattr(w, "dwell_seconds", 0),
                        "gear": getattr(w, "gear", {}),
                    },
                    zone,
                )

        with st.expander("📋 Detailed Personnel Safety Checklist", expanded=True):
            st.dataframe(build_workers_status_dataframe(workers), use_container_width=True, hide_index=True)

    c_tr, c_zn = st.columns([1.8, 1.2], gap="large")
    with c_tr:
        render_trend_chart_panel(STATE.get_history_df())
    with c_zn:
        render_zone_occupancy_panel(workers, DEFAULT_ZONES)

    render_recent_events_table(STATE.get_events(), max_rows=6)

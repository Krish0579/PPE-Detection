"""Live Feed page — real-time shopfloor PPE monitoring across all feed sources.

Periodic refresh uses ``st.fragment(run_every=0.5)`` scoped to the telemetry
subtree only (2 Hz): re-rendering the full page at 20 Hz raced Streamlit's DOM
reconciliation and caused visible flicker/overlap (glitch fix G1).
"""

from __future__ import annotations

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
    RTC_LOCAL_CONFIGURATION = RTCConfiguration({"iceServers": []})
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
    RTC_LOCAL_CONFIGURATION = None
    RTC_CLOUD_CONFIGURATION = None

from src.config.settings import DEFAULT_ZONES
from src.ui.app_context import AppContext
from src.ui.components import (
    build_workers_status_dataframe,
    play_violation_chime,
    render_audio_alert_script,
    render_compliance_panel,
    render_empty_state,
    render_html,
    render_metrics_grid,
    render_page_header,
    render_recent_events_table,
    render_skeleton_block,
    render_trend_chart_panel,
    render_workers_grid,
    render_zone_occupancy_panel,
)
from src.video.pipeline import VideoPipeline
from src.video.renderer import enhance_visual_clarity, render_8k_clarity_canvas


def render_camera_controls_bar(ctx: AppContext, pipeline_ref: VideoPipeline) -> None:
    """Render camera device selector, start/stop buttons, and hardware status."""
    camera_manager = ctx.camera_manager
    is_live = camera_manager.is_running
    is_sim = is_live and bool(getattr(camera_manager, "is_simulated", False))

    if is_sim:
        status_badge = '<span class="badge badge-amber">SIMULATED · DEMO FEED</span>'
    elif is_live:
        status_badge = '<span class="badge badge-green">LIVE · OPENCV STREAMING</span>'
    else:
        status_badge = '<span class="badge badge-slate">STANDBY</span>'
    render_html(
        f"""
        <div class="panel" style="margin-bottom: 12px;">
            <div class="panel-heading">
                <div>
                    <h3>Camera Stream Controls</h3>
                    <p>CAM-{st.session_state.get("opencv_device_idx", 0):02d} · Production Floor Primary</p>
                </div>
                {status_badge}
            </div>
        </div>
        """
    )

    c_btn, c_dev, c_info = st.columns([1.8, 1.4, 2.8])
    with c_btn:
        if is_live:
            if st.button("⏹ Stop Camera", key="btn_stop_cam", use_container_width=True):
                camera_manager.stop()
                st.session_state["cam_stream_active"] = False
                st.rerun()
        else:
            if st.button("▶ Start Camera", key="btn_start_cam", type="primary", use_container_width=True):
                dev_id = st.session_state.get("opencv_device_idx", 0)
                camera_manager.start(device_index=dev_id, pipeline_ref=pipeline_ref)
                st.session_state["cam_stream_active"] = True
                st.rerun()

    with c_dev:
        dev_choice = st.selectbox(
            "Device",
            [0, 1, 2],
            index=st.session_state.get("opencv_device_idx", 0),
            format_func=lambda d: f"CAM-{d:02d}",
            key="sel_opencv_device",
            label_visibility="collapsed",
        )
        if dev_choice != st.session_state.get("opencv_device_idx", 0):
            st.session_state["opencv_device_idx"] = dev_choice
            if is_live:
                camera_manager.start(device_index=dev_choice, pipeline_ref=pipeline_ref)
                st.rerun()

    with c_info:
        if is_live:
            if is_sim:
                st.caption(f"🟡 Simulated demo feed ({camera_manager.fps:.1f} FPS) — real webcam unavailable to server")
            elif camera_manager.fps <= 0:
                st.caption("🟠 Hardware capture warming up — waiting for the first frame…")
            else:
                st.caption(f"🟢 Direct hardware capture ({camera_manager.fps:.1f} FPS)")
        else:
            st.caption("⚡ Click 'Start Camera' for real-time capture")


def render_camera_viewport(ctx: AppContext) -> None:
    """Render real-time annotated camera viewport from background OpenCV worker."""
    camera_manager = ctx.camera_manager
    is_live = camera_manager.is_running
    if is_live:
        frame = camera_manager.get_latest_frame()
        if frame is not None:
            st.image(frame, channels="BGR", use_container_width=True)
            if getattr(camera_manager, "is_simulated", False):
                sim_why = getattr(camera_manager, "sim_reason", "") or "hardware camera not detected by OpenCV"
                st.warning(
                    "**⚠️ SIMULATED FEED — your real webcam is not accessible to the server process.**\n\n"
                    f"Reason: {sim_why}. Everything you see is a synthetic demo shopfloor — the detections are "
                    "simulated personnel, not people in front of your camera.\n\n"
                    "**To enable your real webcam (macOS):**\n"
                    "1. Open **System Settings → Privacy & Security → Camera** and enable the terminal app you "
                    "launched Streamlit from (Terminal / iTerm / VS Code), then restart this app.\n"
                    "2. Or run `tccutil reset Camera` in that terminal and press **▶ Start Camera** again to "
                    "re-trigger the permission prompt.\n\n"
                    "**Works right now:** switch to **'📸 Direct Browser Camera'** or "
                    "**'🌐 Continuous Video Stream (WebRTC · 30 FPS)'** above — your browser already has camera "
                    "permission, so live PPE detection runs on your real webcam."
                )
        else:
            # U2: shimmering skeleton placeholder while the capture worker warms up
            # (theme-aware; replaced the hard-coded flat-color cv2 placeholder).
            render_skeleton_block(
                "Initializing camera…",
                "Waiting for the first annotated frame from the capture worker.",
            )
    else:
        render_skeleton_block(
            "Camera standby",
            "Click Start Camera to begin real-time PPE monitoring.",
        )

    if camera_manager.last_error:
        st.error(f"⚠️ {camera_manager.last_error}")
        st.info(
            "💡 **Recommended**: Switch to **'🌐 Browser Webcam (WebRTC · 30 FPS)'** or **'📸 Camera Snapshot (Instant)'** above to stream directly from your browser webcam without server driver barriers."
        )


def render(ctx: AppContext) -> None:
    """Render the Live Shopfloor Vision Feed page."""
    STATE = ctx.state
    camera_manager = ctx.camera_manager
    pipeline = ctx.pipeline

    # U3: `S` keyboard shortcut arrives as a `cam=toggle` query param —
    # toggle the OpenCV capture worker, clear the param, and rerun.
    if st.query_params.get("cam") == "toggle":
        if camera_manager.is_running:
            camera_manager.stop()
            st.session_state["cam_stream_active"] = False
        else:
            dev_id = st.session_state.get("opencv_device_idx", 0)
            camera_manager.start(device_index=dev_id, pipeline_ref=pipeline)
            st.session_state["cam_stream_active"] = True
        del st.query_params["cam"]
        st.rerun()

    render_page_header(
        title="Live Shopfloor Vision Feed",
        subtitle="Real-time camera feed with continuous multi-person PPE tracking and zone safety monitoring.",
        eyebrow="INDUSTRIAL VISION SYSTEM",
        tag="CAM-01 ACTIVE",
    )

    feed_source = st.radio(
        "Live Feed Source",
        [
            "📸 Direct Browser Camera (Instant & Recommended)",
            "🌐 Continuous Video Stream (WebRTC · 30 FPS)",
            "🔌 Hardware USB Camera (OpenCV)",
        ],
        horizontal=True,
        key="live_feed_src_choice",
    )

    # --- Audio Alarm Toggle & Viewport Customization (Global for all feed sources) ---
    render_audio_alert_script(active=st.session_state.audio_alarms_enabled)

    with st.expander("🔊 Audio Alarm & 👁️ Viewport Overlay Settings", expanded=False):
        col_audio, col_viewport = st.columns([1, 2], gap="large")

        with col_audio:
            st.markdown("#### 🔊 Audio Alarm")
            audio_enabled = st.toggle(
                "Enable Industrial Chime on Violation",
                value=st.session_state.audio_alarms_enabled,
                key="audio_alarm_toggle",
                help="Plays an 880Hz synthesized industrial chime when a new safety violation is detected. Uses Web Audio API - no audio files required.",
            )
            if audio_enabled != st.session_state.audio_alarms_enabled:
                st.session_state.audio_alarms_enabled = audio_enabled
                st.rerun()

            if audio_enabled:
                st.caption("🔈 Chime will play on first violation frame (STATE.violation_streak == 1)")
                if st.button("🔊 Test Chime", key="test_chime_btn"):
                    play_violation_chime()
                    st.toast("🔊 Chime played successfully!")

        with col_viewport:
            st.markdown("#### 👁️ Viewport Overlay Toggles")
            st.caption("Toggle individual overlay elements for minimalist or ultra-detailed view")

            c1, c2 = st.columns(2)
            with c1:
                lbl = st.checkbox(
                    "Show Labels (Worker # · Status)",
                    value=st.session_state.overlay_show_labels,
                    key="overlay_show_labels_chk",
                )
                st.session_state.overlay_show_labels = lbl
                STATE.overlay_show_labels = lbl

                brk = st.checkbox(
                    "Show Corner Brackets",
                    value=st.session_state.overlay_show_corner_brackets,
                    key="overlay_show_brackets_chk",
                )
                st.session_state.overlay_show_corner_brackets = brk
                STATE.overlay_show_corner_brackets = brk

            with c2:
                conf = st.checkbox(
                    "Show Confidence %",
                    value=st.session_state.overlay_show_conf_pct,
                    key="overlay_show_conf_chk",
                )
                st.session_state.overlay_show_conf_pct = conf
                STATE.overlay_show_conf_pct = conf

                pills = st.checkbox(
                    "Show PPE Status Pills",
                    value=st.session_state.overlay_show_status_pills,
                    key="overlay_show_pills_chk",
                )
                st.session_state.overlay_show_status_pills = pills
                STATE.overlay_show_status_pills = pills

    if feed_source == "🌐 Continuous Video Stream (WebRTC · 30 FPS)":
        if camera_manager.is_running:
            camera_manager.stop()
            st.session_state.cam_stream_active = False

        st.caption("Continuous 30 FPS video streaming via browser WebRTC. Click **START** below to begin streaming.")
        st.info(
            "💡 **Camera & Network Notice**:\n"
            "- **Secure Context**: Browsers only permit WebRTC over `http://localhost:8501` or `https://`. If accessing over LAN IP (e.g. `http://192.168.x.x:8501`), browser security blocks `navigator.mediaDevices`.\n"
            "- **Instant Solution**: Switch to **'🔌 Hardware USB Camera (OpenCV)'** above (captures directly on the machine/server without any browser security or driver constraints) or open `http://localhost:8501`."
        )

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
            webrtc_ctx = webrtc_streamer(
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
            webrtc_ctx = None
            st.warning(
                "WebRTC streamer unavailable in this environment. Please switch to '📸 Direct Browser Camera' above."
            )

        _is_webrtc_live = bool(HAS_WEBRTC and webrtc_ctx and getattr(webrtc_ctx.state, "playing", False))

        @st.fragment(run_every=0.5)
        def render_webrtc_telemetry_fragment():
            data = STATE.snapshot_ui()
            workers = data["workers"]
            counts = data["counts"]
            total_w = len(workers)
            viol_w = sum(1 for w in workers if w.has_active_violation)
            safe_w = sum(1 for w in workers if w.is_compliant)
            score = 100.0 if total_w == 0 else max(0.0, min(100.0, (safe_w / float(total_w)) * 100.0))

            # Audio alarm trigger: check violation_streak == 1 (first frame of new violation sequence)
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

            # Visual alert border for active violations
            alert_border = "3px solid var(--red)" if viol_w > 0 else "1px solid var(--line)"

            render_html(
                f"""
                <div style="background: var(--panel); border: {alert_border}; border-radius: 7px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; margin-top: 10px; margin-bottom: 12px;">
                    <div>
                        <span class="badge badge-green">LIVE WEBRTC INFERENCE</span>
                        <span style="font-size: 11px; margin-left: 10px; color: var(--secondary);">
                            <strong>{len(data["detections"])}</strong> detections · <strong>{total_w}</strong> personnel · <strong>{viol_w}</strong> violations
                        </span>
                    </div>
                    <div style="font-size: 11px; font-family: monospace; color: var(--green);">
                        ⚡ {data["fps"]:.1f} FPS │ {data["inference_ms"]:.0f} ms
                    </div>
                </div>
                """
            )

            # Row 1: KPI Metrics
            render_metrics_grid(total_workers=total_w, safe_workers=safe_w, violations=viol_w, safety_score=score)

            # Row 2: Compliance Panel
            render_compliance_panel(
                counts, score, total_tracked=total_w, workers=workers, required_ppe=STATE.required_ppe
            )

            # Row 3: Tracked Personnel Cards
            if workers:
                st.markdown("#### Tracked Personnel Compliance Profile")
                render_workers_grid(workers)
                with st.expander("📋 Detailed Personnel Safety & PPE Checklist (All 5 Categories)", expanded=True):
                    st.dataframe(build_workers_status_dataframe(workers), use_container_width=True, hide_index=True)

            # Row 4: Zone & Trend
            c_tr, c_zn = st.columns([1.8, 1.2], gap="large")
            with c_tr:
                render_trend_chart_panel(STATE.get_history_df())
            with c_zn:
                render_zone_occupancy_panel(workers, DEFAULT_ZONES)

            render_recent_events_table(STATE.get_events(), max_rows=6)

        render_webrtc_telemetry_fragment()

    elif feed_source == "📸 Direct Browser Camera (Instant & Recommended)":
        if camera_manager.is_running:
            camera_manager.stop()
            st.session_state.cam_stream_active = False

        st.caption(
            "Instant camera capture directly from your browser. Click the button below to take a live photo and immediately execute PPE safety inspection."
        )

        cam_snap = st.camera_input(
            "Take Live Photo for Inspection", key="camera_input_live_feed", label_visibility="collapsed"
        )

        c_v, c_p = st.columns([1.8, 1.2], gap="large")
        with c_v:
            if cam_snap is not None:
                raw_bytes = np.frombuffer(cam_snap.getvalue(), np.uint8)
                raw_img = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
                if raw_img is None or raw_img.size == 0:
                    st.error("The camera capture could not be decoded. Please take another photo.")
                    raw_img = None

                clean_img = None
                if raw_img is not None:
                    clean_img = raw_img.copy()
                    _ = pipeline.process_numpy_frame(raw_img.copy(), force_infer=True)
                data = STATE.snapshot_ui()

                # Audio alarm trigger for Direct Browser Camera
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
                        "violations_count": sum(1 for w in data["workers"] if w.has_active_violation),
                        "inference_ms": data["inference_ms"],
                        "show_labels": st.session_state.overlay_show_labels,
                        "show_conf_pct": st.session_state.overlay_show_conf_pct,
                        "show_corner_brackets": st.session_state.overlay_show_corner_brackets,
                        "show_status_pills": st.session_state.overlay_show_status_pills,
                    }
                    try:
                        annotated = render_fn(clean_img, **render_kwargs)
                    except TypeError:
                        import importlib

                        import src.video.renderer as _rmod

                        _rmod = importlib.reload(_rmod)
                        pipeline.renderer = _rmod.OverlayRenderer()
                        annotated = pipeline.renderer.render_8k_clarity_canvas(clean_img, **render_kwargs)
                    st.session_state["latest_annotated_frame"] = annotated

                    # Add to session inspection filmstrip (cap at 5)
                    import time as time_module

                    current_ts = time_module.time()
                    st.session_state.recent_inspections.insert(0, (annotated.copy(), current_ts, data["workers"]))
                    if len(st.session_state.recent_inspections) > 5:
                        st.session_state.recent_inspections.pop()

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
                # U1: themed empty state (replaced the flat-color cv2.putText placeholder
                # that ignored light/dark mode and didn't scale responsively).
                render_empty_state(
                    "📸",
                    "Take a live camera photo above to audit",
                    "The snapshot inference viewport updates as soon as a photo is captured.",
                    "Use the camera control at the top of this page",
                )

            data = STATE.snapshot_ui()
            render_html(
                f"""
                <div style="background: var(--panel); border: 1px solid var(--line); border-radius: 7px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                    <div>
                        <span class="badge badge-green">SNAPSHOT INFERENCE</span>
                        <span style="font-size: 11px; margin-left: 10px; color: var(--secondary);">
                            <strong>{len(data["detections"])}</strong> detections · <strong>{len(data["workers"])}</strong> personnel
                        </span>
                    </div>
                    <div style="font-size: 11px; font-family: monospace; color: var(--green);">
                        ⚡ {data["fps"]:.1f} FPS │ {data["inference_ms"]:.0f} ms
                    </div>
                </div>
                """
            )

        data = STATE.snapshot_ui()
        workers = data["workers"]
        counts = data["counts"]
        total_w = len(workers)
        viol_w = sum(1 for w in workers if w.has_active_violation)
        safe_w = sum(1 for w in workers if w.is_compliant)
        score = 100.0 if total_w == 0 else max(0.0, min(100.0, (safe_w / float(total_w)) * 100.0))

        with c_p:
            render_compliance_panel(
                counts, score, total_tracked=total_w, workers=workers, required_ppe=STATE.required_ppe
            )

        # KPI Metrics
        render_metrics_grid(total_workers=total_w, safe_workers=safe_w, violations=viol_w, safety_score=score)

        # Tracked Personnel Cards
        if workers:
            st.markdown("#### Tracked Personnel Compliance Profile")
            render_workers_grid(workers)
            with st.expander("📋 Detailed Personnel Safety & PPE Checklist (All 5 Categories)", expanded=True):
                st.dataframe(build_workers_status_dataframe(workers), use_container_width=True, hide_index=True)

        # Zone & Trend
        c_tr, c_zn = st.columns([1.8, 1.2], gap="large")
        with c_tr:
            render_trend_chart_panel(STATE.get_history_df())
        with c_zn:
            render_zone_occupancy_panel(workers, DEFAULT_ZONES)

        render_recent_events_table(STATE.get_events(), max_rows=6)

        # --- Session Inspection Filmstrip (Direct Browser Camera) ---
        if st.session_state.recent_inspections:
            st.markdown("#### 📸 Session Inspection Filmstrip")
            st.caption("Last 5 captures — click to review before/after PPE corrections")

            film_cols = st.columns(min(5, len(st.session_state.recent_inspections)))
            for idx, (insp_img, insp_ts, insp_workers) in enumerate(st.session_state.recent_inspections):
                with film_cols[idx]:
                    dt_str = datetime.fromtimestamp(insp_ts).strftime("%H:%M:%S")
                    viol_count = sum(1 for w in insp_workers if w.has_active_violation)
                    badge_text = f"{viol_count} violations" if viol_count > 0 else "Compliant"

                    st.image(insp_img, channels="BGR", use_container_width=True, caption=f"{dt_str} · {badge_text}")

                    if st.button("View", key=f"filmstrip_view_{idx}", use_container_width=True):
                        # Show larger view in a modal-like expander
                        with st.expander(f"Inspection Detail — {dt_str}", expanded=True):
                            st.image(insp_img, channels="BGR", use_container_width=True)
                            if insp_workers:
                                st.dataframe(
                                    build_workers_status_dataframe(insp_workers),
                                    use_container_width=True,
                                    hide_index=True,
                                )

    else:
        # Hardware OpenCV Live Camera
        render_camera_controls_bar(ctx, pipeline)

        is_cam_live = camera_manager.is_running and st.session_state.get("cam_stream_active", False)

        # NOTE: 0.5s refresh (not 0.05s) — re-rendering the full metrics/viewport/
        # charts fragment 20x/sec raced Streamlit's DOM reconciliation and caused
        # visible flicker and overlapping panels. 2 Hz is smooth for telemetry.
        @st.fragment(run_every=0.5 if is_cam_live else None)
        def render_live_monitoring_fragment():
            data = STATE.snapshot_ui()
            detections = data["detections"]
            workers = data["workers"]
            counts = data["counts"]

            total_w = len(workers)
            viol_w = sum(1 for w in workers if getattr(w, "has_active_violation", False))
            safe_w = sum(1 for w in workers if getattr(w, "is_compliant", False))
            score = 100.0 if total_w == 0 else max(0.0, min(100.0, (safe_w / float(total_w)) * 100.0))

            # Audio alarm trigger: check violation_streak == 1 (first frame of new violation sequence)
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

            # Visual alert border for active violations
            alert_border = "3px solid var(--red)" if viol_w > 0 else "1px solid var(--line)"

            # Row 1: KPI Metrics
            render_metrics_grid(total_workers=total_w, safe_workers=safe_w, violations=viol_w, safety_score=score)

            # Row 2: Live Viewport & Compliance Breakdown
            c_cam, c_comp = st.columns([1.8, 1.2], gap="large")

            with c_cam:
                render_camera_viewport(ctx)
                fps_disp = camera_manager.fps if camera_manager.is_running and camera_manager.fps > 0 else data["fps"]
                is_sim_feed = bool(getattr(camera_manager, "is_simulated", False))
                infer_badge = (
                    '<span class="badge badge-amber">SIMULATED INFERENCE</span>'
                    if (camera_manager.is_running and is_sim_feed)
                    else '<span class="badge badge-green">LIVE INFERENCE</span>'
                )
                render_html(
                    f"""
                    <div style="background: var(--panel); border: {alert_border}; border-radius: 7px; padding: 10px 16px; display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                        <div>
                            {infer_badge}
                            <span style="font-size: 11px; margin-left: 10px; color: var(--secondary);">
                                <strong>{len(detections)}</strong> detections · <strong>{total_w}</strong> personnel · <strong>{viol_w}</strong> violations
                            </span>
                        </div>
                        <div style="font-size: 11px; font-family: monospace; color: var(--green);">
                            ⚡ {fps_disp:.1f} FPS │ {data["inference_ms"]:.0f} ms
                        </div>
                    </div>
                    """
                )

            with c_comp:
                render_compliance_panel(
                    counts,
                    score,
                    total_tracked=total_w,
                    workers=workers,
                    required_ppe=STATE.required_ppe,
                    simulated=bool(getattr(camera_manager, "is_simulated", False)),
                )

            # Row 3: Tracked Personnel Cards
            if workers:
                st.markdown("#### Tracked Personnel Compliance Profile")
                render_workers_grid(workers)
                with st.expander("📋 Detailed Personnel Safety & PPE Checklist (All 5 Categories)", expanded=True):
                    st.dataframe(build_workers_status_dataframe(workers), use_container_width=True, hide_index=True)

            # Row 4: Trend Chart & Zone Occupancy
            c_trend, c_zones = st.columns([1.8, 1.2], gap="large")
            with c_trend:
                render_trend_chart_panel(STATE.get_history_df())
            with c_zones:
                render_zone_occupancy_panel(workers, DEFAULT_ZONES)

            # Row 5: Chronological Audit Log
            render_recent_events_table(STATE.get_events(), max_rows=6)

        render_live_monitoring_fragment()

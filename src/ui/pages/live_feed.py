"""Live camera review page for person and required-equipment monitoring.

Coordinates camera inputs, zone policies, source switching, and person review
interactions.
"""

from __future__ import annotations

import streamlit as st

from src.config.settings import DEFAULT_ZONES
from src.ui.app_context import AppContext
from src.ui.components import (
    build_workers_status_dataframe,
    play_violation_chime,
    render_audio_alert_script,
    render_compliance_panel,
    render_html,
    render_metrics_grid,
    render_page_header,
    render_recent_events_table,
    render_section_header,
    render_trend_chart_panel,
    render_workers_grid,
    render_zone_occupancy_panel,
)
from src.ui.pages.live_feed_controls import (
    open_worker_inspector_dialog,
    render_camera_controls_bar,
    render_camera_matrix_bar,
    render_zone_policy_selector,
)
from src.ui.pages.live_feed_runtime import (
    render_camera_viewport,
    render_direct_browser_stream,
    render_webrtc_stream,
)


def render(ctx: AppContext) -> None:
    """Render the live camera review page."""
    STATE = ctx.state
    camera_manager = ctx.camera_manager
    pipeline = ctx.pipeline

    # Global keyboard shortcut `S` (start/stop camera)
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
        title="Live camera review",
        subtitle="Review a camera source, inspect detected people, and keep each decision tied to its zone and evidence.",
        eyebrow="MONITOR",
        tag="LIVE REVIEW",
    )

    render_section_header("Choose a camera source", "Select the input and zone policy before starting review.")
    render_camera_matrix_bar(ctx, pipeline)

    # Zone Compliance Policy Selector
    active_zone = render_zone_policy_selector()

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

    # Audio alarm & overlay settings
    render_audio_alert_script(active=st.session_state.audio_alarms_enabled)
    with st.expander("Audio notification and viewport settings", expanded=False):
        col_audio, col_viewport = st.columns([1, 2], gap="large")
        with col_audio:
            st.markdown("#### Audio notification")
            audio_enabled = st.toggle(
                "Enable notification sound on violation",
                value=st.session_state.audio_alarms_enabled,
                key="audio_alarm_toggle",
            )
            if audio_enabled != st.session_state.audio_alarms_enabled:
                st.session_state.audio_alarms_enabled = audio_enabled
                st.rerun()

            if audio_enabled and st.button("Test notification sound", key="test_chime_btn"):
                play_violation_chime()
                st.toast("Notification sound played")

        with col_viewport:
            st.markdown("#### Viewport overlays")
            c1, c2 = st.columns(2)
            with c1:
                lbl = st.checkbox(
                    "Show Labels", value=st.session_state.overlay_show_labels, key="overlay_show_labels_chk"
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
                    "Show Confidence %", value=st.session_state.overlay_show_conf_pct, key="overlay_show_conf_chk"
                )
                st.session_state.overlay_show_conf_pct = conf
                STATE.overlay_show_conf_pct = conf

                pills = st.checkbox(
                    "Show Status Pills", value=st.session_state.overlay_show_status_pills, key="overlay_show_pills_chk"
                )
                st.session_state.overlay_show_status_pills = pills
                STATE.overlay_show_status_pills = pills

    # Route based on selected feed source
    if feed_source == "🌐 Continuous Video Stream (WebRTC · 30 FPS)":
        if camera_manager.is_running:
            camera_manager.stop()
            st.session_state.cam_stream_active = False
        render_webrtc_stream(ctx, active_zone, open_worker_inspector_dialog)

    elif feed_source == "📸 Direct Browser Camera (Instant & Recommended)":
        if camera_manager.is_running:
            camera_manager.stop()
            st.session_state.cam_stream_active = False
        render_direct_browser_stream(ctx, active_zone, open_worker_inspector_dialog)

    else:
        # Hardware OpenCV Live Camera
        render_camera_controls_bar(ctx, pipeline)
        is_cam_live = camera_manager.is_running and st.session_state.get("cam_stream_active", False)

        @st.fragment(run_every=0.5 if is_cam_live else None)
        def render_live_monitoring_fragment() -> None:
            data = STATE.snapshot_ui()
            detections = data["detections"]
            workers = data["workers"]
            counts = data["counts"]

            total_w = len(workers)
            viol_w = sum(1 for w in workers if getattr(w, "has_active_violation", False))
            safe_w = sum(1 for w in workers if getattr(w, "is_compliant", False))
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
            render_metrics_grid(total_workers=total_w, safe_workers=safe_w, violations=viol_w, safety_score=score)

            c_cam, c_comp = st.columns([1.8, 1.2], gap="large")
            with c_cam:
                render_camera_viewport(ctx)
                fps_disp = camera_manager.fps if camera_manager.is_running and camera_manager.fps > 0 else data["fps"]
                is_sim = bool(getattr(camera_manager, "is_simulated", False))
                infer_badge = (
                    '<span class="badge badge-amber">SIMULATED</span>'
                    if (camera_manager.is_running and is_sim)
                    else '<span class="badge badge-green">CAMERA INFERENCE</span>'
                )
                render_html(
                    f"""
                    <div style="background:var(--panel);border:{alert_border};border-radius:7px;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;margin-top:10px;">
                        <div>
                            {infer_badge}
                            <span style="font-size:11px;margin-left:10px;color:var(--secondary);">
                                <strong>{len(detections)}</strong> detections · <strong>{total_w}</strong> personnel · <strong>{viol_w}</strong> violations
                            </span>
                        </div>
                        <div style="font-size:11px;font-family:monospace;color:var(--green);">
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

            if workers:
                st.markdown("#### Tracked Personnel Compliance Profile")
                render_workers_grid(workers)
                for w in workers:
                    if st.button(f"🔍 Inspect Worker #{w.worker_id:02d}", key=f"btn_insp_hw_{w.worker_id}"):
                        open_worker_inspector_dialog(
                            w.worker_id,
                            {
                                "status": "UNSAFE" if w.has_active_violation else "SAFE",
                                "dwell_seconds": getattr(w, "dwell_seconds", 0),
                                "gear": getattr(w, "gear", {}),
                            },
                            active_zone,
                        )

                with st.expander("📋 Detailed Personnel Safety & PPE Checklist", expanded=True):
                    st.dataframe(build_workers_status_dataframe(workers), use_container_width=True, hide_index=True)

            c_trend, c_zones = st.columns([1.8, 1.2], gap="large")
            with c_trend:
                render_trend_chart_panel(STATE.get_history_df())
            with c_zones:
                render_zone_occupancy_panel(workers, DEFAULT_ZONES)

            render_recent_events_table(STATE.get_events(), max_rows=6)

        render_live_monitoring_fragment()

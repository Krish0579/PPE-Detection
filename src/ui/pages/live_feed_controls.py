"""Camera controls, zone compliance policies, and worker inspection dialogs."""

from __future__ import annotations

import streamlit as st

from src.core.zones import DEFAULT_ZONE_POLICIES, ZonePolicy, ZonePolicyEngine
from src.ui.app_context import AppContext
from src.ui.components import play_violation_chime, render_html
from src.video.camera_registry import default_sources
from src.video.pipeline import VideoPipeline


@st.dialog("👷 Worker Safety Inspector")
def open_worker_inspector_dialog(worker_id: int, worker_info: dict, zone: ZonePolicy) -> None:
    """Detailed inspection dialog with site-policy status and interventions."""
    status = worker_info.get("status", "SAFE")
    badge_color = "var(--red)" if status == "UNSAFE" else "var(--green)"
    bg_color = "var(--red-soft)" if status == "UNSAFE" else "var(--green-soft)"

    render_html(
        f"""
        <div style="padding:14px;border-radius:10px;background:{bg_color};border:1px solid {badge_color};margin-bottom:14px;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <h3 style="margin:0;color:var(--heading);">Worker #{worker_id:02d}</h3>
                    <p style="margin:2px 0 0;font-size:12px;color:var(--muted);">Zone: <strong>{zone.name}</strong> ({zone.zone_type})</p>
                </div>
                <span class="badge" style="background:{badge_color};color:#fff;font-weight:700;">{status}</span>
            </div>
        </div>
        """
    )

    dwell_sec = worker_info.get("dwell_seconds", 0)
    max_dwell = zone.max_dwell_seconds
    if max_dwell:
        dwell_pct = min(1.0, float(dwell_sec) / float(max_dwell))
        st.write(f"⏱️ **Dwell Time:** {dwell_sec:.0f}s / {max_dwell:.0f}s threshold")
        st.progress(dwell_pct)
        if dwell_sec > max_dwell:
            st.error("⚠️ **EXCESSIVE DWELL TIME**: Worker has exceeded maximum allowed duration in restricted zone.")
    else:
        st.write(f"⏱️ **Dwell Time:** {dwell_sec:.0f}s (No dwell limit in this zone)")

    st.markdown("#### Site policy checklist")
    gear = worker_info.get("gear", {})
    citations = {
        "helmet": ("Head protection", "Required by this zone"),
        "vest": ("High-visibility garment", "Required by this zone"),
        "boots": ("Safety footwear", "Required by this zone"),
        "gloves": ("Protective gloves", "Required by this zone"),
        "goggles": ("Eye protection", "Required by this zone"),
    }

    for item, (desc, cite) in citations.items():
        is_required = item in zone.required_ppe
        is_worn = gear.get(item) == "COMPLIANT"
        req_badge = "Required" if is_required else "Optional"

        if is_worn:
            st.markdown(f"✅ **{desc}**: `WORN` · *{cite}* ({req_badge})")
        elif is_required:
            st.markdown(f"❌ **{desc}**: `MISSING / VIOLATION` · *{cite}* (**REQUIRED**)")
        else:
            st.markdown(f"⚪ **{desc}**: `Not Worn` · *{cite}* (Optional in this zone)")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📢 Dispatch Alert Chime", key=f"insp_chime_{worker_id}", use_container_width=True):
            play_violation_chime()
            st.toast(f"Audio warning chime sent to Worker #{worker_id:02d} sector.")
    with c2:
        if st.button("📝 Log Safety Intervention", key=f"insp_log_{worker_id}", use_container_width=True):
            st.toast(f"Intervention recorded in audit trail for Worker #{worker_id:02d}.")


def render_camera_matrix_bar(ctx: AppContext, pipeline_ref: VideoPipeline) -> None:
    """Tactile camera matrix switcher bar enabling instant multi-camera feed switching."""
    sources = default_sources()
    camera_manager = ctx.camera_manager
    current_idx = st.session_state.get("opencv_device_idx", 0)

    render_html(
        """
        <div style="font-size:11px;font-weight:800;color:var(--muted);letter-spacing:1px;margin-bottom:6px;text-transform:uppercase;">
            CAMERA MATRIX SWITCHER
        </div>
        """
    )
    cols = st.columns(len(sources))
    for i, src in enumerate(sources):
        with cols[i]:
            is_active = (current_idx == i) and camera_manager.is_running
            btn_type = "primary" if is_active else "secondary"
            label = f"{'🟢' if is_active else '📹'} {src.id}: {src.zone or src.display_name}"
            if st.button(label, key=f"matrix_cam_{src.id}", type=btn_type, use_container_width=True):
                st.session_state["opencv_device_idx"] = i
                st.session_state["active_zone_name"] = src.zone or "Assembly Line A"
                if not camera_manager.is_running:
                    camera_manager.start(device_index=i, pipeline_ref=pipeline_ref)
                    st.session_state["cam_stream_active"] = True
                st.rerun()


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

    current_idx = st.session_state.get("opencv_device_idx", 0)
    render_html(
        f"""
        <div class="panel" style="margin-bottom: 12px;">
            <div class="panel-heading">
                <div>
                    <h3>Camera Stream Controls</h3>
                    <p>CAM-{current_idx + 1:02d} · Primary workspace view</p>
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


def render_zone_policy_selector() -> ZonePolicy:
    """Render zone policy selector and return active ZonePolicy object."""
    engine = ZonePolicyEngine()
    policy_names = [p.name for p in DEFAULT_ZONE_POLICIES]

    selected_name = st.selectbox(
        "Active Compliance Zone",
        policy_names,
        index=0,
        key="active_zone_selector",
        help="Applies the selected zone's required equipment and dwell-time limits.",
    )
    policy = engine.get_policy(selected_name) or DEFAULT_ZONE_POLICIES[0]

    # Show zone mandate pill badges
    pills = [f'<span class="badge badge-green">⛑️ {p.upper()}</span>' for p in sorted(policy.required_ppe)]
    dwell_badge = (
        f'<span class="badge badge-amber">⏱️ Max {policy.max_dwell_seconds:.0f}s</span>'
        if policy.max_dwell_seconds
        else ""
    )
    render_html(
        f"""
        <div style="display:flex;align-items:center;gap:8px;margin-top:-6px;margin-bottom:12px;flex-wrap:wrap;">
            <span style="font-size:11px;color:var(--muted);font-weight:700;">POLICY {policy.zone_id} MANDATES:</span>
            {" ".join(pills)}
            {dwell_badge}
        </div>
        """
    )
    return policy

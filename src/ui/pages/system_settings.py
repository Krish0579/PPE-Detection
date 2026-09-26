"""System Settings page — hardware, model, thresholds, and PPE policy."""
from __future__ import annotations

import streamlit as st

from src.config.settings import (
    ALLOW_EXTERNAL_MODEL_PATH,
    DEFAULT_ZONES,
    MAX_MODEL_UPLOAD_BYTES,
    MODEL_DIR,
    MODEL_UPLOAD_ENABLED,
)
from src.core.validation import (
    UploadValidationError,
    persist_upload_bytes,
    read_uploaded_bytes,
    validate_model_path,
)
from src.ui.app_context import AppContext
from src.ui.components import render_html, render_page_header


def render(ctx: AppContext) -> None:
    """Render the Workspace & Vision Engine Settings page."""
    STATE = ctx.state
    EVIDENCE_MGR = ctx.evidence
    active_model_path = ctx.active_model_path

    render_page_header(
        title="Workspace & Vision Engine Settings",
        subtitle="Configure model weights, hardware compute accelerators, per-class confidence thresholds, and PPE policy.",
        eyebrow="SYSTEM CONFIGURATION",
        tag="ADMIN CONTROLS",
    )

    s_c1, s_c2 = st.columns(2, gap="large")

    with s_c1:
        st.markdown("#### Neural Model Checkpoint")
        st.caption(f"Active model path: `{active_model_path}`")

        model_path_input = st.text_input(
            "Custom Weights Path (.pt)",
            value=st.session_state.custom_model_path,
            help="Local absolute or relative path to trained YOLO .pt weights file.",
        )
        if st.button("Apply Model Weights", type="secondary"):
            try:
                model_path = validate_model_path(
                    model_path_input,
                    MODEL_DIR,
                    allow_external_paths=ALLOW_EXTERNAL_MODEL_PATH,
                )
                st.session_state.custom_model_path = str(model_path)
                st.success("Weights path applied.")
                st.rerun()
            except UploadValidationError as exc:
                st.error(f"Weights path rejected: {exc}")

        if MODEL_UPLOAD_ENABLED:
            uploaded_weights = st.file_uploader("Upload Reviewed .pt Weights", type=["pt"], key="uploader_weights_file")
            if uploaded_weights:
                try:
                    safe_weight_name, weight_bytes = read_uploaded_bytes(
                        uploaded_weights,
                        {".pt"},
                        MAX_MODEL_UPLOAD_BYTES,
                    )
                    stored_model = persist_upload_bytes(
                        safe_weight_name,
                        weight_bytes,
                        MODEL_DIR,
                        "reviewed-model",
                    )
                    st.session_state.custom_model_path = str(stored_model.path)
                    st.success(f"Uploaded and set as active: {stored_model.original_name}")
                    st.rerun()
                except UploadValidationError as exc:
                    st.error(f"Model upload rejected: {exc}")
        else:
            st.info("Browser model upload is disabled in production. Place reviewed checkpoints in `models/` during deployment.")

    with s_c2:
        st.markdown("#### Inference Threshold Calibration")
        conf_val = st.slider(
            "Master Detection Confidence Floor",
            0.01,
            0.95,
            float(STATE.conf),
            0.01,
            help="Base confidence threshold for all detections.",
        )
        iou_val = st.slider(
            "IoU NMS Overlap Floor",
            0.05,
            0.95,
            float(STATE.iou),
            0.05,
            help="Non-maximum suppression overlap threshold.",
        )

        with st.expander("🎛️ Per-Class Confidence Floor Sliders", expanded=False):
            st.caption("Fine-tune sensitivity per protective equipment category:")
            c_conf_helmet = st.slider("Helmet Floor", 0.01, 0.50, float(STATE.class_conf.get("helmet", 0.06)), 0.01)
            c_conf_vest = st.slider("Vest Floor", 0.01, 0.50, float(STATE.class_conf.get("vest", 0.04)), 0.01)
            c_conf_boots = st.slider("Boots Floor", 0.01, 0.50, float(STATE.class_conf.get("boots", 0.04)), 0.01)
            c_conf_gloves = st.slider("Gloves Floor", 0.01, 0.50, float(STATE.class_conf.get("gloves", 0.035)), 0.005)
            c_conf_goggles = st.slider("Goggles Floor", 0.01, 0.50, float(STATE.class_conf.get("goggles", 0.04)), 0.01)

            custom_class_conf = dict(STATE.class_conf)
            custom_class_conf.update({
                "helmet": c_conf_helmet,
                "no-helmet": c_conf_helmet,
                "no_helmet": c_conf_helmet,
                "vest": c_conf_vest,
                "no-vest": c_conf_vest,
                "no_vest": c_conf_vest,
                "boots": c_conf_boots,
                "no-boots": c_conf_boots,
                "no_boots": c_conf_boots,
                "gloves": c_conf_gloves,
                "no-gloves": c_conf_gloves,
                "no_gloves": c_conf_gloves,
                "goggles": c_conf_goggles,
                "no-goggle": c_conf_goggles,
                "no_goggle": c_conf_goggles,
                "no-goggles": c_conf_goggles,
                "no_goggles": c_conf_goggles,
            })

        st.markdown("#### Mandatory PPE Policy Checks")
        st.caption("Select which items are mandatory for personnel safety compliance:")
        st.session_state.setdefault("ppe_helmet", True)
        st.session_state.setdefault("ppe_vest", True)
        st.session_state.setdefault("ppe_boots", True)
        st.session_state.setdefault("ppe_gloves", True)
        st.session_state.setdefault("ppe_goggles", True)

        st.session_state.ppe_helmet = st.checkbox("Safety Helmet (Hardhat)", value=st.session_state.ppe_helmet, key="chk_helmet")
        st.session_state.ppe_vest = st.checkbox("High-Visibility Safety Vest", value=st.session_state.ppe_vest, key="chk_vest")
        st.session_state.ppe_boots = st.checkbox("Steel-Toe Safety Boots", value=st.session_state.ppe_boots, key="chk_boots")
        st.session_state.ppe_gloves = st.checkbox("Protective Gloves", value=st.session_state.ppe_gloves, key="chk_gloves")
        st.session_state.ppe_goggles = st.checkbox("Safety Goggles (Eye Protection)", value=st.session_state.ppe_goggles, key="chk_goggles")

        req_ppe_dict = {
            "helmet": bool(st.session_state.ppe_helmet),
            "vest": bool(st.session_state.ppe_vest),
            "boots": bool(st.session_state.ppe_boots),
            "gloves": bool(st.session_state.ppe_gloves),
            "goggles": bool(st.session_state.ppe_goggles),
        }

        STATE.update_config(
            conf=conf_val,
            iou=iou_val,
            class_conf=custom_class_conf,
            mode_key=getattr(STATE, "mode_key", "balanced"),
            required_ppe=req_ppe_dict,
        )

        st.markdown("#### Shopfloor Physical Zones")
        for z in DEFAULT_ZONES:
            restr_badge = "badge-amber" if z.type == "Restricted" else "badge-green"
            render_html(
                f"""
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: var(--panel); border: 1px solid var(--line); border-radius: 6px; margin-bottom: 6px; font-size: 11px;">
                    <div>
                        <strong>{z.name}</strong> <small style="color: var(--muted); margin-left: 6px;">({z.id})</small>
                    </div>
                    <div>
                        <span class="badge {restr_badge}" style="margin-right: 8px;">{z.type.upper()}</span>
                        <span>Capacity: <strong>{z.capacity}</strong></span>
                    </div>
                </div>
                """
            )

        st.markdown("#### 💾 Evidence Disk Usage & Maintenance")
        st.caption("Monitor storage consumption and prune stale captures to prevent disk fill-up during long shifts")
        
        # Get storage telemetry
        storage_info = EVIDENCE_MGR.get_storage_telemetry()
        
        col_disk1, col_disk2, col_disk3 = st.columns(3)
        with col_disk1:
            st.metric("Files Stored", storage_info["file_count"])
        with col_disk2:
            st.metric("Disk Usage", f"{storage_info['total_size_mb']:.2f} MB")
        with col_disk3:
            st.metric("Oldest Capture", storage_info["oldest_capture"])
        
        # Progress bar showing usage relative to max snapshots
        usage_pct = min(100, (storage_info["file_count"] / max(1, storage_info["max_snapshots_configured"])) * 100)
        st.progress(usage_pct / 100, text=f"Snapshot retention: {storage_info['file_count']} / {storage_info['max_snapshots_configured']} ({usage_pct:.0f}%)")
        
        col_prune1, col_prune2 = st.columns([2, 1])
        with col_prune1:
            prune_hours = st.number_input(
                "Prune captures older than (hours)",
                min_value=1,
                max_value=720,
                value=24,
                step=1,
                key="prune_hours_input",
                help="Snapshots older than this will be permanently deleted"
            )
        with col_prune2:
            if st.button("🧹 Clear Stale Captures", key="btn_prune_stale", width="stretch", type="primary"):
                result = EVIDENCE_MGR.prune_stale_snapshots(older_than_hours=int(prune_hours))
                if result.get("error"):
                    st.error(f"Pruning failed: {result['error']}")
                else:
                    st.success(f"Deleted {result['deleted_count']} stale captures, freed {result['freed_mb']:.2f} MB")
                    st.rerun()

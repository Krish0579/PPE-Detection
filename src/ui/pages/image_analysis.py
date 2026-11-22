"""Image Analysis page — high-resolution static PPE inspection."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from src.config.settings import MAX_IMAGE_UPLOAD_BYTES
from src.core.class_semantics import format_label
from src.core.validation import UploadValidationError, read_uploaded_bytes
from src.ui.app_context import AppContext
from src.ui.components import (
    build_workers_status_dataframe,
    render_compliance_panel,
    render_metrics_grid,
    render_page_header,
    render_perf_chip,
    render_workers_grid,
)
from src.video.renderer import render_8k_clarity_canvas


def render(ctx: AppContext) -> None:
    """Render the High-Resolution Image Inspection page."""
    STATE = ctx.state
    EVIDENCE_MGR = ctx.evidence
    pipeline = ctx.pipeline

    render_page_header(
        title="Image review",
        subtitle="Inspect one image at a time with clear detections, required equipment status, and evidence capture.",
        eyebrow="REVIEW",
        tag="IMAGE",
    )

    source_choice = st.radio(
        "Image Inspection Source",
        ["📁 Upload Image File", "📸 Live Camera Capture"],
        horizontal=True,
        key="img_analysis_source_choice",
    )

    target_img = None
    source_name = "image_inspection"

    if source_choice == "📁 Upload Image File":
        uploaded_image = st.file_uploader(
            "Upload Image File (JPG, PNG, WEBP)",
            type=["jpg", "jpeg", "png", "webp"],
            key="uploader_single_image",
            help="Upload high-definition photographs for detailed PPE compliance verification.",
        )

        if uploaded_image is not None:
            try:
                safe_image_name, image_bytes = read_uploaded_bytes(
                    uploaded_image,
                    {".jpg", ".jpeg", ".png", ".webp"},
                    MAX_IMAGE_UPLOAD_BYTES,
                )
                raw_bytes = np.frombuffer(image_bytes, np.uint8)
                target_img = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
                if target_img is None or target_img.size == 0:
                    st.error("⚠️ Could not decode image. The file format may be corrupted or unsupported.")
                else:
                    source_name = Path(safe_image_name).stem
            except UploadValidationError as exc:
                st.error(f"⚠️ Image upload rejected: {exc}")
            except cv2.error as exc:
                st.error(f"Failed to decode image: {exc}")
        else:
            st.info("Upload a JPG, PNG, or WEBP image to begin a focused review.")

    elif source_choice == "📸 Live Camera Capture":
        st.caption("Take a still capture from your browser to begin a focused review.")
        cam_snap = st.camera_input(
            "Take Live Photo for Inspection",
            key="camera_input_image_analysis",
        )

        if cam_snap is not None:
            if cam_snap.size == 0:
                st.error("⚠️ Captured photo is empty (0 bytes). Please capture again.")
            else:
                try:
                    raw_bytes = np.frombuffer(cam_snap.getvalue(), np.uint8)
                    target_img = cv2.imdecode(raw_bytes, cv2.IMREAD_COLOR)
                    if target_img is None or target_img.size == 0:
                        st.error("⚠️ Could not decode captured camera photo. Please capture again.")
                    else:
                        source_name = f"camera_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                except Exception as e:
                    st.error(f"Failed to read captured camera image: {e}")
        else:
            st.info("Capture a photo above to begin a focused review.")

    if target_img is not None:
        orig_h, orig_w = target_img.shape[:2]

        ctrl_col1, ctrl_col2 = st.columns([1, 1])
        with ctrl_col1:
            view_mode = st.radio(
                "View Mode",
                ["Annotated Overlay", "Side-by-Side Comparison"],
                horizontal=True,
                key="img_view_mode",
            )
        with ctrl_col2:
            inspect_precision = st.selectbox(
                "Inspection Precision Profile",
                [
                    "✨ Max AI Accuracy Boost (960px + TTA + Crop Scan)",
                    "Deep High-Res (960px Standard)",
                    "Fast Inspection (640px)",
                ],
                index=0,
                key="img_inspect_precision",
                help="Max AI Accuracy Boost runs hierarchical person-crop super-resolution and TTA to detect small PPE (goggles, gloves, boots).",
            )

        # Run pipeline inference with force_infer and render onto high-clarity canvas
        target_mode = "1080p"
        image_digest = hashlib.sha256(target_img.tobytes()).hexdigest()
        img_fingerprint = f"{target_img.shape}_{image_digest}_{target_mode}_{inspect_precision}"
        cached_eval = st.session_state.get("_img_analysis_cache")
        if cached_eval and cached_eval.get("fingerprint") == img_fingerprint:
            annotated_img = cached_eval["annotated_img"]
            data = cached_eval["data"]
        else:
            orig_mode = STATE.mode_key
            orig_acc = getattr(STATE, "accuracy_boost", False)
            orig_crop = getattr(STATE, "crop_refine", False)
            if "Max AI Accuracy Boost" in inspect_precision:
                STATE.mode_key = "boosted"
                STATE.accuracy_boost = True
                STATE.crop_refine = True
            elif "960px" in inspect_precision:
                STATE.mode_key = "precision"
                STATE.accuracy_boost = False
                STATE.crop_refine = False
            else:
                STATE.mode_key = "balanced"
                STATE.accuracy_boost = False
                STATE.crop_refine = False
            try:
                _ = pipeline.process_numpy_frame(target_img.copy(), force_infer=True)
                data = STATE.snapshot_ui()
            finally:
                STATE.mode_key = orig_mode
                STATE.accuracy_boost = orig_acc
                STATE.crop_refine = orig_crop

            render_fn = getattr(pipeline.renderer, "render_8k_clarity_canvas", render_8k_clarity_canvas)
            render_kwargs = {
                "workers": data["workers"],
                "boxes": pipeline.last_boxes,
                "labels": pipeline.last_labels,
                "scores": pipeline.last_scores,
                "target_mode": target_mode,
                "enhance_sharpness": True,
                "show_hud": True,
                "fps": pipeline.smoothed_fps,
                "violations_count": sum(1 for w in data["workers"] if w.has_active_violation),
                "inference_ms": data["inference_ms"],
                "show_labels": getattr(STATE, "overlay_show_labels", True),
                "show_conf_pct": getattr(STATE, "overlay_show_conf_pct", True),
                "show_corner_brackets": getattr(STATE, "overlay_show_corner_brackets", True),
                "show_status_pills": getattr(STATE, "overlay_show_status_pills", True),
            }
            try:
                annotated_img = render_fn(target_img, **render_kwargs)
            except TypeError:
                import importlib

                import src.video.renderer as _rmod

                _rmod = importlib.reload(_rmod)
                pipeline.renderer = _rmod.OverlayRenderer()
                annotated_img = pipeline.renderer.render_8k_clarity_canvas(target_img, **render_kwargs)
            st.session_state["_img_analysis_cache"] = {
                "fingerprint": img_fingerprint,
                "annotated_img": annotated_img,
                "data": data,
            }
        st.session_state["latest_annotated_frame"] = annotated_img
        i_workers = data["workers"]
        i_dets = data["detections"]
        i_counts = data["counts"]
        i_tot = len(i_workers)
        i_viol = sum(1 for w in i_workers if w.has_active_violation)
        i_safe = sum(1 for w in i_workers if w.is_compliant)
        i_score = None if i_tot == 0 else max(0.0, min(100.0, (i_safe / float(i_tot)) * 100.0))

        # Viewport Display
        if view_mode == "Side-by-Side Comparison":
            c_orig, c_anno = st.columns(2, gap="medium")
            with c_orig:
                st.caption(f"Original Capture ({orig_w}×{orig_h})")
                st.image(target_img, channels="BGR", use_container_width=True)
            with c_anno:
                st.caption("AI Annotated Inspection")
                st.image(annotated_img, channels="BGR", use_container_width=True)
        else:
            st.image(annotated_img, channels="BGR", use_container_width=True)

        # U7: FPS/latency telemetry chip on the viewport
        render_perf_chip(data["fps"], data["inference_ms"], label="STATIC INSPECTION")

        # KPI Metrics
        render_metrics_grid(total_workers=i_tot, safe_workers=i_safe, violations=i_viol, safety_score=i_score)

        # Detail Inspection Tabs
        tab_workers, tab_objects, tab_compliance = st.tabs(
            [
                "👥 Personnel Profile",
                "🔍 Detected Objects Table",
                "📊 Compliance Breakdown",
            ]
        )

        with tab_workers:
            if i_workers:
                render_workers_grid(i_workers)
                st.markdown("#### Detailed Safety & PPE Category Breakdown")
                st.dataframe(build_workers_status_dataframe(i_workers), use_container_width=True, hide_index=True)
            else:
                st.info("No personnel anchors identified in this photograph.")

        with tab_objects:
            if i_dets:
                df_dets = pd.DataFrame(
                    [
                        {
                            "Class": format_label(d["label"]),
                            "Category": d.get("category", "NEUTRAL"),
                            "Confidence": f"{round(d.get('confidence', 0.0) * 100)}%",
                            "Box (X1, Y1, X2, Y2)": f"({d['x1']}, {d['y1']}, {d['x2']}, {d['y2']})",
                            "Status": "VIOLATION"
                            if d.get("violation")
                            else ("COMPLIANT" if d.get("compliance") else "NEUTRAL"),
                        }
                        for d in i_dets
                    ]
                )
                st.dataframe(df_dets, use_container_width=True, hide_index=True)
            else:
                st.info("No objects detected above the confidence threshold.")

        with tab_compliance:
            render_compliance_panel(
                i_counts, i_score, total_tracked=i_tot, workers=i_workers, required_ppe=STATE.required_ppe
            )

        # Export Actions
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            ok_enc, buf_enc = cv2.imencode(".jpg", annotated_img)
            if ok_enc:
                st.download_button(
                    "⬇️ Download Annotated Inspection (JPG)",
                    data=buf_enc.tobytes(),
                    file_name=f"inspected_{source_name}.jpg",
                    mime="image/jpeg",
                    use_container_width=True,
                )
        with col_exp2:
            if st.button("💾 Save Inspection to Evidence Log", use_container_width=True):
                v_labels = [d["label"] for d in i_dets if d.get("violation", False)]
                for w in i_workers:
                    if w.has_active_violation:
                        for v in w.violations:
                            if v not in v_labels:
                                v_labels.append(v)
                rec = EVIDENCE_MGR.save_snapshot(annotated_img, v_labels or ["image-inspection"])
                if rec:
                    STATE.add_snapshot(rec)
                    st.success("Inspection capture saved to Evidence Archive and SQLite database.")

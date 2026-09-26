"""Video File page — offline recorded-footage PPE audit with frame scrubbing."""
from __future__ import annotations

import hashlib
import os
from html import escape

import cv2
import streamlit as st

from src.config.settings import MAX_VIDEO_UPLOAD_BYTES, UPLOAD_DIR
from src.core.validation import (
    UploadValidationError,
    persist_upload_bytes,
    read_uploaded_bytes,
)
from src.ui.app_context import AppContext
from src.ui.components import (
    build_workers_status_dataframe,
    render_html,
    render_metrics_grid,
    render_page_header,
    render_perf_chip,
    render_workers_grid,
)


def render(ctx: AppContext) -> None:
    """Render the Recorded Video Inspection page."""
    STATE = ctx.state
    EVIDENCE_MGR = ctx.evidence
    pipeline = ctx.pipeline

    render_page_header(
        title="Recorded Video Inspection",
        subtitle="High-throughput video file audit with frame scrubbing, PPE detection, and safety violation logging.",
        eyebrow="OFFLINE AUDIT ENGINE",
        tag="VIDEO ANALYSIS",
    )

    uploaded_video = st.file_uploader(
        "Upload Video File (MP4, MOV, AVI, WEBM)",
        type=["mp4", "mov", "avi", "webm"],
        key="uploader_video_file",
        help="Upload shopfloor surveillance clips for frame-by-frame compliance analysis.",
    )

    if uploaded_video is not None:
        try:
            safe_video_name, video_bytes = read_uploaded_bytes(
                uploaded_video,
                {".mp4", ".mov", ".avi", ".webm"},
                MAX_VIDEO_UPLOAD_BYTES,
            )
            video_hash = hashlib.sha256(video_bytes).hexdigest()
            cache_key = f"_vid_path_{video_hash}"
            vid_path = st.session_state.get(cache_key)
            if vid_path is None or not os.path.isfile(vid_path):
                stored_video = persist_upload_bytes(safe_video_name, video_bytes, UPLOAD_DIR / "videos", "video")
                vid_path = str(stored_video.path)
                st.session_state[cache_key] = vid_path
        except UploadValidationError as exc:
            st.error(f"⚠️ Video upload rejected: {exc}")
            vid_path = None

        if vid_path:

            cap = None
            try:
                cap = cv2.VideoCapture(vid_path)
                if not cap.isOpened():
                    st.error("⚠️ Failed to open video file. The codec may be unsupported or corrupted.")
                else:
                    total_frames = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
                    vid_fps = max(1.0, cap.get(cv2.CAP_PROP_FPS))
                    vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                    if vid_w <= 0 or vid_h <= 0:
                        st.error("⚠️ Corrupted video header: zero dimensions detected. Please verify file integrity.")
                    else:
                        duration_sec = total_frames / vid_fps

                        render_html(
                            f"""
                            <div style="background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px 18px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 12px;">
                                <div>
                                    <strong>{escape(uploaded_video.name)}</strong>
                                    <span style="color: var(--muted); margin-left: 10px;">{vid_w}×{vid_h} · {total_frames} frames · {duration_sec:.1f}s</span>
                                </div>
                                <span class="badge badge-green">READY FOR AUDIT</span>
                            </div>
                            """
                        )

                        col_c1, col_c2, col_c3 = st.columns([2, 5, 2])
                        with col_c1:
                            run_vid_infer = st.toggle("▶ Run AI Detection", value=True, key="toggle_vid_ai")
                        with col_c2:
                            current_idx = st.slider("Timeline Scrubber", 0, max(0, total_frames - 1), 0, key="vid_scrubber_slider")
                        with col_c3:
                            st.caption(f"Frame {current_idx + 1} / {total_frames}")

                        cap.set(cv2.CAP_PROP_POS_FRAMES, current_idx)
                        ret, raw_frame = cap.read()

                        if ret and raw_frame is not None:
                            if run_vid_infer:
                                annotated_frame = pipeline.process_numpy_frame(raw_frame, force_infer=True)
                            else:
                                annotated_frame = raw_frame

                            st.session_state["latest_annotated_frame"] = annotated_frame

                            # Video viewport
                            st.image(annotated_frame, channels="BGR", use_container_width=True)

                            data = STATE.snapshot_ui()
                            # U7: FPS/latency telemetry chip on the viewport
                            render_perf_chip(data["fps"], data["inference_ms"], label="VIDEO AUDIT")
                            v_workers = data["workers"]
                            v_tot = len(v_workers)
                            v_viol = sum(1 for w in v_workers if w.has_active_violation)
                            v_safe = sum(1 for w in v_workers if w.is_compliant)
                            v_score = 100.0 if v_tot == 0 else max(0.0, min(100.0, (v_safe / float(v_tot)) * 100.0))

                            render_metrics_grid(total_workers=v_tot, safe_workers=v_safe, violations=v_viol, safety_score=v_score)

                            if v_workers:
                                st.markdown("#### Frame Personnel & PPE Inspection")
                                render_workers_grid(v_workers)
                                with st.expander("📋 Detailed Personnel Safety & PPE Checklist (All 5 Categories)", expanded=True):
                                    st.dataframe(build_workers_status_dataframe(v_workers), use_container_width=True, hide_index=True)

                            col_save1, col_save2 = st.columns([2, 2])
                            with col_save1:
                                if st.button("💾 Save Frame Snapshot to Evidence Archive", use_container_width=True):
                                    v_labels = [d["label"] for d in data["detections"] if d.get("violation", False)]
                                    for w in v_workers:
                                        if w.has_active_violation:
                                            for v in w.violations:
                                                if v not in v_labels:
                                                    v_labels.append(v)
                                    rec = EVIDENCE_MGR.save_snapshot(annotated_frame, v_labels or ["manual-inspection"])
                                    if rec:
                                        STATE.add_snapshot(rec)
                                        st.success("Frame snapshot archived to Evidence Database.")
                            with col_save2:
                                ok_enc, buf_enc = cv2.imencode(".jpg", annotated_frame)
                                if ok_enc:
                                    st.download_button(
                                        "⬇️ Download Annotated Frame (JPG)",
                                        data=buf_enc.tobytes(),
                                        file_name=f"frame_{current_idx + 1:04d}_{uploaded_video.name}.jpg",
                                        mime="image/jpeg",
                                        use_container_width=True,
                                    )
                        else:
                            st.warning("Could not decode selected frame from video.")
            except Exception as exc:
                st.error(f"Video processing error: {exc}")
            finally:
                if cap is not None:
                    try:
                        cap.release()
                    except Exception:
                        pass
    else:
        st.info("Upload an MP4, MOV, or AVI video clip to scrub through frames and execute automated PPE inspection.")

"""Evidence Log page — SQLite audit trail, snapshot gallery, and exports."""

from __future__ import annotations

import re
from datetime import datetime

import pandas as pd
import streamlit as st

from src.ui.app_context import AppContext
from src.ui.components import (
    consolidate_person_alerts,
    render_alerts_view,
    render_html,
    render_page_header,
    render_printable_safety_certificate,
    render_reports_view,
    render_section_header,
)


def render(ctx: AppContext) -> None:
    """Render the Evidence Archive & Incident Log page."""
    STATE = ctx.state
    EVIDENCE_MGR = ctx.evidence
    model_name = ctx.model_name

    render_page_header(
        title="Evidence and incident review",
        subtitle="Review captured events, resolve incidents, verify file integrity, and export a traceable record.",
        eyebrow="REVIEW",
        tag="EVIDENCE",
    )

    events = STATE.get_events()
    workers = STATE.snapshot_ui().get("workers", [])
    person_incidents = consolidate_person_alerts(events, workers=workers)

    resolved_set = st.session_state.get("resolved_person_alerts", set())
    acked_set = st.session_state.get("acknowledged_person_alerts", set())

    total_persons = len(person_incidents) if person_incidents else (len(workers) if workers else 0)
    violating_persons = sum(1 for p in person_incidents if p["person_name"] not in resolved_set)
    resolved_count = sum(1 for p in person_incidents if p["person_name"] in resolved_set)

    all_missing = [m for p in person_incidents for m in p["missing_ppe"]]
    if all_missing:
        from collections import Counter

        top_missing = Counter(all_missing).most_common(1)[0][0]
    else:
        top_missing = "None (Fully Compliant)"

    render_section_header("Incident overview", "A quick count of open, resolved, and recurring evidence.")

    # Row 1: KPI Metrics
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_html(
            f"""
            <div class="panel" style="padding: 14px 18px; margin-bottom: 12px;">
                <div style="font-size: 9.5px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px;">TOTAL PERSONNEL</div>
                <div style="font-size: 24px; font-weight: 800; color: var(--heading); line-height: 32px;">{total_persons}</div>
                <div style="font-size: 10px; color: var(--blue);">Monitored workers</div>
            </div>
            """
        )
    with k2:
        render_html(
            f"""
            <div class="panel" style="padding: 14px 18px; margin-bottom: 12px;">
                <div style="font-size: 9.5px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px;">ACTIVE VIOLATIONS</div>
                <div style="font-size: 24px; font-weight: 800; color: var(--red); line-height: 32px;">{violating_persons}</div>
                <div style="font-size: 10px; color: var(--red);">Action required</div>
            </div>
            """
        )
    with k3:
        render_html(
            f"""
            <div class="panel" style="padding: 14px 18px; margin-bottom: 12px;">
                <div style="font-size: 9.5px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px;">RESOLVED INCIDENTS</div>
                <div style="font-size: 24px; font-weight: 800; color: var(--green); line-height: 32px;">{resolved_count}</div>
                <div style="font-size: 10px; color: var(--green);">Cleared / Acknowledged</div>
            </div>
            """
        )
    with k4:
        render_html(
            f"""
            <div class="panel" style="padding: 14px 18px; margin-bottom: 12px;">
                <div style="font-size: 9.5px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px;">PRIMARY VIOLATION</div>
                <div style="font-size: 15px; font-weight: 800; color: var(--amber); line-height: 32px;">{top_missing}</div>
                <div style="font-size: 10px; color: var(--muted);">Highest frequency check</div>
            </div>
            """
        )

    # Tabbed interface: personnel incidents, snapshot gallery, and exports
    tab_incidents, tab_gallery, tab_export = st.tabs(
        [
            "⚠️ Incident Management",
            "📸 Snapshot Archive",
            "📦 Review exports",
        ]
    )

    with tab_incidents:

        def handle_incident_action(person_name: str, new_status: str):
            m = re.search(r"\d+", person_name)
            w_id = int(m.group(0)) if m else None
            recent_events = EVIDENCE_MGR.query_events(limit=100)
            for ev in recent_events:
                if (w_id is not None and ev.get("person_id") == w_id) or person_name.lower() in str(
                    ev.get("violation_type", "")
                ).lower():
                    EVIDENCE_MGR.update_event_status(ev["id"], new_status)

        _c_head, c_reset = st.columns([3, 1])
        with c_reset:
            if st.button(
                "🧹 Clear Session Log",
                help="Reset live personnel alert history and re-initialize person tracker",
                key="btn_reset_personnel_log",
                use_container_width=True,
            ):
                if hasattr(STATE, "clear_events"):
                    STATE.clear_events()
                st.session_state["resolved_person_alerts"] = set()
                st.session_state["acknowledged_person_alerts"] = set()
                if hasattr(ctx, "pipeline") and hasattr(ctx.pipeline, "reset_tracker"):
                    ctx.pipeline.reset_tracker()
                st.success("Personnel tracking & session log cleared.")
                st.rerun()

        render_alerts_view(events, on_action=handle_incident_action, workers=workers)

        if person_incidents:
            st.markdown("#### Consolidated Personnel Safety History")
            rows = []
            for p in person_incidents:
                p_name = p["person_name"]
                if p_name in resolved_set:
                    status = "Resolved"
                elif p_name in acked_set:
                    status = "Acknowledged"
                else:
                    status = "Active Violation"

                missing_str = ", ".join(sorted(p["missing_ppe"])) if p["missing_ppe"] else "None (Compliant)"
                compliant_str = ", ".join(sorted(p["compliant_ppe"])) if p["compliant_ppe"] else "None"

                try:
                    first_dt = datetime.fromtimestamp(p["first_seen"]).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    first_dt = "--"
                try:
                    last_dt = datetime.fromtimestamp(p["last_seen"]).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    last_dt = "--"

                dur_sec = max(0, int(p["last_seen"] - p["first_seen"]))
                dur_disp = f"{dur_sec // 60}m {dur_sec % 60}s" if dur_sec > 60 else f"{dur_sec}s"

                rows.append(
                    {
                        "Personnel": p_name,
                        "Missing Required PPE": missing_str,
                        "Equipped Gear": compliant_str,
                        "First Observed": first_dt,
                        "Last Observed": last_dt,
                        "Duration": dur_disp,
                        "Location": p["zone"],
                        "Status": status,
                    }
                )

            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab_gallery:
        PAGE_SIZE = 8  # captures per "Load more" window

        # B4: DB-backed snapshot index — server-side pagination instead of
        # scanning the whole evidence directory on every rerun. Existing
        # on-disk captures are backfilled into the index automatically.
        snap_days = EVIDENCE_MGR.get_snapshot_days()
        snap_labels = EVIDENCE_MGR.get_snapshot_labels()

        gf_date, gf_label = st.columns(2)
        with gf_date:
            selected_date = st.selectbox(
                "Filter captures by date",
                ["All dates"] + snap_days,
                key="gallery_date_filter",
                help="Narrow the evidence gallery to a single capture day.",
            )
        with gf_label:
            selected_label = st.selectbox(
                "Filter by violation type",
                ["All violation types"] + snap_labels,
                key="gallery_label_filter",
                help="Show only captures tagged with this violation label.",
            )

        # U6 (extended): any filter change resets the visible window
        if st.session_state.get("gallery_filter_prev") != (selected_date, selected_label):
            st.session_state.gallery_filter_prev = (selected_date, selected_label)
            st.session_state.gallery_visible = PAGE_SIZE
        if "gallery_visible" not in st.session_state:
            st.session_state.gallery_visible = PAGE_SIZE

        # U6 (extended): lazy pagination — SQL LIMIT window with a
        # "Load more" control instead of flooding the DOM on large archives.
        day_q = None if selected_date == "All dates" else selected_date
        label_q = None if selected_label == "All violation types" else selected_label
        total = EVIDENCE_MGR.count_snapshots(day=day_q, label=label_q)
        visible_snaps = EVIDENCE_MGR.query_snapshots(limit=st.session_state.gallery_visible, day=day_q, label=label_q)

        if visible_snaps:
            shown = len(visible_snaps)
            st.markdown(f"#### Violation Snapshots Archive ({shown} of {total} captures)")
            st.caption("Click **🔍 Inspect** on any capture to open a full-size detail view with export controls.")

            @st.dialog("Snapshot Detail")
            def _open_snapshot_detail(snap: dict, snap_idx: int) -> None:
                """Lightbox modal (U6): full-size snapshot with metadata, export, and delete."""
                snap_path = EVIDENCE_MGR.storage_dir / snap["filename"]
                try:
                    st.image(str(snap_path), use_container_width=True)
                    f_name = snap["filename"]
                    size_kb = snap.get("size_bytes", 0) / 1024 or snap_path.stat().st_size / 1024
                    labels_str = str(snap.get("labels") or "").replace("-", " ").strip()
                    c_meta1, c_meta2, c_meta3 = st.columns(3)
                    c_meta1.metric("Captured", datetime.fromtimestamp(snap["timestamp"]).strftime("%H:%M:%S"))
                    c_meta2.metric("File", f_name[:18])
                    c_meta3.metric("Size", f"{size_kb:.0f} KB")
                    if labels_str:
                        st.caption(f"🏷️ Violations: {labels_str}")

                    # Cryptographic Chain of Custody Verification (C1)
                    sha256_val = snap.get("sha256")
                    if sha256_val:
                        from src.storage.integrity import verify_snapshot_integrity

                        if verify_snapshot_integrity(snap_path, sha256_val):
                            st.success(f"🔒 Tamper-evident Seal: SHA-256 `{sha256_val[:16]}…` (VERIFIED)")
                        else:
                            st.error("⚠️ Hash Mismatch: Evidence integrity seal broken or file modified!")
                    else:
                        from src.storage.integrity import compute_file_sha256

                        try:
                            calc_hash = compute_file_sha256(snap_path)
                            st.info(f"ℹ️ Snapshot Hash: SHA-256 `{calc_hash[:16]}…`")
                        except Exception:
                            pass

                    with open(snap_path, "rb") as f_obj:
                        st.download_button(
                            "⬇️ Download Full-Size JPEG",
                            data=f_obj.read(),
                            file_name=f_name,
                            mime="image/jpeg",
                            key=f"dl_snap_modal_{snap_idx}_{f_name}",
                            use_container_width=True,
                        )

                    # Evidence management: permanent delete behind an explicit
                    # confirmation checkbox (mirrors the U8 ZIP gate pattern).
                    st.divider()
                    st.markdown("**Danger zone**")
                    del_confirm = st.checkbox(
                        "I understand this permanently removes the capture from disk and the audit index.",
                        key=f"del_confirm_{snap_idx}_{f_name}",
                    )
                    if st.button(
                        "🗑 Delete Capture Permanently",
                        disabled=not del_confirm,
                        key=f"del_snap_{snap_idx}_{f_name}",
                        use_container_width=True,
                    ):
                        if EVIDENCE_MGR.delete_snapshot(f_name):
                            st.toast("Snapshot deleted from evidence archive.")
                            st.rerun()
                        else:
                            st.error("Delete failed — the capture could not be removed.")
                except Exception:
                    st.error("Snapshot could not be loaded from disk.")

            cols = st.columns(4)
            for idx, snap in enumerate(visible_snaps):
                s_path = EVIDENCE_MGR.storage_dir / snap["filename"]
                c = cols[idx % 4]
                with c:
                    try:
                        st.image(str(s_path), use_container_width=True)
                        f_name = snap["filename"]
                        mtime_str = datetime.fromtimestamp(snap["timestamp"]).strftime("%H:%M:%S")
                        snap_labels_str = str(snap.get("labels") or "").replace("-", " ")[:26]
                        st.caption(f"🕒 {mtime_str} · {f_name[:20]}")
                        if snap_labels_str:
                            st.caption(f"🏷️ {snap_labels_str}", help=f_name)
                        if st.button("🔍 Inspect", key=f"inspect_snap_{idx}_{f_name}", use_container_width=True):
                            _open_snapshot_detail(snap, idx)
                    except Exception:
                        pass

            if total > shown:
                c_more, c_hint = st.columns([1, 2])
                with c_more:
                    if st.button("⬇️ Load more captures", key="gallery_load_more", use_container_width=True):
                        st.session_state.gallery_visible += PAGE_SIZE
                        st.rerun()
                with c_hint:
                    st.caption(f"{total - shown} older capture(s) still in the archive.")
        else:
            render_html(
                """
                <div class="panel" style="padding: 30px; text-align: center; color: var(--muted);">
                    <p>No violation snapshots currently stored on disk.</p>
                </div>
                """
            )

        # Incident analytics from the persistent SQLite audit trail
        # (survives app restarts — unlike the in-memory session history).
        with st.expander("📊 Incident Analytics (persistent database)", expanded=False):
            db_events = EVIDENCE_MGR.query_events(limit=1000)
            if db_events:
                ev_df = pd.DataFrame(db_events)
                ev_df["dt"] = ev_df["timestamp"].apply(lambda t: datetime.fromtimestamp(float(t)))
                ev_df["hour"] = ev_df["dt"].dt.hour
                an_day, an_type = st.columns(2)
                with an_day:
                    st.caption("Incidents by hour of day")
                    st.bar_chart(ev_df.groupby("hour").size())
                with an_type:
                    st.caption("Top violation types")
                    top_types = ev_df.groupby("violation_type").size().sort_values(ascending=False).head(8)
                    st.bar_chart(top_types)
                st.caption(f"Based on the {len(ev_df)} most recent audit events (retention-capped).")
            else:
                st.caption("No database events recorded yet — analytics appear after the first monitoring session.")

    with tab_export:
        snap_data = STATE.snapshot_ui()
        render_reports_view(
            evidence_mgr=EVIDENCE_MGR,
            total_frames=snap_data["total_frames"],
            fps=snap_data["fps"],
            model_name=model_name,
            counts=snap_data["counts"],
            detections=snap_data["detections"],
            events=STATE.get_events(),
            workers=workers,
            person_incidents=person_incidents,
        )

        # Also provide ZIP export of snapshots (U8: guarded behind an explicit
        # confirmation so a stray click can't bulk-export the evidence store)
        recent_files = sorted(EVIDENCE_MGR.storage_dir.glob("viol_*.jpg"), reverse=True)[:50]
        if recent_files:
            confirm_zip = st.checkbox(
                f"Confirm bulk archive of {len(recent_files)} stored snapshots",
                key="confirm_zip_export",
                help="Bulk exports include every retained violation capture. This confirmation prevents accidental evidence downloads on shared workstations.",
            )
            if confirm_zip:
                recent_records = [
                    {"datetime": s.name, "ts": s.stat().st_mtime, "jpeg": s.read_bytes()} for s in recent_files
                ]
                zip_bytes = EVIDENCE_MGR.create_zip_archive(recent_records)
                st.download_button(
                    label="📦 Download Complete Incident Archive (ZIP + Manifest)",
                    data=zip_bytes,
                    file_name=f"safesight_evidence_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
            else:
                st.caption("☑️ Tick the confirmation above to unlock the bulk archive download.")

        st.markdown("---")
        st.markdown("#### 📥 Session exports and review reports")

        col_audit, col_print = st.columns(2, gap="medium")

        with col_audit:
            st.markdown("**1-Click Shift Audit (CSV)**")
            st.caption("Traceable breakdown by person, equipment status, and timestamp")

            # Get available sessions
            sessions = EVIDENCE_MGR.query_sessions(limit=10)
            session_options = ["Current Session (All Events)"] + [
                f"Session #{s['id']} — {datetime.fromtimestamp(s['start_time']).strftime('%Y-%m-%d %H:%M')} ({s['total_frames']} frames, {s['total_violations']} violations)"
                for s in sessions
            ]
            selected_session = st.selectbox("Select Session", session_options, index=0, key="audit_session_select")

            session_id = (
                None
                if selected_session == "Current Session (All Events)"
                else int(selected_session.split("#")[1].split(" ")[0])
            )

            csv_content = EVIDENCE_MGR.export_shift_audit_csv(session_id=session_id)
            st.download_button(
                label="📥 Download Shift Audit (.CSV)",
                data=csv_content,
                file_name=f"safesight_shift_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"dl_shift_audit_csv_{session_id}",
            )

        with col_print:
            st.markdown("**Print-Ready Executive Safety Report**")
            st.caption("Formatted review record for window.print()")

            # Prepare data for certificate
            workers_detail = []
            for w in snap_data["workers"]:
                workers_detail.append(
                    {
                        "name": f"Worker #{w.worker_id:02d}",
                        "worker_id": w.worker_id,
                        "zone": w.zone,
                        "helmet": w.helmet_status,
                        "vest": w.vest_status,
                        "gloves": w.gloves_status,
                        "boots": w.boots_status,
                        "goggles": w.goggles_status,
                        "status": "COMPLIANT" if w.is_compliant else "VIOLATION",
                        "is_compliant": w.is_compliant,
                        "missing_ppe": w.violations,
                        "violations": w.violations,
                    }
                )

            cert_data = {
                "session_id": sessions[0]["id"] if sessions else "N/A",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "model_name": model_name,
                "total_frames": snap_data["total_frames"],
                "total_workers": len(snap_data["workers"]),
                "safe_workers": sum(1 for w in snap_data["workers"] if w.is_compliant),
                "violations": sum(1 for w in snap_data["workers"] if w.has_active_violation),
                "safety_score": 100.0
                if len(snap_data["workers"]) == 0
                else max(
                    0.0,
                    min(
                        100.0,
                        (sum(1 for w in snap_data["workers"] if w.is_compliant) / float(len(snap_data["workers"])))
                        * 100.0,
                    ),
                ),
                "workers_detail": workers_detail,
                "events": STATE.get_events()[:50],
            }

            if st.button("🖨️ Print Executive Safety Report", key="print_executive_report", use_container_width=True):
                st.session_state.show_safety_certificate = True
                st.session_state.certificate_data = cert_data

            if st.session_state.get("show_safety_certificate", False):
                cert_data = st.session_state.get("certificate_data", cert_data)
                render_printable_safety_certificate(cert_data)
                if st.button("✕ Close Report", key="close_certificate"):
                    st.session_state.show_safety_certificate = False
                    st.rerun()

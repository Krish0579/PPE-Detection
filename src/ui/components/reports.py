"""Reporting and export surfaces, including the printable safety
certificate rendered from session data."""

from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

from src.storage.evidence import EvidenceManager
from src.ui.components.alerts import consolidate_person_alerts
from src.ui.components.base import render_html


def render_reports_view(
    evidence_mgr: EvidenceManager,
    total_frames: int,
    fps: float,
    model_name: str,
    counts: dict,
    detections: list,
    events: list,
    workers: list | None = None,
    person_incidents: list | None = None,
) -> None:
    """Render downloadable review records and evidence exports."""
    if person_incidents is None:
        person_incidents = consolidate_person_alerts(events, workers=workers)

    embed_photos = st.checkbox(
        "📷 Embed captured violation photo thumbnails in PDF",
        value=True,
        help="Attaches captured evidence snapshots beside non-compliant personnel records",
        key="pdf_embed_photos",
    )

    # Attach available snapshots to non-compliant personnel
    if embed_photos and person_incidents:
        disk_snaps = sorted(
            evidence_mgr.storage_dir.glob("viol_*.jpg"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for idx, p in enumerate(person_incidents):
            if not p.get("snapshot_path") and p.get("missing_ppe") and disk_snaps:
                p["snapshot_path"] = str(disk_snaps[idx % len(disk_snaps)])

    csv_data, _ = evidence_mgr.generate_report_payload(
        total_frames=total_frames,
        fps=fps,
        model_name=model_name,
        counts=counts,
        detections=detections,
        events=events,
    )

    pdf_data = evidence_mgr.generate_pdf_report(
        total_frames=total_frames,
        fps=fps,
        model_name=model_name,
        counts=counts,
        events=events,
        person_incidents=person_incidents,
        include_snapshots=embed_photos,
    )

    c1, c2 = st.columns(2)
    c1.download_button(
        label="⬇️ Download Detections CSV",
        data=csv_data,
        file_name=f"safesight_detections_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
    c2.download_button(
        label="📄 Download Review Report (PDF)",
        data=pdf_data,
        file_name=f"safesight_audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf",
    )

    render_html(
        f"""
        <div class="panel" style="padding: 24px; margin-top: 20px;">
            <h3 style="margin-bottom: 6px;">Review summary</h3>
            <p style="color: var(--muted); font-size: 11px;">Automated decision-support record produced by SAFE SIGHT AI.</p>
            <hr style="border: 0; border-top: 1px solid var(--line); margin: 16px 0;">
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px;">
                <div>
                    <span style="color: var(--muted); font-size: 10px;">GENERATED AT</span>
                    <strong style="display: block; font-size: 13px; margin-top: 4px; color: var(--heading);">{datetime.now().strftime("%Y-%m-%d %H:%M")}</strong>
                </div>
                <div>
                    <span style="color: var(--muted); font-size: 10px;">MODEL CHECKPOINT</span>
                    <strong style="display: block; font-size: 13px; margin-top: 4px; color: var(--heading);">{escape(str(model_name))}</strong>
                </div>
                <div>
                    <span style="color: var(--muted); font-size: 10px;">FRAMES MONITORED</span>
                    <strong style="display: block; font-size: 13px; margin-top: 4px; color: var(--heading);">{total_frames}</strong>
                </div>
                <div>
                    <span style="color: var(--muted); font-size: 10px;">VERDICT</span>
                    <strong style="display: block; font-size: 13px; margin-top: 4px; color: var(--green);">REVIEW RECORD</strong>
                </div>
            </div>
        </div>
        """
    )


def render_printable_safety_certificate(cert_data: dict) -> None:
    """Render a printable review record from session data."""
    score = cert_data.get("safety_score", 0.0)
    status_color = "var(--green)" if score >= 90 else ("var(--amber, #d97706)" if score >= 70 else "var(--red)")
    status_label = "COMPLIANT" if score >= 90 else ("NEEDS ATTENTION" if score >= 70 else "NON-COMPLIANT")

    workers_detail = cert_data.get("workers_detail", [])
    workers_html = ""
    for wd in workers_detail:
        name = wd.get("name") or (f"Worker #{wd.get('worker_id', 0):02d}" if "worker_id" in wd else "Unknown")
        wd_status = wd.get("status") or ("COMPLIANT" if wd.get("is_compliant") else "VIOLATION")
        raw_missing = wd.get("missing_ppe") or wd.get("violations", [])
        missing = ", ".join(raw_missing) if isinstance(raw_missing, (list, tuple)) else str(raw_missing)
        missing = missing or "None"
        tone_color = "var(--green)" if "COMPLIANT" in str(wd_status).upper() else "var(--red)"
        workers_html += f'<tr><td style="padding:7px 10px;border-bottom:1px solid var(--line);font-weight:600;">{escape(str(name))}</td><td style="padding:7px 10px;border-bottom:1px solid var(--line);color:{tone_color};font-weight:700;">{escape(str(wd_status))}</td><td style="padding:7px 10px;border-bottom:1px solid var(--line);">{escape(str(missing))}</td></tr>'

    if not workers_html:
        workers_html = '<tr><td colspan="3" style="padding:10px;text-align:center;color:var(--muted);">No personnel data for this session.</td></tr>'

    render_html(
        f"""
        <div style="background:var(--bg);border:2px solid var(--line);border-radius:12px;padding:28px 32px;margin:16px 0;font-family:system-ui,sans-serif;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <div>
                    <div style="font-size:20px;font-weight:800;color:var(--heading);">SAFE SIGHT AI</div>
                    <div style="font-size:11px;color:var(--muted);margin-top:2px;">Safety review record</div>
                </div>
                <div style="text-align:right;">
                    <div style="font-size:11px;color:var(--muted);">Generated</div>
                    <div style="font-size:12px;font-weight:600;">{cert_data.get("generated_at", "")}</div>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">
                <div style="background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;text-align:center;">
                    <div style="font-size:10px;color:var(--muted);">SAFETY SCORE</div>
                    <div style="font-size:22px;font-weight:800;color:{status_color};">{score:.1f}%</div>
                    <div style="font-size:10px;font-weight:700;color:{status_color};">{status_label}</div>
                </div>
                <div style="background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;text-align:center;">
                    <div style="font-size:10px;color:var(--muted);">PERSONNEL</div>
                    <div style="font-size:22px;font-weight:800;">{cert_data.get("total_workers", 0)}</div>
                </div>
                <div style="background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;text-align:center;">
                    <div style="font-size:10px;color:var(--muted);">VIOLATIONS</div>
                    <div style="font-size:22px;font-weight:800;color:var(--red);">{cert_data.get("violations", 0)}</div>
                </div>
                <div style="background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:12px;text-align:center;">
                    <div style="font-size:10px;color:var(--muted);">FRAMES</div>
                    <div style="font-size:22px;font-weight:800;">{cert_data.get("total_frames", 0)}</div>
                </div>
            </div>
            <div style="margin-bottom:16px;">
                <div style="font-size:12px;font-weight:700;color:var(--heading);margin-bottom:8px;">Personnel Breakdown</div>
                <table style="width:100%;border-collapse:collapse;font-size:12px;">
                    <tr style="background:var(--panel);">
                        <th style="padding:8px 10px;text-align:left;border-bottom:2px solid var(--line);">Worker</th>
                        <th style="padding:8px 10px;text-align:left;border-bottom:2px solid var(--line);">Status</th>
                        <th style="padding:8px 10px;text-align:left;border-bottom:2px solid var(--line);">Missing PPE</th>
                    </tr>
                    {workers_html}
                </table>
            </div>
            <div style="font-size:10px;color:var(--muted);border-top:1px solid var(--line);padding-top:12px;">
                Model: {escape(str(cert_data.get("model_name", "N/A")))} · Session: {escape(str(cert_data.get("session_id", "N/A")))}
            </div>
        </div>
        """
    )

"""Reports & Shift Management page — audit reports, exports, and shift operations."""

from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from src.compliance.mappings import default_registry
from src.config.settings import DB_PATH
from src.core.shifts import ShiftManager
from src.reporting.exporters import to_csv, to_json, to_pdf
from src.reporting.model import build_report
from src.storage.repositories import SQLiteIncidentRepository
from src.ui.app_context import AppContext
from src.ui.components import render_page_header, render_section_header


def render(ctx: AppContext) -> None:
    """Render the Reports, Compliance Exports & Shift Automation page."""
    render_page_header(
        title="Compliance Reports & Shift Digests",
        subtitle="Export certified executive safety reports (PDF/CSV/JSON) and review operational shift schedules.",
        eyebrow="REPORTING",
        tag="AUDIT EXPORT",
    )

    repo = SQLiteIncidentRepository(DB_PATH)
    all_incidents = repo.list_incidents(limit=1000)
    registry = default_registry()
    shift_mgr = ShiftManager()
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    active_shift = shift_mgr.current(now_utc)

    # Shift overview status
    with st.container():
        shift_name = active_shift.shift.name if active_shift else "Off-shift"
        shift_span = f"{active_shift.start:%H:%M} – {active_shift.end:%H:%M}" if active_shift else "Standard Monitoring"
        st.markdown(
            f"""
            <div class="panel" style="padding:14px 18px;margin-bottom:18px;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <span style="font-size:11px;font-weight:700;letter-spacing:1px;color:var(--muted);text-transform:uppercase;">ACTIVE SHIFT SCHEDULE</span>
                    <h3 style="margin:2px 0 0 0 !important;color:var(--heading);">Shift {shift_name} <span style="font-size:14px;color:var(--secondary);font-weight:400;">({shift_span})</span></h3>
                </div>
                <div>
                    <span class="badge badge-green">Monitoring Operational</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    tab_report, tab_shifts = st.tabs(["📑 Generate Audit Report", "🕒 Shift Handover & Schedule"])

    with tab_report:
        render_section_header("Executive safety report generator", "Compile verifiable incident data and regulatory citations.")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            report_title = st.text_input("Report Title", value="Safe Sight AI · Plant Operations Safety Audit")
        with col2:
            period_start = st.text_input("Start Date (ISO)", value="2026-01-01")
        with col3:
            period_end = st.text_input("End Date (ISO)", value="2026-12-31")

        generated_by = st.text_input("Author / Safety Officer", value="Operations Supervisor")

        # Compile report
        report_data = build_report(
            all_incidents,
            title=report_title,
            period_start=period_start,
            period_end=period_end,
            generated_by=generated_by,
            registry=registry,
        )

        st.markdown("#### Report Summary Preview")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Incidents", report_data.totals.get("incidents", 0))
        m2.metric("Unresolved", report_data.totals.get("unresolved", 0))
        m3.metric("Resolved", report_data.totals.get("resolved", 0))
        m4.metric("Total Occurrences", report_data.totals.get("occurrences", 0))

        if report_data.by_violation:
            st.markdown("##### Violations by Category")
            for violation, count in report_data.by_violation.items():
                refs = registry.references_for(violation)
                std_desc = f" ({refs[0].standard} {refs[0].citation})" if refs else ""
                st.write(f"- **{violation.replace('_', ' ').title()}{std_desc}**: {count} incident(s)")

        render_section_header("Download certified reports", "Export verified artifacts with anti-tamper safeguards.")
        d1, d2, d3 = st.columns(3)

        with d1:
            try:
                pdf_bytes = to_pdf(report_data)
                st.download_button(
                    label="📄 Download Executive PDF",
                    data=pdf_bytes,
                    file_name="safesight_safety_audit.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True,
                )
            except Exception as e:
                st.warning(f"PDF generator unavailable: {e}")

        with d2:
            csv_content = to_csv(report_data)
            st.download_button(
                label="📊 Download CSV (Formula-Guarded)",
                data=csv_content,
                file_name="safesight_incidents.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with d3:
            json_content = to_json(report_data)
            st.download_button(
                label="💻 Download Machine JSON",
                data=json_content,
                file_name="safesight_audit.json",
                mime="application/json",
                use_container_width=True,
            )

    with tab_shifts:
        render_section_header("Configured shifts", "Data-driven shift schedule supporting 24/7 industrial operations.")
        for s in shift_mgr.shifts:
            cross_tag = " (Crosses Midnight)" if s.crosses_midnight else ""
            st.markdown(
                f"""
                <div class="panel" style="padding:12px 16px;margin-bottom:8px;">
                    <strong>Shift {s.name}</strong>: <code>{s.start:%H:%M}</code> to <code>{s.end:%H:%M}</code>{cross_tag}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.caption("Shift rotation schedules are driven by configuration and automatically partition compliance metrics across handovers.")

"""Incidents & Compliance page — FSM governance, transitions, and OSHA/EN citations."""

from __future__ import annotations

import streamlit as st

from src.compliance.mappings import default_registry
from src.config.settings import DB_PATH
from src.core.incident_manager import OPEN_STATES, IncidentManager, IncidentState
from src.storage.repositories import SQLiteIncidentRepository
from src.ui.app_context import AppContext
from src.ui.components import render_page_header, render_section_header


def _get_manager() -> tuple[IncidentManager, SQLiteIncidentRepository]:
    repo = SQLiteIncidentRepository(DB_PATH)
    manager = IncidentManager(repo)
    return manager, repo


def render(ctx: AppContext) -> None:
    """Render the Incident Governance & Regulatory Compliance page."""
    render_page_header(
        title="Incident Governance & Compliance",
        subtitle="Manage incident state machines, review regulatory citations, and log verified corrective actions.",
        eyebrow="LIFECYCLE",
        tag="GOVERNANCE",
    )

    manager, repo = _get_manager()
    registry = default_registry()

    tab_active, tab_history, tab_compliance = st.tabs(
        ["⚠️ Active Incidents", "📜 Incident History & Audit", "🏛️ Regulatory Citations"]
    )

    with tab_active:
        render_section_header("Active incidents", "Incidents awaiting operator acknowledgement or safety resolution.")
        active_incidents = repo.list_incidents(states=OPEN_STATES)

        filter_col, search_col = st.columns([1, 2])
        severity_filter = filter_col.selectbox(
            "Severity", ["All severities", "Emergency", "Critical", "Warning", "Notice"],
            key="incident_severity_filter",
        )
        query = search_col.text_input(
            "Search incidents", placeholder="Incident, PPE type, camera, zone, or track ID",
            key="incident_search", help="Search the visible incident queue.",
        ).strip().casefold()
        if severity_filter != "All severities":
            active_incidents = [i for i in active_incidents if i.severity.casefold() == severity_filter.casefold()]
        if query:
            active_incidents = [
                i for i in active_incidents
                if query in " ".join((i.id, i.violation, i.camera_id, i.zone_id, str(i.track_id or ""), i.state)).casefold()
            ]

        if not active_incidents:
            st.info("No incidents match this view." if query or severity_filter != "All severities" else "No active incidents are recorded. Start a monitored source to populate this queue.")
        else:
            for inc in active_incidents:
                citations = registry.references_for(inc.violation)
                cit_text = ", ".join(f"{c.standard} {c.citation}" for c in citations) if citations else "Internal Safety Policy"

                with st.container():
                    st.markdown(
                        f"""
                        <div class="panel" style="padding:14px 18px;margin-bottom:12px;border-left:4px solid var(--{'red' if inc.severity.lower() in ('critical', 'emergency') else 'amber'});">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <strong style="font-size:14px;color:var(--heading);">{inc.id} · {inc.violation.replace('_', ' ').title()}</strong>
                                <span class="badge badge-{'red' if inc.severity.lower() in ('critical', 'emergency') else 'amber'}">{inc.severity}</span>
                            </div>
                            <div style="font-size:12px;color:var(--muted);margin-top:4px;">
                                Camera: <strong>{inc.camera_id}</strong> | Zone: <strong>{inc.zone_id}</strong> | State: <strong>{inc.state}</strong> | Occurrences: <strong>{inc.occurrences}</strong>
                            </div>
                            <div style="font-size:11.5px;color:var(--secondary);margin-top:4px;">
                                Applicable Standard: <em>{cit_text}</em>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    col1, col2, col3, col4 = st.columns([1.2, 1.5, 1.5, 2])
                    if inc.state == IncidentState.DETECTED.value:
                        with col1:
                            if st.button("Acknowledge", key=f"ack_{inc.id}", type="primary"):
                                try:
                                    manager.transition(inc.id, IncidentState.ACKNOWLEDGED, actor="operator", reason="Acknowledged by operator")
                                    st.success(f"{inc.id} acknowledged.")
                                    st.rerun()
                                except Exception as err:
                                    st.error(str(err))

                    with col2:
                        note = st.text_input("Intervention Note", key=f"note_{inc.id}", placeholder="e.g. Worker alerted", label_visibility="collapsed")
                        if st.button("Log Intervention", key=f"int_{inc.id}"):
                            if not note.strip():
                                st.warning("Please provide an intervention note.")
                            else:
                                try:
                                    manager.transition(inc.id, IncidentState.INTERVENTION_LOGGED, actor="safety_officer", reason=note)
                                    st.success("Intervention logged.")
                                    st.rerun()
                                except Exception as err:
                                    st.error(str(err))

                    with col3:
                        res_reason = st.text_input("Resolution Note", key=f"res_note_{inc.id}", placeholder="e.g. PPE equipped", label_visibility="collapsed")
                        if st.button("Resolve Incident", key=f"res_{inc.id}"):
                            if not res_reason.strip():
                                st.warning("Resolution reason required.")
                            else:
                                try:
                                    manager.transition(inc.id, IncidentState.RESOLVED, actor="safety_officer", reason=res_reason)
                                    st.success(f"{inc.id} resolved.")
                                    st.rerun()
                                except Exception as err:
                                    st.error(str(err))

                    with col4:
                        dismiss_reason = st.text_input("False Positive Reason", key=f"fp_note_{inc.id}", placeholder="e.g. Calibration box", label_visibility="collapsed")
                        if st.button("Dismiss / False Positive", key=f"fp_{inc.id}"):
                            if not dismiss_reason.strip():
                                st.warning("Justification required.")
                            else:
                                try:
                                    manager.transition(inc.id, IncidentState.FALSE_POSITIVE, actor="safety_officer", reason=dismiss_reason)
                                    st.info(f"{inc.id} marked as false positive.")
                                    st.rerun()
                                except Exception as err:
                                    st.error(str(err))

    with tab_history:
        render_section_header("Incident history", "Audit log of all resolved, dismissed, or historically tracked events.")
        all_incidents = repo.list_incidents(limit=100)
        history_items = [i for i in all_incidents if i.state not in {s.value for s in OPEN_STATES}]

        if not history_items:
            st.info("No resolved or closed incidents recorded in this session yet.")
        else:
            for inc in history_items:
                with st.expander(f"{inc.id} — {inc.violation} ({inc.state})", expanded=False):
                    st.write(f"**Opened At:** {inc.opened_at} | **Updated:** {inc.updated_at}")
                    st.write(f"**Camera:** {inc.camera_id} | **Zone:** {inc.zone_id} | **Severity:** {inc.severity}")
                    st.markdown("##### Transition Audit Trail")
                    for h in inc.history:
                        st.markdown(f"- **{h.at}** [{h.actor}] transitioned `{h.from_state}` ➔ `{h.to_state}` — *{h.reason or 'No note'}*")

    with tab_compliance:
        render_section_header("Regulatory citation registry", "Authoritative standards mapped to PPE detection categories.")
        categories = ["missing_helmet", "missing_vest", "missing_gloves", "missing_boots", "missing_goggles"]
        for cat in categories:
            refs = registry.references_for(cat)
            st.markdown(f"#### `{cat}` Standards Mapping")
            if not refs:
                st.caption("No external standard citations registered.")
            else:
                for ref in refs:
                    st.markdown(
                        f"""
                        - **{ref.standard} {ref.citation}** ({ref.title}) [{ref.jurisdiction}]:
                          *{ref.notes or 'Mandatory industrial safety requirement'}*
                        """
                    )
        st.caption(f"Citation Registry Version: `{registry.version}` · Strict legal disclaimer: automated alerts are operational decision support and do not constitute formal legal certifications.")

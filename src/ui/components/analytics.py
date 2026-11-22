"""Shift analytics: rolling safety-compliance and worker-productivity panels."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config.settings import DEFAULT_ZONES
from src.core.ppe_associator import WorkerStatus
from src.ui.components.base import render_html
from src.ui.components.workers import render_floor_map


def render_safety_analytics_view(
    history_df: pd.DataFrame,
    violations_count: int,
    events: list[dict] | None = None,
) -> None:
    """Render comprehensive safety analytics view with genuine calculated metrics."""
    c1, c2 = st.columns([1.8, 1.2], gap="large")

    with c1:
        st.markdown("#### Safety Compliance Trends (Past Rolling Window)")
        if not history_df.empty and "Violations" in history_df.columns:
            display_cols = [
                c for c in ["Helmets", "Vests", "Boots", "Gloves", "Goggles", "Violations"] if c in history_df.columns
            ]
            if display_cols:
                st.line_chart(history_df[display_cols], height=320)
            else:
                st.line_chart(history_df, height=320)
        else:
            render_html(
                """
                <div class="panel" style="padding: 30px; text-align: center; color: var(--muted);">
                    <p>Start live video monitoring or upload media to populate real-time trend analytics.</p>
                </div>
                """
            )

    with c2:
        evs = events or []
        cat_counts = {
            "Missing Safety Helmet": 0,
            "Missing Safety Vest": 0,
            "Missing Protective Gloves": 0,
            "Missing Safety Goggles": 0,
            "Missing Steel-Toe Boots": 0,
            "Restricted Zone Breach": 0,
        }
        for e in evs:
            for lab in e.get("labels", []):
                nl = lab.lower()
                if "helmet" in nl:
                    cat_counts["Missing Safety Helmet"] += 1
                elif "vest" in nl:
                    cat_counts["Missing Safety Vest"] += 1
                elif "glove" in nl:
                    cat_counts["Missing Protective Gloves"] += 1
                elif "goggle" in nl or "eye" in nl:
                    cat_counts["Missing Safety Goggles"] += 1
                elif "boot" in nl or "shoe" in nl:
                    cat_counts["Missing Steel-Toe Boots"] += 1
                elif "restricted" in nl or "zone" in nl:
                    cat_counts["Restricted Zone Breach"] += 1

        total_evs = sum(cat_counts.values())

        if total_evs > 0:
            rows_html = []
            idx = 1
            for cat, cnt in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
                if cnt == 0:
                    continue
                pct = round((cnt / float(total_evs)) * 100)
                rows_html.append(
                    f"""
                    <div style="margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; font-size: 11px;">
                            <span>0{idx} · {cat}</span>
                            <strong>{pct}% ({cnt})</strong>
                        </div>
                        <div class="progress-track red"><div style="width: {pct}%;"></div></div>
                    </div>
                    """
                )
                idx += 1
            joined = "".join(rows_html)
            render_html(
                f"""
                <div class="panel">
                    <div class="panel-heading">
                        <div>
                            <h3>Rule Violation Breakdown</h3>
                            <p>Recorded non-compliance events across active session</p>
                        </div>
                        <span class="badge badge-red">{total_evs} INCIDENTS</span>
                    </div>
                    <div class="panel-body">
                        {joined}
                    </div>
                </div>
                """
            )
        else:
            render_html(
                """
                <div class="panel">
                    <div class="panel-heading">
                        <div>
                            <h3>Rule Violation Breakdown</h3>
                            <p>Recorded non-compliance events across active session</p>
                        </div>
                        <span class="badge badge-green">ALL CLEAR</span>
                    </div>
                    <div class="panel-body" style="text-align: center; padding: 35px 20px; color: var(--muted);">
                        <div style="font-size: 28px; margin-bottom: 8px;">🛡️</div>
                        <strong style="color: var(--heading); font-size: 13px;">0 Rule Violations Recorded</strong>
                        <p style="font-size: 10.5px; margin-top: 4px; color: var(--muted);">No PPE non-compliance or restricted zone breaches detected in the active monitoring window.</p>
                    </div>
                </div>
                """
            )


def render_productivity_view(workers: list[WorkerStatus]) -> None:
    """Render activity and dwell time insights with calculated facility metrics.

    Stationary/idle is derived from dwell time rather than hardcoded to zero,
    and average dwell is omitted when no worker has been observed — an idle
    counter that always reads 0 and a duration labelled "Active Shift" are
    numbers the system has not actually measured.
    """
    total_w = len(workers)
    dwell_vals = [w.dwell_seconds for w in workers if w.dwell_seconds > 0]
    stationary = sum(1 for w in workers if getattr(w, "dwell_seconds", 0.0) > 0)

    total_cap = sum(z.capacity for z in DEFAULT_ZONES)
    utilization_pct = min(100, round((total_w / max(1, total_cap)) * 100))

    avg_dwell_str = f"{int(sum(dwell_vals) / len(dwell_vals))}s" if dwell_vals else "Not measured"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Personnel", total_w)
    c2.metric("Stationary / Idle", stationary)
    c3.metric("Avg Dwell Time", avg_dwell_str)
    c4.metric("Facility Utilization", f"{utilization_pct}%")

    st.markdown("#### Workspace zone map")
    render_floor_map(workers, DEFAULT_ZONES)

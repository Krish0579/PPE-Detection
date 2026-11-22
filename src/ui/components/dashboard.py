"""Dashboard panels: KPI metric cards, PPE compliance breakdown, zone
occupancy, compliance trend, and the recent-events audit table."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from src.config.settings import ZoneConfig
from src.core.class_semantics import (
    is_boots,
    is_gloves,
    is_goggles,
    is_helmet,
    is_vest,
    is_violation,
)
from src.core.ppe_associator import WorkerStatus
from src.ui.components.base import render_html


def render_metrics_grid(total_workers: int, safe_workers: int, violations: int, safety_score: float | None) -> None:
    """Render the 4 flagship SAFE SIGHT AI metric cards.

    ``safety_score=None`` means no population has been observed yet. In that
    case the card shows an em dash and says so, because rendering ``0.0%``
    would tell an operator every worker is non-compliant when in fact nobody
    is being observed at all.
    """
    observed = total_workers > 0
    safe_pct = round((safe_workers / max(1, total_workers)) * 100) if observed else None
    viol_class = "red" if violations > 0 else "green"

    if safety_score is None:
        score_value = "&mdash;"
        score_unit = ""
        score_tone = ""
        score_foot = '<span class="metric-change">No observations</span><span>awaiting a monitored view</span>'
    else:
        score_value = f"{safety_score:.1f}"
        score_unit = "<small>%</small>"
        score_tone = ""
        score_foot = (
            '<span class="metric-change green">Transparent index</span><span>compliant ÷ required checks</span>'
        )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        render_html(
            f"""
            <div class="metric-card">
                <div class="metric-top">
                    <span>Total workers</span>
                    <div class="metric-icon blue">👥</div>
                </div>
                <div class="metric-main">
                    <strong>{total_workers}</strong>
                </div>
                <div class="metric-foot">
                    <span class="metric-change {"green" if observed else ""}">{"● Live" if observed else "○ Idle"}</span>
                    <span>in the current view</span>
                </div>
            </div>
            """
        )

    with col2:
        render_html(
            f"""
            <div class="metric-card">
                <div class="metric-top">
                    <span>Safe workers</span>
                    <div class="metric-icon green">🛡️</div>
                </div>
                <div class="metric-main">
                    <strong>{safe_workers}</strong>
                </div>
                <div class="metric-foot">
                    <span class="metric-change {"green" if observed else ""}">{"●" if observed else "○"} {f"{safe_pct}%" if observed else "Not measured"}</span>
                    <span>of observed personnel</span>
                </div>
            </div>
            """
        )

    with col3:
        render_html(
            f"""
            <div class="metric-card">
                <div class="metric-top">
                    <span>Active violations</span>
                    <div class="metric-icon red">⚠️</div>
                </div>
                <div class="metric-main">
                    <strong style="color: {"var(--red)" if violations > 0 else "var(--heading)"};">{violations}</strong>
                </div>
                <div class="metric-foot">
                    <span class="metric-change {viol_class}">● {violations} unhandled</span>
                    <span>needs attention</span>
                </div>
            </div>
            """
        )

    with col4:
        render_html(
            f"""
            <div class="metric-card">
                <div class="metric-top">
                    <span>Safety score</span>
                    <div class="metric-icon green">📊</div>
                </div>
                <div class="metric-main">
                    <strong style="{score_tone}">{score_value}{score_unit}</strong>
                </div>
                <div class="metric-foot">
                    {score_foot}
                </div>
            </div>
            """
        )


def render_compliance_panel(
    counts: dict[str, int],
    safety_score: float | None,
    total_tracked: int = 0,
    workers: list[WorkerStatus] | None = None,
    required_ppe: dict[str, bool] | None = None,
    simulated: bool = False,
    **kwargs: Any,
) -> None:
    """Render PPE compliance breakdown panel with circular SVG donut chart and item progress bars."""
    req = required_ppe or {"helmet": True, "vest": True, "boots": True, "gloves": True, "goggles": True}
    n_workers = len(workers) if workers is not None else total_tracked

    if n_workers > 0:
        if workers:
            h_ok = sum(1 for w in workers if getattr(w, "helmet_status", "") == "COMPLIANT")
            h_viol = sum(1 for w in workers if getattr(w, "helmet_status", "") == "VIOLATION")
            v_ok = sum(1 for w in workers if getattr(w, "vest_status", "") == "COMPLIANT")
            v_viol = sum(1 for w in workers if getattr(w, "vest_status", "") == "VIOLATION")
            b_ok = sum(1 for w in workers if getattr(w, "boots_status", "") == "COMPLIANT")
            b_viol = sum(1 for w in workers if getattr(w, "boots_status", "") == "VIOLATION")
            g_ok = sum(1 for w in workers if getattr(w, "gloves_status", "") == "COMPLIANT")
            g_viol = sum(1 for w in workers if getattr(w, "gloves_status", "") == "VIOLATION")
            e_ok = sum(1 for w in workers if getattr(w, "goggles_status", "") == "COMPLIANT")
            e_viol = sum(1 for w in workers if getattr(w, "goggles_status", "") == "VIOLATION")
        else:
            h_ok = sum(v for k, v in counts.items() if is_helmet(k) and not is_violation(k))
            h_viol = sum(v for k, v in counts.items() if is_helmet(k) and is_violation(k))
            v_ok = sum(v for k, v in counts.items() if is_vest(k) and not is_violation(k))
            v_viol = sum(v for k, v in counts.items() if is_vest(k) and is_violation(k))
            b_ok = sum(v for k, v in counts.items() if is_boots(k) and not is_violation(k))
            b_viol = sum(v for k, v in counts.items() if is_boots(k) and is_violation(k))
            g_ok = sum(v for k, v in counts.items() if is_gloves(k) and not is_violation(k))
            g_viol = sum(v for k, v in counts.items() if is_gloves(k) and is_violation(k))
            e_ok = sum(v for k, v in counts.items() if is_goggles(k) and not is_violation(k))
            e_viol = sum(v for k, v in counts.items() if is_goggles(k) and is_violation(k))

        def calc_item_metric(ok: int, viol: int, is_req: bool) -> tuple[int, str]:
            if not is_req:
                return -1, "Off"
            total = ok + viol
            if total > 0:
                pct = round((ok / float(total)) * 100)
                return pct, f"{pct}%"
            if n_workers > 0:
                return 0, "0%"
            # Nothing observed yet: 0% would read as total non-compliance and
            # 100% as perfect compliance. Neither is known, so reuse the neutral
            # (-1) fill with an explicitly unmeasured label.
            return -1, "Not measured"

        h_pct, h_label = calc_item_metric(h_ok, h_viol, req.get("helmet", True))
        v_pct, v_label = calc_item_metric(v_ok, v_viol, req.get("vest", True))
        b_pct, b_label = calc_item_metric(b_ok, b_viol, req.get("boots", True))
        g_pct, g_label = calc_item_metric(g_ok, g_viol, req.get("gloves", True))
        eye_pct, eye_label = calc_item_metric(e_ok, e_viol, req.get("goggles", True))
    else:
        # No workers in view: render neutral empty bars labelled "Not measured"
        # rather than full bars reading "Ready · 100%", which claimed
        # compliance the system had no evidence for.
        h_pct = v_pct = b_pct = g_pct = eye_pct = -1
        h_label = v_label = b_label = g_label = eye_label = "Not measured"

    circumference = 301.6
    # safety_score is None when no worker has been observed: render an empty
    # ring labelled "not measured" rather than a 0% or 100% compliance score.
    measured = safety_score is not None
    clamped = max(0.0, min(100.0, safety_score)) if measured else 0.0
    dash_length = (clamped / 100.0) * circumference
    stroke_dash = f"{dash_length:.1f} {circumference:.1f}"
    donut_color = "var(--muted)" if not measured else ("var(--green)" if clamped >= 80 else "var(--red)")
    if measured:
        score_display = f'{clamped:.0f}<small style="font-size: 16px; color: {donut_color};">%</small>'
        score_caption = "Overall score"
    else:
        score_display = "&mdash;"
        score_caption = "Not measured"

    items = [
        ("⛑️", "Safety Helmet", h_pct, h_label),
        ("🦺", "Safety Vest", v_pct, v_label),
        ("👢", "Steel-Toe Boots", b_pct, b_label),
        ("🧤", "Protective Gloves", g_pct, g_label),
        ("🥽", "Safety Goggles", eye_pct, eye_label),
    ]

    rows_html = []
    for emoji, title, pct, label in items:
        if pct == -1:
            bar_color = "var(--line)"
            val_color = "var(--muted)"
            bar_pct = 0
        elif pct >= 80:
            bar_color = "var(--green)"
            val_color = "var(--green)"
            bar_pct = pct
        else:
            bar_color = "var(--red)"
            val_color = "var(--red)"
            bar_pct = pct

        rows_html.append(
            f"""
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px; width: 100%;">
                <div style="width: 38px; height: 38px; min-width: 38px; max-width: 38px; border-radius: 8px; background: var(--bg); border: 1px solid var(--line); display: flex; align-items: center; justify-content: center; font-size: 19px; flex-shrink: 0; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
                    {emoji}
                </div>
                <div style="flex: 1 1 auto; min-width: 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                        <span style="font-size: 13.5px; font-weight: 600; color: var(--heading); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{title}</span>
                        <strong style="font-size: 13.5px; font-weight: 700; color: {val_color}; margin-left: 8px; flex-shrink: 0;">{label}</strong>
                    </div>
                    <div style="height: 8px; width: 100%; background: var(--bg); border-radius: 4px; overflow: hidden; border: 1px solid var(--line);">
                        <div style="height: 100%; width: {bar_pct}%; background: {bar_color}; border-radius: 4px; transition: width 0.3s ease;"></div>
                    </div>
                </div>
            </div>
            """
        )

    joined_rows = "".join(rows_html)

    render_html(
        f"""
        <div class="panel" style="width: 100%; box-sizing: border-box; overflow: hidden;">
            <div class="panel-heading">
                <div>
                    <h3>Compliance breakdown</h3>
                    <p>Observed protective equipment</p>
                </div>
                <span class="badge badge-green">LIVE</span>
            </div>
            <div class="panel-body" style="padding: 18px 20px;">
                <div style="width: 124px; height: 124px; position: relative; margin: 0 auto 18px auto; display: flex; align-items: center; justify-content: center;">
                    <svg viewBox="0 0 120 120" style="width: 124px; height: 124px; transform: rotate(-90deg); display: block;">
                        <circle cx="60" cy="60" r="48" fill="none" stroke="var(--line)" stroke-width="10"/>
                        <circle cx="60" cy="60" r="48" fill="none" stroke="{donut_color}" stroke-width="10"
                            stroke-dasharray="{stroke_dash}" stroke-linecap="round"/>
                    </svg>
                    <div style="position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;">
                        <strong style="font-size: 28px; font-weight: 800; color: var(--heading); line-height: 1;">{score_display}</strong>
                        <span style="font-size: 10.5px; color: var(--muted); margin-top: 3px; font-weight: 600;">{score_caption}</span>
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; width: 100%;">
                    {joined_rows}
                </div>
            </div>
        </div>
        """
    )


def render_zone_occupancy_panel(workers: list[WorkerStatus], zones: list[ZoneConfig]) -> None:
    """Render zone occupancy bars matching SAFE SIGHT AI design."""
    rows_html = []
    for z in zones:
        occ = sum(1 for w in workers if w.zone == z.name)
        pct = min(100, round((occ / max(1, z.capacity)) * 100))
        tone = "red" if pct >= 100 or (z.type == "Restricted" and occ > 0) else "green"

        row = f"""
        <div style="margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 11px;">
                <span>
                    <strong style="color: var(--heading);">{z.name}</strong>
                    <small style="color: var(--muted); margin-left: 6px;">({z.type})</small>
                </span>
                <span><strong>{occ}</strong> / {z.capacity} workers</span>
            </div>
            <div class="progress-track {tone}">
                <div style="width: {pct}%;"></div>
            </div>
        </div>
        """
        rows_html.append(row.strip())

    joined_rows = "".join(rows_html)

    render_html(
        f"""
        <div class="panel">
            <div class="panel-heading">
                <div>
                    <h3>Zone occupancy</h3>
                    <p>Monitored physical areas & capacities</p>
                </div>
                <span class="badge badge-slate">{len(zones)} ZONES</span>
            </div>
            <div class="panel-body">
                {joined_rows}
            </div>
        </div>
        """
    )


def render_trend_chart_panel(history_df: pd.DataFrame) -> None:
    """Render rolling safety compliance trend line chart on Dashboard matching Next.js reference."""
    render_html(
        """
        <div class="panel" style="margin-bottom: 0;">
            <div class="panel-heading">
                <div>
                    <h3>Safety compliance trend</h3>
                    <p>Rolling telemetry over active monitoring session</p>
                </div>
                <span class="badge badge-green">LIVE STREAM</span>
            </div>
        </div>
        """
    )
    if not history_df.empty and "Violations" in history_df.columns:
        display_cols = [
            c for c in ["Helmets", "Vests", "Boots", "Gloves", "Goggles", "Violations"] if c in history_df.columns
        ]
        if display_cols:
            st.line_chart(history_df[display_cols], height=240)
        else:
            st.line_chart(history_df, height=240)
    else:
        render_html(
            """
            <div class="panel" style="padding: 26px; text-align: center; color: var(--muted); border-top: 0;">
                <p>Streaming video to generate rolling trend analytics…</p>
            </div>
            """
        )


def render_recent_events_table(events: list[dict], max_rows: int = 6) -> None:
    """Render recent safety events and detections table on Dashboard matching Next.js reference."""
    if not events:
        render_html(
            """
            <div class="panel">
                <div class="panel-heading">
                    <div>
                        <h3>Recent safety events</h3>
                        <p>Recent detections and review events</p>
                    </div>
                    <span class="badge badge-green">ALL CLEAR</span>
                </div>
                <div class="panel-body" style="text-align: center; padding: 25px; color: var(--muted);">
                    <p>No safety violations detected. Operations operating within compliance parameters.</p>
                </div>
            </div>
            """
        )
        return

    rows_html = []
    for e in events[:max_rows]:
        ts = e.get("ts", 0)
        try:
            dt = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        except Exception:
            dt = "--:--:--"
        etype = e.get("type", "EVENT")
        labels = e.get("labels", [])
        labels_str = "; ".join(labels) if labels else "General Inspection"
        severity = "CRITICAL" if etype == "VIOLATION" else ("UPDATE" if etype == "VIOLATION_UPDATE" else "CLEARED")
        tone = "red" if severity == "CRITICAL" else ("amber" if severity == "UPDATE" else "green")

        # Dynamic personnel ID parsing
        worker_id_badge = "#01"
        worker_name = "Personnel"
        if labels:
            for l in labels:
                if "person" in l.lower():
                    p_part = l.split("-")[0].strip()
                    digits = "".join(c for c in p_part if c.isdigit())
                    if digits:
                        worker_id_badge = f"#{int(digits):02d}"
                        worker_name = f"Person {digits}"
                    break

        row = f"""
        <tr>
            <td style="padding: 11px 18px; border-bottom: 1px solid var(--line);">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 26px; height: 26px; border-radius: 50%; background: var(--green-soft); color: var(--green); display: grid; place-items: center; font-weight: 700; font-size: 10px;">
                        {worker_id_badge}
                    </div>
                    <div>
                        <strong style="color: var(--heading); font-size: 11.5px;">{worker_name}</strong>
                        <small style="display: block; color: var(--muted); font-size: 9px;">CAM-01 · Floor Primary</small>
                    </div>
                </div>
            </td>
            <td style="padding: 11px 14px; border-bottom: 1px solid var(--line);">
                <span class="badge badge-{tone}">{severity}</span>
            </td>
            <td style="padding: 11px 14px; border-bottom: 1px solid var(--line); font-weight: 500; color: var(--heading); font-size: 11px;">
                {labels_str}
            </td>
            <td style="padding: 11px 14px; border-bottom: 1px solid var(--line); color: var(--muted); font-family: monospace; font-size: 10.5px;">
                {dt}
            </td>
            <td style="padding: 11px 18px; border-bottom: 1px solid var(--line);">
                <span class="badge badge-slate">CAM-01</span>
            </td>
        </tr>
        """
        rows_html.append(row.strip())

    joined_rows = "".join(rows_html)

    render_html(
        f"""
        <div class="panel">
            <div class="panel-heading">
                <div>
                    <h3>Recent safety events & audit log</h3>
                    <p>Live chronological event stream</p>
                </div>
                <span class="badge badge-slate">{len(events)} EVENTS</span>
            </div>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 11px; text-align: left;">
                    <thead>
                        <tr style="background: var(--bg); border-bottom: 1px solid var(--line); color: var(--muted); font-size: 9px; letter-spacing: 0.5px;">
                            <th style="padding: 10px 18px;">PERSONNEL</th>
                            <th style="padding: 10px 14px;">SEVERITY</th>
                            <th style="padding: 10px 14px;">DETAILS</th>
                            <th style="padding: 10px 14px;">TIMESTAMP</th>
                            <th style="padding: 10px 18px;">LOCATION</th>
                        </tr>
                    </thead>
                    <tbody>
                        {joined_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """
    )

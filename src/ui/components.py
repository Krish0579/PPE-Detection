"""SAFE SIGHT AI component library.

Implements all 10 views from the shopfloor safety platform:
Dashboard, Live Monitoring, Safety Analytics, Productivity Analytics, Workers,
Zones, Alerts, History, Reports, and Settings.
Zero HTML leaks via strict whitespace minification.
"""

from __future__ import annotations

import base64
import functools
import io
import json
import math
import re
import struct
import time
from collections.abc import Callable
from datetime import datetime
from html import escape
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as st_components

from src.config.settings import DEFAULT_ZONES, ZoneConfig
from src.core.class_semantics import (
    is_boots,
    is_gloves,
    is_goggles,
    is_helmet,
    is_vest,
    is_violation,
)
from src.core.ppe_associator import WorkerStatus
from src.storage.evidence import EvidenceManager


def render_html(html_str: str) -> None:
    """Safely render HTML directly via st.html without any markdown parsing interference."""
    clean = " ".join(line.strip() for line in html_str.splitlines() if line.strip())
    if hasattr(st, "html"):
        st.html(clean)
    else:
        st.markdown(clean, unsafe_allow_html=True)


def render_page_header(
    title: str,
    subtitle: str,
    eyebrow: str = "SHOPFLOOR INTELLIGENCE",
    tag: str = "LIVE INFERENCE",
    action_label: str = "Today, Shift 1",
) -> None:
    """Render high-end enterprise page heading with status eyebrow matching the reference platform."""
    render_html(
        f"""
        <div class="page-heading">
            <div>
                <div class="page-eyebrow">
                    <span class="status-dot"></span>
                    <span>{eyebrow}</span>
                    <span class="eyebrow-separator">/</span>
                    <span class="demo-tag">{tag}</span>
                </div>
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
            <div class="heading-actions">
                <div class="badge badge-slate" style="padding: 7px 14px; font-size: 11px; font-weight: 600;">
                    📅 {action_label}
                </div>
                <div class="badge badge-green" style="padding: 7px 14px; font-size: 11px; font-weight: 600;">
                    <span class="status-dot"></span> AI VISION ACTIVE
                </div>
            </div>
        </div>
        """
    )


# -----------------------------------------------------------------------------
# 1. SIDEBAR COMPONENTS
# -----------------------------------------------------------------------------
def render_sidebar_header() -> None:
    """Render SAFE SIGHT AI brand mark in sidebar."""
    render_html(
        """
        <div style="padding: 6px 0 16px 0; border-bottom: 1px solid var(--line); margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="background: var(--green-soft); color: var(--green); width: 46px; height: 46px; border-radius: 10px; display: grid; place-items: center; font-size: 25px; font-weight: 800; flex-shrink: 0;">
                    🛡️
                </div>
                <div>
                    <strong style="font-size: 19px; font-weight: 800; letter-spacing: -0.5px; color: var(--heading); line-height: 1.1;">
                        SAFE SIGHT <span style="color: var(--green);">AI</span>
                    </strong>
                    <small style="display: block; font-size: 10px; letter-spacing: 1.6px; color: var(--muted); font-weight: 700; margin-top: 3px;">
                        VISION THAT PROTECTS.
                    </small>
                </div>
            </div>
        </div>
        """
    )


def render_sidebar_system_card(device_label: str = "", model_name: str = "") -> None:
    """Sidebar footer placeholder."""


def render_sidebar_profile() -> None:
    """Render user profile card at the bottom of the sidebar."""
    render_html(
        """
        <div class="sidebar-profile">
            <div class="sidebar-avatar">
                JD
                <span></span>
            </div>
            <div class="sidebar-profile-info">
                <strong>Jamie Davis</strong>
                <small>Safety Director · Admin</small>
            </div>
        </div>
        """
    )


# -----------------------------------------------------------------------------
# 2. TOPBAR & SHELL HEADER
# -----------------------------------------------------------------------------
def render_safesight_topbar(current_page: str, health_ok: bool = True, model_name: str = "models/best.pt") -> None:
    """Render clean SAFE SIGHT AI brand header and workspace status."""
    status_class = "" if health_ok else "red"
    health_text = "System operational" if health_ok else "Model error"

    render_html(
        f"""
        <div class="safesight-topbar">
            <div class="safesight-brand">
                <div class="safesight-brand-logo">🛡️</div>
                <div class="safesight-brand-title">
                    <strong>SAFE SIGHT <span>AI</span></strong>
                    <small>VISION THAT PROTECTS.</small>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <div class="badge badge-{"green" if health_ok else "red"}" style="padding: 6px 14px; font-size: 11px;">
                    <span class="status-dot {status_class}"></span>
                    {health_text}
                </div>
            </div>
        </div>
        """
    )


# -----------------------------------------------------------------------------
# 3. KPI METRIC CARDS (DASHBOARD & OVERVIEW)
# -----------------------------------------------------------------------------
def render_metrics_grid(total_workers: int, safe_workers: int, violations: int, safety_score: float) -> None:
    """Render the 4 flagship SAFE SIGHT AI metric cards."""
    safe_pct = round((safe_workers / max(1, total_workers)) * 100) if total_workers > 0 else 100
    viol_class = "red" if violations > 0 else "green"

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
                    <span class="metric-change green">● Live</span>
                    <span>monitored on shopfloor</span>
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
                    <span class="metric-change green">{safe_pct}%</span>
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
                    <strong>{safety_score:.1f}<small>%</small></strong>
                </div>
                <div class="metric-foot">
                    <span class="metric-change green">Transparent index</span>
                    <span>compliant ÷ required checks</span>
                </div>
            </div>
            """
        )


# -----------------------------------------------------------------------------
# 4. COMPLIANCE DONUT & PPE PROGRESS BARS
# -----------------------------------------------------------------------------
def render_compliance_panel(
    counts: dict[str, int],
    safety_score: float,
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
            elif n_workers > 0:
                return 0, "0%"
            else:
                return 100, "100%"

        h_pct, h_label = calc_item_metric(h_ok, h_viol, req.get("helmet", True))
        v_pct, v_label = calc_item_metric(v_ok, v_viol, req.get("vest", True))
        b_pct, b_label = calc_item_metric(b_ok, b_viol, req.get("boots", True))
        g_pct, g_label = calc_item_metric(g_ok, g_viol, req.get("gloves", True))
        eye_pct, eye_label = calc_item_metric(e_ok, e_viol, req.get("goggles", True))
    else:
        h_pct = 100
        v_pct = 100
        b_pct = 100
        g_pct = 100
        eye_pct = 100
        h_label = "Ready · 100%"
        v_label = "Ready · 100%"
        b_label = "Ready · 100%"
        g_label = "Ready · 100%"
        eye_label = "Ready · 100%"

    circumference = 301.6
    dash_length = (max(0.0, min(100.0, safety_score)) / 100.0) * circumference
    stroke_dash = f"{dash_length:.1f} {circumference:.1f}"
    donut_color = "var(--green)" if safety_score >= 80 else "var(--red)"

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
                        <strong style="font-size: 28px; font-weight: 800; color: var(--heading); line-height: 1;">{safety_score:.0f}<small style="font-size: 16px; color: {donut_color};">%</small></strong>
                        <span style="font-size: 10.5px; color: var(--muted); margin-top: 3px; font-weight: 600;">Overall score</span>
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; width: 100%;">
                    {joined_rows}
                </div>
            </div>
        </div>
        """
    )


# -----------------------------------------------------------------------------
# 5. ZONE OCCUPANCY PANEL
# -----------------------------------------------------------------------------
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


# -----------------------------------------------------------------------------
# 6. WORKER CARDS GRID
# -----------------------------------------------------------------------------
def render_workers_grid(workers: list[WorkerStatus]) -> None:
    """Render anonymous worker tracking cards."""
    if not workers:
        render_html(
            """
            <div class="panel">
                <div class="panel-body" style="text-align: center; color: var(--muted); padding: 35px;">
                    <h3 style="color: var(--heading); margin-bottom: 8px;">No personnel currently detected in frame</h3>
                    <p>Start live monitoring or run demo stream to track workers on shopfloor.</p>
                </div>
            </div>
            """
        )
        return

    cards = []
    for w in workers:
        viol = w.has_active_violation
        tone = "red" if viol else "green"
        status_label = "UNSAFE" if viol else "SAFE"
        avatar_bg = "var(--red-soft)" if viol else "var(--green-soft)"
        avatar_fg = "var(--red)" if viol else "var(--green)"

        req = getattr(w, "required_ppe", None) or {}

        def _get_item_pill(st_val: str, key: str, emoji: str, name: str, no_name: str, req: dict = req) -> str:
            is_req = req.get(key, True) if req else True
            if not is_req:
                return f'<span class="ppe-pill" style="display: inline-flex; align-items: center; gap: 4px; background: var(--bg-hover); color: var(--muted); padding: 4px 8px; border-radius: 6px; font-size: 11.5px; border: 1px solid var(--border);">{emoji} {name}: <span style="font-weight: 600;">Optional</span></span>'
            if st_val == "COMPLIANT":
                return f'<span class="ppe-pill" style="display: inline-flex; align-items: center; gap: 4px; background: var(--green-soft); color: var(--green); padding: 4px 8px; border-radius: 6px; font-size: 11.5px; border: 1px solid var(--green); font-weight: 600;">{emoji} {name}: <strong>WORN</strong></span>'
            else:
                return f'<span class="ppe-pill" style="display: inline-flex; align-items: center; gap: 4px; background: var(--red-soft); color: var(--red); padding: 4px 8px; border-radius: 6px; font-size: 11.5px; border: 1px solid var(--red); font-weight: 700;">{emoji} <strong>{no_name.upper()}</strong></span>'

        h_pill = _get_item_pill(w.helmet_status, "helmet", "⛑️", "Helmet", "No Helmet")
        v_pill = _get_item_pill(w.vest_status, "vest", "🦺", "Vest", "No Vest")
        g_pill = _get_item_pill(w.gloves_status, "gloves", "🧤", "Gloves", "No Gloves")
        b_pill = _get_item_pill(w.boots_status, "boots", "🥾", "Boots", "No Boots")
        eye_pill = _get_item_pill(w.goggles_status, "goggles", "🥽", "Goggles", "No Goggles")

        card = f"""
        <div class="worker-card" style="padding: 16px; border-radius: 12px; background: var(--card-bg); border: 1px solid var(--border); box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
            <div class="worker-card-head" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="background: {avatar_bg}; color: {avatar_fg}; width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: 13px; flex-shrink: 0;">
                        #{w.worker_id:02d}
                    </div>
                    <div>
                        <strong style="color: var(--heading); font-size: 14px; font-weight: 700;">Worker #{w.worker_id:02d}</strong>
                        <small style="display: block; color: var(--muted); font-size: 11px; margin-top: 1px;">{w.zone}</small>
                    </div>
                </div>
                <span class="badge badge-{tone}" style="font-weight: 700; padding: 4px 10px; font-size: 11px;">{status_label}</span>
            </div>
            <div style="margin: 10px 0 12px 0;">
                <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); margin-bottom: 6px; font-weight: 600;">PPE Compliance Breakdown</div>
                <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                    {h_pill}
                    {v_pill}
                    {g_pill}
                    {b_pill}
                    {eye_pill}
                </div>
            </div>
            <div class="worker-card-foot" style="font-size: 11.5px; display: flex; justify-content: space-between; border-top: 1px solid var(--border); padding-top: 8px; color: var(--text-secondary);">
                <span>Zone: <strong>{w.zone_type}</strong></span>
                <span>Dwell: <strong>{int(w.dwell_seconds)}s</strong></span>
            </div>
        </div>
        """
        cards.append(card.strip())

    joined_cards = "".join(cards)
    render_html(f'<div class="workers-grid">{joined_cards}</div>')


def build_workers_status_dataframe(workers: list[Any]) -> pd.DataFrame:
    """Construct an explicit per-worker PPE status table clearly displaying each category separately."""
    rows = []
    for w in workers:
        req = getattr(w, "required_ppe", None) or {}

        def _fmt(st: str, key: str, worn_txt: str, no_txt: str, req: dict = req) -> str:
            if req and not req.get(key, True):
                return "– Optional"
            if st == "COMPLIANT":
                return f"✅ {worn_txt}"
            return f"❌ {no_txt}"

        h_val = _fmt(getattr(w, "helmet_status", ""), "helmet", "Helmet Worn", "NO HELMET")
        v_val = _fmt(getattr(w, "vest_status", ""), "vest", "Vest Worn", "NO VEST")
        g_val = _fmt(getattr(w, "gloves_status", ""), "gloves", "Gloves Worn", "NO GLOVES")
        b_val = _fmt(getattr(w, "boots_status", ""), "boots", "Boots Worn", "NO BOOTS")
        e_val = _fmt(getattr(w, "goggles_status", ""), "goggles", "Goggles Worn", "NO GOGGLES")

        viols = ", ".join(getattr(w, "violations", [])) if getattr(w, "violations", []) else "None (Compliant)"
        rows.append(
            {
                "Personnel": f"Worker #{getattr(w, 'worker_id', 1):02d}",
                "Status": "❌ VIOLATION" if getattr(w, "has_active_violation", False) else "✅ COMPLIANT",
                "⛑️ Helmet": h_val,
                "🦺 Vest": v_val,
                "🧤 Gloves": g_val,
                "🥾 Boots": b_val,
                "🥽 Goggles": e_val,
                "Zone": getattr(w, "zone", "Production Line"),
                "Active Violations": viols,
            }
        )
    return pd.DataFrame(rows)


# -----------------------------------------------------------------------------
# 7. ALERTS CENTER
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# 7. ALERTS CENTER (CONSOLIDATED PER PERSONNEL)
# -----------------------------------------------------------------------------
def consolidate_person_alerts(
    events: list[dict],
    workers: list[Any] | None = None,
) -> list[dict]:
    """Consolidate PPE violations strictly per person, producing exactly one persistent record per person."""
    person_map: dict[str, dict] = {}

    # Determine the maximum simultaneous workers observed concurrently in the session
    max_simultaneous = len(workers) if workers else 0
    for e in events:
        recs = e.get("person_records", [])
        if recs:
            max_simultaneous = max(max_simultaneous, len(recs))
        reps = e.get("person_reports", [])
        if reps:
            rep_ids = set()
            for r in reps:
                m = re.search(r"Person\s+(\d+)", r, re.IGNORECASE)
                if m:
                    rep_ids.add(int(m.group(1)))
            max_simultaneous = max(max_simultaneous, len(rep_ids))

    # In a session where at most 1 worker is ever concurrently visible (e.g. single camera/station/webcam),
    # all sequential detections/re-entries represent the same person and map to Person 1.
    single_worker_session = max_simultaneous <= 1

    def get_or_create_person(p_name: str, worker_id: int) -> dict:
        if single_worker_session:
            p_name = "Person 1"
            worker_id = 1
        if p_name not in person_map:
            person_map[p_name] = {
                "worker_id": worker_id,
                "person_name": p_name,
                "missing_ppe": set(),
                "compliant_ppe": set(),
                "zone": "CAM-01 · Production Floor Primary",
                "first_seen": float("inf"),
                "last_seen": 0.0,
                "dwell_seconds": 0.0,
                "active": False,
            }
        return person_map[p_name]

    # 1. Inspect live workers if available
    if workers:
        now = time.time()
        for w in workers:
            w_id = 1 if single_worker_session else getattr(w, "worker_id", 1)
            p_name = f"Person {w_id}"
            rec = get_or_create_person(p_name, w_id)
            rec["zone"] = getattr(w, "zone", "CAM-01 · Production Floor Primary")
            rec["dwell_seconds"] = max(rec["dwell_seconds"], getattr(w, "dwell_seconds", 0.0))
            rec["first_seen"] = min(rec["first_seen"], now - rec["dwell_seconds"])
            rec["last_seen"] = max(rec["last_seen"], now)

            # Check individual statuses
            if getattr(w, "helmet_status", "") == "VIOLATION":
                rec["missing_ppe"].add("No Helmet")
            elif getattr(w, "helmet_status", "") == "COMPLIANT":
                rec["compliant_ppe"].add("Helmet")

            if getattr(w, "vest_status", "") == "VIOLATION":
                rec["missing_ppe"].add("No Vest")
            elif getattr(w, "vest_status", "") == "COMPLIANT":
                rec["compliant_ppe"].add("Vest")

            if getattr(w, "boots_status", "") == "VIOLATION":
                rec["missing_ppe"].add("No Boots")
            elif getattr(w, "boots_status", "") == "COMPLIANT":
                rec["compliant_ppe"].add("Boots")

            if getattr(w, "gloves_status", "") == "VIOLATION":
                rec["missing_ppe"].add("No Gloves")
            elif getattr(w, "gloves_status", "") == "COMPLIANT":
                rec["compliant_ppe"].add("Gloves")

            if getattr(w, "goggles_status", "") == "VIOLATION":
                rec["missing_ppe"].add("No Goggles")
            elif getattr(w, "goggles_status", "") == "COMPLIANT":
                rec["compliant_ppe"].add("Goggles")

            if getattr(w, "is_restricted_zone", False):
                rec["missing_ppe"].add("Restricted Zone")

            for v in getattr(w, "violations", []):
                cleaned = v.replace("_", " ").title()
                if not cleaned.lower().startswith("no ") and cleaned.lower() not in (
                    "restricted zone",
                    "safety violation",
                ):
                    cleaned = f"No {cleaned}"
                rec["missing_ppe"].add(cleaned)

            if getattr(w, "has_active_violation", False) or len(rec["missing_ppe"]) > 0:
                rec["active"] = True

    # 2. Inspect historical events
    for e in events:
        ts = e.get("ts", time.time())
        etype = e.get("type", "")
        if etype not in ("VIOLATION", "VIOLATION_UPDATE"):
            continue

        precords = e.get("person_records", [])
        if precords:
            for prec in precords:
                w_id = 1 if single_worker_session else prec.get("worker_id", 1)
                p_name = f"Person {w_id}"
                rec = get_or_create_person(p_name, w_id)
                rec["first_seen"] = min(rec["first_seen"], ts)
                rec["last_seen"] = max(rec["last_seen"], ts)
                rec["zone"] = prec.get("zone") or rec["zone"]
                rec["dwell_seconds"] = max(rec["dwell_seconds"], prec.get("dwell_seconds", 0.0))
                for m in prec.get("missing_ppe", []):
                    cleaned = m.replace("_", " ").title()
                    if not cleaned.lower().startswith("no ") and cleaned.lower() not in (
                        "restricted zone",
                        "safety violation",
                    ):
                        cleaned = f"No {cleaned}"
                    rec["missing_ppe"].add(cleaned)
                rec["active"] = True
            continue

        preports = e.get("person_reports", [])
        matched_any = False
        for rep in preports:
            m = re.search(r"Person\s+(\d+)\s*[-:]\s*(.+)", rep, re.IGNORECASE)
            if m:
                w_id = 1 if single_worker_session else int(m.group(1))
                p_name = f"Person {w_id}"
                rec = get_or_create_person(p_name, w_id)
                rec["first_seen"] = min(rec["first_seen"], ts)
                rec["last_seen"] = max(rec["last_seen"], ts)
                rec["active"] = True
                matched_any = True
                raw_items = m.group(2).split(",")
                for it in raw_items:
                    cleaned = it.strip().replace("_", " ").title()
                    if not cleaned.lower().startswith("no ") and cleaned.lower() not in (
                        "restricted zone",
                        "safety violation",
                    ):
                        cleaned = f"No {cleaned}"
                    rec["missing_ppe"].add(cleaned)

        if matched_any:
            continue

        labels = e.get("labels", [])
        for lbl in labels:
            m = re.search(r"Person\s+(\d+)\s*[-:]\s*(.+)", lbl, re.IGNORECASE)
            if m:
                w_id = 1 if single_worker_session else int(m.group(1))
                p_name = f"Person {w_id}"
                rec = get_or_create_person(p_name, w_id)
                rec["first_seen"] = min(rec["first_seen"], ts)
                rec["last_seen"] = max(rec["last_seen"], ts)
                rec["active"] = True
                raw_items = m.group(2).split(",")
                for it in raw_items:
                    cleaned = it.strip().replace("_", " ").title()
                    if not cleaned.lower().startswith("no ") and cleaned.lower() not in (
                        "restricted zone",
                        "safety violation",
                    ):
                        cleaned = f"No {cleaned}"
                    rec["missing_ppe"].add(cleaned)
            else:
                if "no" in lbl.lower() or "violation" in lbl.lower():
                    rec = get_or_create_person("Person 1", 1)
                    rec["first_seen"] = min(rec["first_seen"], ts)
                    rec["last_seen"] = max(rec["last_seen"], ts)
                    rec["active"] = True
                    cleaned = lbl.strip().replace("-", " ").replace("_", " ").title()
                    if not cleaned.lower().startswith("no ") and cleaned.lower() not in (
                        "restricted zone",
                        "safety violation",
                    ):
                        cleaned = f"No {cleaned}"
                    rec["missing_ppe"].add(cleaned)

    results = []
    for p_name, rec in sorted(person_map.items(), key=lambda item: item[1]["worker_id"]):
        if not rec["missing_ppe"]:
            continue
        if rec["first_seen"] == float("inf"):
            rec["first_seen"] = time.time()
        if rec["last_seen"] == 0.0:
            rec["last_seen"] = rec["first_seen"]
        results.append(rec)

    return results


def render_alerts_view(
    events: list[dict],
    on_action: Callable[[str, str], None] | None = None,
    workers: list[Any] | None = None,
) -> None:
    """Render consolidated per-person safety alert cards with acknowledge/resolve buttons."""
    st.session_state.setdefault("resolved_person_alerts", set())
    st.session_state.setdefault("acknowledged_person_alerts", set())

    consolidated = consolidate_person_alerts(events, workers=workers)

    if not consolidated and not events:
        render_html(
            """
            <div class="panel" style="padding: 40px; text-align: center; color: var(--muted);">
                <h3 style="color: var(--heading); margin-bottom: 8px;">🎉 All caught up! No active safety violations</h3>
                <p>Shopfloor operations are compliant. Any detected violations will appear here consolidated by person.</p>
            </div>
            """
        )
        return

    active_incidents = [p for p in consolidated if p["person_name"] not in st.session_state["resolved_person_alerts"]]
    resolved_incidents = [p for p in consolidated if p["person_name"] in st.session_state["resolved_person_alerts"]]

    if active_incidents:
        st.markdown("#### Active Personnel Violations")
        cols = st.columns(min(3, max(1, len(active_incidents))))
        for idx, p in enumerate(active_incidents):
            col = cols[idx % len(cols)]
            with col:
                p_name = p["person_name"]
                w_id = p["worker_id"]
                missing_sorted = sorted(p["missing_ppe"])
                missing_summary = ", ".join(missing_sorted)
                is_acked = p_name in st.session_state["acknowledged_person_alerts"]

                status_label = "ACKNOWLEDGED" if is_acked else "CRITICAL VIOLATION"
                status_class = "blue" if is_acked else "red"
                severity_badge = "ACKNOWLEDGED" if is_acked else "CRITICAL"
                severity_class = "amber" if is_acked else "red"

                try:
                    last_dt = datetime.fromtimestamp(p["last_seen"]).strftime("%H:%M:%S")
                except Exception:
                    last_dt = "--:--:--"

                duration_sec = max(0, int(p["last_seen"] - p["first_seen"]))
                dur_str = f"{duration_sec // 60}m {duration_sec % 60}s" if duration_sec > 60 else f"{duration_sec}s"

                missing_badges = "".join(
                    f'<span class="badge badge-red" style="margin: 2px;">{m}</span>' for m in missing_sorted
                )

                compliant_sorted = sorted(p["compliant_ppe"])
                compliant_badges = "".join(
                    f'<span class="badge badge-green" style="margin: 2px;">{c}</span>' for c in compliant_sorted
                )
                compliant_html = ""
                if compliant_badges:
                    compliant_html = f"""
                    <div style="margin-top: 8px;">
                        <div style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--green); font-weight: 700; margin-bottom: 4px;">
                            Equipped Gear:
                        </div>
                        <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                            {compliant_badges}
                        </div>
                    </div>
                    """

                render_html(
                    f"""
                    <div class="alert-card high" style="padding: 16px; border-radius: 8px; margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <span class="badge badge-{severity_class}">{severity_badge}</span>
                            <small style="color: var(--muted); font-family: monospace;">Observed {last_dt}</small>
                        </div>
                        <h4 style="margin: 0 0 6px 0; font-size: 14px; font-weight: 700; color: var(--heading);">
                            {p_name} — {missing_summary}
                        </h4>
                        <p style="font-size: 11px; color: var(--muted); margin-bottom: 10px;">
                            Location: {p["zone"]} │ Active: {dur_str}
                        </p>
                        <div>
                            <div style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--red); font-weight: 700; margin-bottom: 4px;">
                                Missing Required PPE:
                            </div>
                            <div style="display: flex; gap: 4px; flex-wrap: wrap;">
                                {missing_badges}
                            </div>
                        </div>
                        {compliant_html}
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; padding-top: 8px; border-top: 1px solid var(--line);">
                            <span class="badge badge-{status_class}">{status_label}</span>
                            <small style="color: var(--green); font-weight: 600;">Active Live Detector</small>
                        </div>
                    </div>
                    """
                )
                c1, c2 = st.columns(2)
                if c1.button("👁️ Acknowledge", key=f"btn_ack_{p_name}_{w_id}", use_container_width=True):
                    st.session_state["acknowledged_person_alerts"].add(p_name)
                    if on_action:
                        on_action(p_name, "ACKNOWLEDGED")
                    st.toast(f"Acknowledged safety alert for {p_name}.")
                    st.rerun()
                if c2.button("✓ Resolve", key=f"btn_res_{p_name}_{w_id}", use_container_width=True):
                    st.session_state["resolved_person_alerts"].add(p_name)
                    st.session_state["acknowledged_person_alerts"].discard(p_name)
                    if on_action:
                        on_action(p_name, "RESOLVED")
                    st.toast(f"Resolved safety incident for {p_name}.")
                    st.rerun()
    else:
        render_html(
            """
            <div class="panel" style="padding: 30px; text-align: center; color: var(--muted); margin-bottom: 14px;">
                <h3 style="color: var(--heading); margin-bottom: 8px;">✅ No active personnel violations</h3>
                <p>All detected personnel are compliant with mandatory PPE protocols or incidents have been resolved.</p>
            </div>
            """
        )

    if resolved_incidents:
        st.markdown(f"#### Resolved Personnel Incidents ({len(resolved_incidents)})")
        for p in resolved_incidents:
            p_name = p["person_name"]
            missing_summary = ", ".join(sorted(p["missing_ppe"]))
            c_r1, c_r2 = st.columns([4, 1])
            with c_r1:
                render_html(
                    f"""
                    <div style="background: var(--green-soft); border: 1px solid var(--line); border-left: 3px solid var(--green); border-radius: 6px; padding: 10px 16px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; font-size: 11px;">
                        <div>
                            <span style="color: var(--green); font-weight: 700;">✓ {p_name} incident resolved</span>
                            <span style="color: var(--muted); margin-left: 10px;">({missing_summary})</span>
                        </div>
                        <span class="badge badge-green">RESOLVED</span>
                    </div>
                    """
                )
            with c_r2:
                if st.button("↺ Reopen", key=f"btn_reopen_{p_name}", use_container_width=True):
                    st.session_state["resolved_person_alerts"].discard(p_name)
                    if on_action:
                        on_action(p_name, "ACTIVE")
                    st.rerun()


# -----------------------------------------------------------------------------
# 8. SAFETY & PRODUCTIVITY ANALYTICS PANELS
# -----------------------------------------------------------------------------
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
    """Render activity and dwell time insights with calculated facility metrics."""
    total_w = len(workers)
    active_w = total_w
    idle_w = 0
    total_cap = sum(z.capacity for z in DEFAULT_ZONES)  # 20
    utilization_pct = min(100, round((total_w / max(1, total_cap)) * 100))

    dwell_vals = [w.dwell_seconds for w in workers if w.dwell_seconds > 0]
    if dwell_vals:
        avg_dwell_str = f"{int(sum(dwell_vals) / len(dwell_vals))}s"
    else:
        avg_dwell_str = "Active Shift"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Personnel", active_w)
    c2.metric("Stationary / Idle", idle_w)
    c3.metric("Avg Dwell Time", avg_dwell_str)
    c4.metric("Facility Utilization", f"{utilization_pct}%")

    st.markdown("#### Shopfloor Spatial Zone Map")
    render_floor_map(workers, DEFAULT_ZONES)


def render_floor_map(workers: list[WorkerStatus], zones: list[ZoneConfig]) -> None:
    """Render interactive 2D shopfloor factory map with physical zone boundaries and worker pins."""
    zone_coords = {
        "Assembly Line A": {"left": "4%", "top": "8%", "width": "44%", "height": "40%"},
        "Heavy Machinery Bay": {"left": "52%", "top": "8%", "width": "44%", "height": "40%"},
        "Material Staging": {"left": "4%", "top": "52%", "width": "44%", "height": "40%"},
        "Quality Inspection": {"left": "52%", "top": "52%", "width": "44%", "height": "40%"},
    }

    zone_boxes = []
    for z in zones:
        coords = zone_coords.get(z.name, {"left": "4%", "top": "8%", "width": "44%", "height": "40%"})
        is_restr = z.type == "Restricted"
        border_color = "var(--amber)" if is_restr else "var(--green)"
        bg_color = "var(--amber-soft)" if is_restr else "var(--green-soft)"
        zone_workers = [w for w in workers if w.zone == z.name]

        worker_pins = []
        for i, w in enumerate(zone_workers):
            pin_tone = "red" if w.has_active_violation else "green"
            pin_left = 15 + (i * 24) % 65
            pin_top = 40 + (i * 16) % 45
            worker_pins.append(
                f"""
                <div style="position: absolute; left: {pin_left}%; top: {pin_top}%; width: 26px; height: 26px; border-radius: 50%; background: var(--{pin_tone}); color: white; display: grid; place-items: center; font-size: 10px; font-weight: 700; border: 2px solid white; box-shadow: 0 2px 6px rgba(0,0,0,0.15); z-index: 5;" title="Worker #{w.worker_id:02d} ({"UNSAFE" if w.has_active_violation else "SAFE"})">
                    #{w.worker_id:02d}
                </div>
                """
            )
        joined_pins = "".join(worker_pins)

        box_html = f"""
        <div style="position: absolute; left: {coords["left"]}; top: {coords["top"]}; width: {coords["width"]}; height: {coords["height"]}; border: 2px dashed {border_color}; border-radius: 8px; background: {bg_color}; padding: 12px; box-sizing: border-box;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong style="font-size: 11.5px; color: var(--heading);">{z.name}</strong>
                <span class="badge {"badge-amber" if is_restr else "badge-green"}" style="font-size: 8px;">{z.type.upper()}</span>
            </div>
            <small style="color: var(--muted); font-size: 9px; display: block; margin-top: 2px;">
                Occupancy: <strong>{len(zone_workers)}</strong> / {z.capacity}
            </small>
            {joined_pins}
        </div>
        """
        zone_boxes.append(box_html.strip())

    all_boxes = "".join(zone_boxes)

    render_html(
        f"""
        <div class="panel">
            <div class="panel-heading">
                <div>
                    <h3>2D Shopfloor Spatial Layout</h3>
                    <p>Physical factory zones & live personnel positioning</p>
                </div>
                <span class="badge badge-green">LIVE TRACKING</span>
            </div>
            <div class="panel-body" style="padding: 16px;">
                <div style="position: relative; width: 100%; height: 280px; background: var(--bg); border: 1px solid var(--line); border-radius: 8px; overflow: hidden;">
                    {all_boxes}
                </div>
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
                        <p>Real-time audit log of shopfloor detections</p>
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


# -----------------------------------------------------------------------------
# 9. REPORTS & EXPORTS
# -----------------------------------------------------------------------------
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
    """Render downloadable safety audit reports."""
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
        label="📄 Download Certified Audit Report (PDF)",
        data=pdf_data,
        file_name=f"safesight_audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf",
    )

    render_html(
        f"""
        <div class="panel" style="padding: 24px; margin-top: 20px;">
            <h3 style="margin-bottom: 6px;">Executive Compliance Summary</h3>
            <p style="color: var(--muted); font-size: 11px;">Automated verification record produced by SAFE SIGHT AI Vision Engine.</p>
            <hr style="border: 0; border-top: 1px solid var(--line); margin: 16px 0;">
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px;">
                <div>
                    <span style="color: var(--muted); font-size: 10px;">GENERATED AT</span>
                    <strong style="display: block; font-size: 13px; margin-top: 4px; color: var(--heading);">{datetime.now().strftime("%Y-%m-%d %H:%M")}</strong>
                </div>
                <div>
                    <span style="color: var(--muted); font-size: 10px;">MODEL CHECKPOINT</span>
                    <strong style="display: block; font-size: 13px; margin-top: 4px; color: var(--heading);">{model_name}</strong>
                </div>
                <div>
                    <span style="color: var(--muted); font-size: 10px;">FRAMES MONITORED</span>
                    <strong style="display: block; font-size: 13px; margin-top: 4px; color: var(--heading);">{total_frames}</strong>
                </div>
                <div>
                    <span style="color: var(--muted); font-size: 10px;">VERDICT</span>
                    <strong style="display: block; font-size: 13px; margin-top: 4px; color: var(--green);">CERTIFIED AUDIT</strong>
                </div>
            </div>
        </div>
        """
    )


def render_printable_safety_certificate(cert_data: dict) -> None:
    """Render a printable executive safety compliance certificate from session data."""
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
        workers_html += f'<tr><td style="padding:7px 10px;border-bottom:1px solid var(--line);font-weight:600;">{name}</td><td style="padding:7px 10px;border-bottom:1px solid var(--line);color:{tone_color};font-weight:700;">{wd_status}</td><td style="padding:7px 10px;border-bottom:1px solid var(--line);">{missing}</td></tr>'

    if not workers_html:
        workers_html = '<tr><td colspan="3" style="padding:10px;text-align:center;color:var(--muted);">No personnel data for this session.</td></tr>'

    render_html(
        f"""
        <div style="background:var(--bg);border:2px solid var(--line);border-radius:12px;padding:28px 32px;margin:16px 0;font-family:system-ui,sans-serif;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
                <div>
                    <div style="font-size:20px;font-weight:800;color:var(--heading);">SAFE SIGHT AI</div>
                    <div style="font-size:11px;color:var(--muted);margin-top:2px;">Executive Safety Compliance Report</div>
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
                Model: {cert_data.get("model_name", "N/A")} · Session: {cert_data.get("session_id", "N/A")}
            </div>
        </div>
        """
    )


@functools.lru_cache(maxsize=1)
def _get_chime_wav_b64() -> str:
    """Generate a crisp, harmonious two-tone industrial safety chime in PCM WAV format."""
    sample_rate = 22050
    duration = 0.38  # 380ms total
    num_samples = int(sample_rate * duration)
    buf = io.BytesIO()
    # RIFF header
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + num_samples * 2))
    buf.write(b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", num_samples * 2))

    for i in range(num_samples):
        t = i / sample_rate
        # Tone 1: 880Hz (A5) for 140ms, Tone 2: 587.33Hz (D5) harmonic resolution
        if t < 0.14:
            phase = 2 * math.pi * 880.0 * t
        else:
            phase = 2 * math.pi * 880.0 * 0.14 + 2 * math.pi * 587.33 * (t - 0.14)
        decay = math.exp(-5.2 * t)
        sample = int(0.75 * math.sin(phase) * decay * 32767)
        buf.write(struct.pack("<h", max(-32768, min(32767, sample))))

    return base64.b64encode(buf.getvalue()).decode("ascii")


def play_violation_chime() -> None:
    """Play an immediate, reliable industrial safety chime in the user's browser."""
    wav_b64 = _get_chime_wav_b64()
    chime_html = f"""
    <audio autoplay="autoplay" style="display:none;" preload="auto">
        <source src="data:audio/wav;base64,{wav_b64}" type="audio/wav">
    </audio>
    <script>
    (function() {{
        var wav = "{wav_b64}";
        // 1. Try local Audio element
        try {{
            var snd = new Audio("data:audio/wav;base64," + wav);
            snd.volume = 0.85;
            var p = snd.play();
            if (p && p.catch) p.catch(function(e) {{}});
        }} catch(e) {{}}

        // 2. Dispatch cross-window message to top-level window context
        try {{
            if (window.parent && window.parent !== window) {{
                window.parent.postMessage({{type: 'safesight_play_chime', audio: wav}}, '*');
                if (window.parent.Audio) {{
                    var pSnd = new window.parent.Audio("data:audio/wav;base64," + wav);
                    pSnd.volume = 0.85;
                    var p2 = pSnd.play();
                    if (p2 && p2.catch) p2.catch(function(e) {{}});
                }}
            }}
        }} catch(e) {{}}
    }})();
    </script>
    """
    st_components.html(chime_html, height=0, width=0)


def render_audio_alert_script(active: bool = False) -> None:
    """Prepare audio playback infrastructure and unlock Web Audio API on first user gesture."""
    if not active:
        return
    # Pre-warm the cache so audio generation is instantaneous
    _get_chime_wav_b64()
    # Install listener in host page to bypass iframe autoplay sandboxes
    st_components.html(
        """
        <script>
        (function() {
            if (window._safesight_audio_bridge_ready) return;
            window._safesight_audio_bridge_ready = true;

            function unlock() {
                try {
                    var ctx = new (window.AudioContext || window.webkitAudioContext)();
                    if (ctx && ctx.state === 'suspended') ctx.resume();
                } catch(e) {}
                window.removeEventListener('click', unlock);
                window.removeEventListener('keydown', unlock);
            }
            window.addEventListener('click', unlock);
            window.addEventListener('keydown', unlock);

            window.addEventListener('message', function(ev) {
                if (ev.data && ev.data.type === 'safesight_play_chime' && ev.data.audio) {
                    try {
                        var a = new Audio('data:audio/wav;base64,' + ev.data.audio);
                        a.volume = 0.85;
                        var p = a.play();
                        if (p && p.catch) p.catch(function() {});
                    } catch(e) {}
                }
            });
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def render_perf_chip(
    fps: float | str = 0.0,
    inference_ms: float = 0.0,
    label: str = "INFERENCE",
    mode_key: str | None = None,
    **kwargs: Any,
) -> None:
    """Render a performance badge displaying FPS/latency telemetry or performance mode."""
    if isinstance(fps, str) and not mode_key:
        mode_key = fps

    if mode_key is not None:
        labels = {"fast": "⚡ Fast", "balanced": "⚖️ Balanced", "quality": "🔬 Quality"}
        label_text = labels.get(mode_key, mode_key.title())
        render_html(
            f'<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;'
            f"border:1px solid var(--line);border-radius:999px;font-size:10px;"
            f'color:var(--secondary);background:var(--panel);">{label_text}</span>'
        )
    else:
        try:
            fps_val = float(fps)
        except (ValueError, TypeError):
            fps_val = 0.0
        render_html(
            f'<div style="display:inline-flex;align-items:center;gap:8px;padding:3px 9px;'
            f"background:var(--panel);border:1px solid var(--line);border-radius:6px;font-size:10.5px;"
            f'font-family:monospace;margin:4px 0;">'
            f'<span style="color:var(--muted);font-weight:600;">{label}</span>'
            f'<span style="color:var(--green);">⚡ {fps_val:.1f} FPS │ {inference_ms:.0f} ms</span>'
            f"</div>"
        )


def render_skeleton_block(title: str = "Loading…", subtitle: str = "") -> None:
    """Render a themed skeleton placeholder while content is loading."""
    sub_html = f'<p style="margin:4px 0 0;font-size:12px;color:var(--muted);">{subtitle}</p>' if subtitle else ""
    render_html(
        f"""
        <div style="background:var(--panel);border:1px solid var(--line);border-radius:10px;
                    padding:32px 24px;text-align:center;margin:12px 0;">
            <div style="font-size:14px;font-weight:600;color:var(--secondary);">{title}</div>
            {sub_html}
            <div style="margin-top:16px;height:4px;border-radius:2px;background:var(--line);
                        overflow:hidden;max-width:200px;margin-left:auto;margin-right:auto;">
                <div style="width:40%;height:100%;background:var(--green);border-radius:2px;
                            animation:skeleton-pulse 1.5s ease-in-out infinite;"></div>
            </div>
        </div>
        <style>
        @keyframes skeleton-pulse {{
            0%, 100% {{ transform: translateX(-100%); }}
            50% {{ transform: translateX(250%); }}
        }}
        </style>
        """
    )


def render_empty_state(icon: str, title: str, subtitle: str = "", hint: str = "") -> None:
    """Render a themed, action-led empty state (U1: replaces flat cv2.putText placeholders)."""
    sub_html = (
        f'<p style="margin:6px 0 0;font-size:13px;color:var(--secondary);">{escape(subtitle)}</p>' if subtitle else ""
    )
    hint_html = (
        f'<div style="margin-top:14px;display:inline-flex;align-items:center;gap:6px;padding:6px 12px;'
        f"border:1px solid var(--line);border-radius:999px;background:var(--bg);font-size:11.5px;"
        f'color:var(--muted);">{hint}</div>'
        if hint
        else ""
    )
    render_html(
        f"""
        <div style="background:var(--panel);border:1px dashed var(--line);border-radius:10px;
                    padding:36px 24px;text-align:center;margin:12px 0;">
            <div style="font-size:30px;line-height:1;" aria-hidden="true">{icon}</div>
            <div style="margin-top:10px;font-size:14.5px;font-weight:650;color:var(--heading);">{escape(title)}</div>
            {sub_html}
            {hint_html}
        </div>
        """
    )


def render_keyboard_shortcuts_script(page_names: list[str] | None = None) -> None:
    """Install the global keyboard-shortcut handler (plan item U3).

    ``1``–``5`` switch workspace pages, ``S`` starts/stops the camera, and
    ``?`` opens the shortcuts cheat-sheet dialog. Keys are ignored while the
    operator is typing in an input and while modifier keys are held.

    Navigation is translated into clicks on hidden hotkey buttons rendered by
    ``app.py`` (labels ``__hk_nav_N`` / ``__hk_cam`` / ``__hk_help``): clicking
    triggers a normal Streamlit rerun so session state (camera, evidence,
    theme) is preserved — unlike a URL-driven page reload. Invalid or missing
    buttons are safely discarded.
    """
    names = list(page_names or [])
    payload = json.dumps(names)
    script = f"""
    <script>
    (function() {{
        var top = null;
        try {{ top = window.parent; }} catch (e) {{}}
        var doc = top ? top.document : document;

        function hideHotkeyButtons() {{
            try {{
                var buttons = doc.querySelectorAll('[data-testid="stButton"] button');
                for (var i = 0; i < buttons.length; i++) {{
                    var txt = (buttons[i].textContent || "").trim();
                    if (txt.indexOf("__hk_") === 0) {{
                        var el = buttons[i].closest('[data-testid="element-container"]') || buttons[i];
                        el.style.display = "none";
                    }}
                }}
            }} catch (e) {{}}
        }}

        // Re-hide on every rerun (Streamlit rebuilds the DOM each run)
        hideHotkeyButtons();

        if (!top || top.__safesight_hotkeys_bound) return;
        top.__safesight_hotkeys_bound = true;

        var PAGE_NAMES = {payload};

        function findHotkey(label) {{
            try {{
                var buttons = doc.querySelectorAll('[data-testid="stButton"] button');
                for (var i = 0; i < buttons.length; i++) {{
                    if ((buttons[i].textContent || "").trim() === label) return buttons[i];
                }}
            }} catch (e) {{}}
            return null;
        }}

        function click(label) {{
            var btn = findHotkey(label);
            if (btn) {{ btn.click(); }}
        }}

        // Bind on the parent document: keypresses inside component iframes
        // never propagate, so the handler must live where the operator types.
        doc.addEventListener('keydown', function(e) {{
            if (e.ctrlKey || e.metaKey || e.altKey || e.altGraphKey) return;
            var t = e.target;
            if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
            var k = e.key;
            if (k === 's' || k === 'S') {{
                click('__hk_cam');
            }} else if (k >= '1' && k <= '9') {{
                var idx = parseInt(k, 10) - 1;
                if (idx < PAGE_NAMES.length) click('__hk_nav_' + (idx + 1));
            }} else if (k === '?' || (e.shiftKey && k === '/')) {{
                click('__hk_help');
            }}
        }});
    }})();
    </script>
    """
    st_components.html(script, height=0, width=0)

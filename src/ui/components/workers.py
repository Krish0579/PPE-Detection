"""Worker-facing views: person status cards, the status table, and the
workspace zone map."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.config.settings import ZoneConfig
from src.core.ppe_associator import WorkerStatus
from src.ui.components.base import render_html


def render_workers_grid(workers: list[WorkerStatus]) -> None:
    """Render anonymous worker tracking cards."""
    if not workers:
        render_html(
            """
            <div class="panel">
                <div class="panel-body" style="text-align: center; color: var(--muted); padding: 35px;">
                    <h3 style="color: var(--heading); margin-bottom: 8px;">No personnel currently detected in frame</h3>
                    <p>Start a camera or run the demo source to track people in the current workspace.</p>
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


WORKER_TABLE_COLUMNS = (
    "Personnel",
    "Status",
    "⛑️ Helmet",
    "🦺 Vest",
    "🧤 Gloves",
    "🥾 Boots",
    "🥽 Goggles",
    "Zone",
    "Active Violations",
)


def build_workers_status_dataframe(workers: list[Any]) -> pd.DataFrame:
    """Construct an explicit per-worker PPE status table clearly displaying each category separately.

    Three states are kept distinct because collapsing them misleads a supervisor:
    worn, confirmed missing, and *not observed*. An unobserved item is rendered
    neutrally rather than as a red failure, since the detector never saw it.
    """
    rows = []
    for w in workers:
        req = getattr(w, "required_ppe", None) or {}

        def _fmt(st: str, key: str, worn_txt: str, no_txt: str, req: dict = req) -> str:
            if req and not req.get(key, True):
                return "– Optional"
            if st == "COMPLIANT":
                return f"✅ {worn_txt}"
            if st == "VIOLATION":
                return f"❌ {no_txt}"
            return "⚠️ Not observed"

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
    # Always return the full column set so an empty table still renders headers.
    return pd.DataFrame(rows, columns=list(WORKER_TABLE_COLUMNS))


def render_floor_map(workers: list[WorkerStatus], zones: list[ZoneConfig]) -> None:
    """Render the interactive 2D workspace map with zone boundaries and pins."""
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
                    <h3>Workspace zone layout</h3>
                    <p>Configured zones and current person positions</p>
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

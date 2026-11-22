"""Alert center: per-person violation consolidation with acknowledge/resolve actions.

Consolidation deliberately produces exactly one persistent record per person
rather than one per frame, so an operator acknowledges a violation once
instead of fighting a stream of duplicates.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import streamlit as st

from src.ui.components.base import render_html


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
                # A label with no person identity ("no helmet") cannot be
                # attributed to a specific human. Previously it was pinned to
                # "Person 1" unconditionally, which in a multi-person session
                # falsely incriminated Person 1 — bad in an evidence product.
                # Only attribute it when exactly one person is in scope.
                if ("no" in lbl.lower() or "violation" in lbl.lower()) and single_worker_session:
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
                <p>No active incident is open. New detections will appear here grouped by person.</p>
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

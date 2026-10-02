"""Command Center — production-grade landing dashboard (minimal MVP integration).

This page provides a concise, operator-focused overview intended to be the primary landing
screen. It leverages the existing TelemetryState and worker/event data exposed by the
VideoPipeline in AppContext.
"""

from __future__ import annotations

from datetime import datetime

from src.ui.app_context import AppContext
from src.ui.components import render_html


def _health_status(ctx: AppContext) -> str:
    # Simple health classification based on model load and camera state
    if ctx.load_error:
        return "DEGRADED"
    if ctx.camera_manager and getattr(ctx.camera_manager, 'is_running', False):
        return "HEALTHY"
    return "DEGRADED" if not ctx.pipeline else "HEALTHY"


def render(ctx: AppContext) -> None:
    """Render the Command Center landing view."""
    s = ctx.state
    workers = s.get_history_df() if hasattr(s, 'get_history_df') else None

    # Basic counts derived from TelemetryState
    total_people = len(ctx.state.workers) if hasattr(ctx.state, 'workers') else 0
    active_incidents = sum(1 for w in getattr(ctx.state, 'workers', []) if getattr(w, 'has_active_violation', False))
    camera_count = len(ctx.devices) if hasattr(ctx, 'devices') else 0
    current_fps = getattr(ctx.pipeline, 'smoothed_fps', 0.0) if hasattr(ctx, 'pipeline') else 0.0
    latency = getattr(ctx.state, 'inference_ms', 0.0)
    health = _health_status(ctx)

    # Header shell (compact, non-animated)
    render_html(
        f"""
        <div class='panel' style='padding:12px 16px; display:flex; align-items:center; justify-content:space-between; border-radius:8px; margin-bottom:12px; background:var(--panel); border:1px solid var(--line);'>
            <div style='display:flex; align-items:center; gap:12px;'>
                <div style='width:40px; height:40px; border-radius:8px; display:grid; place-items:center; background:var(--green-soft); color:var(--green); font-weight:800;'>🛡️</div>
                <div>
                    <strong style='font-size:14px; color:var(--heading);'>SAFE SIGHT AI</strong>
                    <div style='font-size:11px; color:var(--muted);'>Industrial PPE Safety Command Center</div>
                </div>
            </div>
            <div style='display:flex; gap:12px; align-items:center;'>
                <span class='badge badge-green' style='padding:6px 12px; font-size:12px; border-radius:6px;'>Health: {health}</span>
                <span class='badge badge-blue' style='padding:6px 12px; font-size:12px; border-radius:6px;'>Cameras: {camera_count}</span>
                <span class='badge badge-slate' style='padding:6px 12px; font-size:12px; border-radius:6px;'>Active Incidents: {active_incidents}</span>
                <span class='badge badge-green' style='padding:6px 12px; font-size:12px; border-radius:6px;'>Time: {datetime.now().strftime('%H:%M:%S')}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Live status row
    render_html(
        f"""
        <div class='panel' style='padding:14px; border-radius:8px; margin-bottom:12px; border:1px solid var(--line);'>
            <div style='font-weight:700; font-size:14px; color:var(--heading); margin-bottom:6px;'>LIVE CAMERA/SAFETY SITUATION</div>
            <div style='display:grid; grid-template-columns: repeat(4, 1fr); gap:12px;'>
                <div class='panel' style='padding:12px; border-radius:6px; background:var(--bg);'>
                    <div style='font-size:11px; color:var(--muted);'>Tracked People</div>
                    <div style='font-size:20px; font-weight:800; color:var(--heading);'>{total_people}</div>
                </div>
                <div class='panel' style='padding:12px; border-radius:6px; background:var(--bg);'>
                    <div style='font-size:11px; color:var(--muted);'>Active Incidents</div>
                    <div style='font-size:20px; font-weight:800; color:var(--heading);'>{active_incidents}</div>
                </div>
                <div class='panel' style='padding:12px; border-radius:6px; background:var(--bg);'>
                    <div style='font-size:11px; color:var(--muted);'>FPS</div>
                    <div style='font-size:20px; font-weight:800; color:var(--heading);'>{current_fps:.1f}</div>
                </div>
                <div class='panel' style='padding:12px; border-radius:6px; background:var(--bg);'>
                    <div style='font-size:11px; color:var(--muted);'>Latency</div>
                    <div style='font-size:20px; font-weight:800; color:var(--heading);'>{latency:.1f} ms</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Incidents summary
    events = getattr(ctx.state, 'get_events', lambda: [])()
    if isinstance(events, list) and events:
        render_html(
            f"""
            <div class='panel' style='padding:12px 16px; border-radius:8px; border:1px solid var(--line);'>
                <div style='font-weight:700; font-size:14px; color:var(--heading); margin-bottom:6px;'>ACTIVE INCIDENTS</div>
                <div style='max-height:200px; overflow:auto;'>
                    <ul style='margin:0; padding-left:20px;'>
                        {''.join(f'<li style=\"margin:4px 0; color:var(--muted);\">{e.get("type","INCIDENT")} @ {e.get("ts", "")}</li>' for e in events[:6])}
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # KPI strip (basic)
    render_html(
        f"""
        <div class='panel' style='padding:12px 16px; border-radius:8px; border:1px solid var(--line); margin-top:8px;'>
            <div style='font-weight:700; font-size:14px; color:var(--heading);'>PERSONNEL & METRICS</div>
            <div style='display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin-top:8px;'>
                <div style='padding:8px; background:var(--bg); border-radius:6px; text-align:center;'>
                    <div style='font-size:11px; color:var(--muted);'>Workers</div>
                    <div style='font-size:18px; font-weight:700; color:var(--heading);'>{total_people}</div>
                </div>
                <div style='padding:8px; background:var(--bg); border-radius:6px; text-align:center;'>
                    <div style='font-size:11px; color:var(--muted);'>Incidents</div>
                    <div style='font-size:18px; font-weight:700; color:var(--heading);'>{active_incidents}</div>
                </div>
                <div style='padding:8px; background:var(--bg); border-radius:6px; text-align:center;'>
                    <div style='font-size:11px; color:var(--muted);'>FPS</div>
                    <div style='font-size:18px; font-weight:700; color:var(--heading);'>{current_fps:.1f}</div>
                </div>
                <div style='padding:8px; background:var(--bg); border-radius:6px; text-align:center;'>
                    <div style='font-size:11px; color:var(--muted);'>Latency</div>
                    <div style='font-size:18px; font-weight:700; color:var(--heading);'>{latency:.0f} ms</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Legend (static)
    render_html(
        """
        <div class='panel' style='padding:10px 12px; border-radius:6px; border:1px solid var(--line); margin-top:6px;'>
            <span class='badge badge-green' style='margin-right:6px;'>GREEN</span> Compliant
            <span class='badge badge-amber' style='margin:0 6px;'>AMBER</span> Attention
            <span class='badge badge-red' style='margin-left:6px;'>RED</span> Violation
        </div>
        """,
        unsafe_allow_html=True,
    )

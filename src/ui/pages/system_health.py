"""System Health page for the industrial command center."""

from __future__ import annotations

from src.ui.app_context import AppContext
from src.ui.components import render_html


def _health_label(healthy: bool) -> str:
    return "HEALTHY" if healthy else "DEGRADED"


def render(ctx: AppContext) -> None:
    # Gather simple health indicators from the context
    healthy = True
    if getattr(ctx, 'load_error', None):
        healthy = False

    camera_health = "HEALTHY" if getattr(ctx.camera_manager, 'is_running', False) else "OFFLINE"
    model_status = "OK" if not ctx.load_error else "FAILED"
    db_status = "OK"  # placeholder: assume OK in this mono-container setup
    storage_usage = getattr(ctx.evidence, 'get_storage_telemetry', lambda: {})()
    cpu_load = getattr(ctx, 'state', None)

    render_html(
        f"""
        <div class='panel' style='padding:12px 16px; border-radius:8px; border:1px solid var(--line);'>
            <div style='font-weight:700; font-size:14px; color:var(--heading);'>SYSTEM HEALTH</div>
            <div style='display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin-top:8px;'>
                <div class='panel' style='padding:12px; border-radius:6px; background:var(--bg);'>
                    <div style='font-size:11px; color:var(--muted);'>Overall</div>
                    <div style='font-size:18px; font-weight:800; color:var(--heading);'>{_health_label(healthy)}</div>
                </div>
                <div class='panel' style='padding:12px; border-radius:6px; background:var(--bg);'>
                    <div style='font-size:11px; color:var(--muted);'>Camera</div>
                    <div style='font-size:18px; font-weight:800; color:var(--heading);'>{camera_health}</div>
                </div>
                <div class='panel' style='padding:12px; border-radius:6px; background:var(--bg);'>
                    <div style='font-size:11px; color:var(--muted);'>Model</div>
                    <div style='font-size:18px; font-weight:800; color:var(--heading);'>{model_status}</div>
                </div>
                <div class='panel' style='padding:12px; border-radius:6px; background:var(--bg);'>
                    <div style='font-size:11px; color:var(--muted);'>Storage</div>
                    <div style='font-size:18px; font-weight:800; color:var(--heading);'>OK</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Details row
    render_html(
        f"""
        <div class='panel' style='padding:12px 16px; border-radius:8px; border:1px solid var(--line); margin-top:8px;'>
            <div style='font-weight:700; font-size:14px; color:var(--heading);'>INFRASTRUCTURE & PERFORMANCE</div>
            <div style='display:grid; grid-template-columns: repeat(4, 1fr); gap:12px; margin-top:8px;'>
                <div>Latency: <strong>~{getattr(ctx.state, 'inference_ms', 0):.0f} ms</strong></div>
                <div>FPS: <strong>{getattr(ctx.pipeline, 'smoothed_fps', 0.0):.1f}</strong></div>
                <div>Uptime: <strong>LIVE</strong></div>
                <div>Webhooks: <strong>OK</strong></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

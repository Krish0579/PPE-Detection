"""Camera Wall — compact live wall with per-camera tiles and a Camera Focus view placeholder."""

from __future__ import annotations

from src.ui.app_context import AppContext
from src.ui.components import render_html


def render(ctx: AppContext) -> None:
    # Build a simple wall from available devices
    devices = getattr(ctx, 'devices', []) or []
    render_html(
        f"""
        <div class='panel' style='padding: 12px 14px; border-radius: 8px; border:1px solid var(--line);'>
            <div style='font-weight:700; font-size:14px; color:var(--heading);'>CAMERA WALL</div>
            <div style='font-size:12px; color:var(--muted);'>Live tiles for configured cameras</div>
        </div>
        """
    )

    # Grid of camera tiles
    cols = 4
    if not devices:
        render_html(
            """<div class='panel' style='padding: 20px; text-align: center; color: var(--muted);'>No cameras configured.</div>"""
        )
        return
    per_row = []
    row_html = ""
    for i, dev in enumerate(devices):
        cam_id = f"CAM-{i+1:02d}"
        location = getattr(ctx, 'pipeline', None) and getattr(ctx.pipeline, 'model', None) or dev
        # Simple tile
        tile = f"""
        <div class='panel' style='padding:8px; border-radius:6px; background:var(--bg); border:1px solid var(--line); text-align:left;'>
            <div style='font-weight:700; font-size:12px; color:var(--heading);'>{cam_id} • {location}</div>
            <div style='font-size:11px; color:var(--muted);'>Status: LIVE</div>
            <div style='font-size:11px; color:var(--muted);'>FPS: 0.0 • Latency: 0 ms</div>
            <div style='margin-top:6px;'>
                <button style='font-size:11px; padding:4px 8px; border-radius:6px; border:1px solid var(--line); background:var(--panel);'>Open Focus</button>
            </div>
        </div>
        """
        row_html += tile
        if (i + 1) % cols == 0:
            per_row.append(f"<div style='display:grid; grid-template-columns: repeat({cols}, 1fr); gap:12px; margin-bottom:12px;'>{row_html}</div>")
            row_html = ""
    if row_html:
        per_row.append(f"<div style='display:grid; grid-template-columns: repeat({cols}, 1fr); gap:12px; margin-bottom:12px;'>{row_html}</div>")
    render_html("""<div class='panel' style='padding: 12px; border-radius: 8px; border: 1px solid var(--line);'>""" + "".join(per_row) + "</div>" )

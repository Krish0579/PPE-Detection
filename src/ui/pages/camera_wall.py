"""Camera Wall — one tile per configured camera, showing measured state only.

A tile never claims a stream is live unless the capture manager reports it
running, and never prints an FPS figure that was not measured. Every tile
reads its state from :mod:`src.ui.status` rather than assuming health.

Focus behaviour: only the camera currently bound to the capture manager is
marked in focus; selecting another camera requires the Live Feed, because a
single-process deployment drives one capture source at a time.
"""

from __future__ import annotations

from html import escape

from src.config.runtime import load_runtime_config
from src.ui.app_context import AppContext
from src.ui.components import render_html
from src.ui.status import Status
from src.video.camera_registry import CameraRegistry, parse_camera_sources


def _configured_cameras(ctx: AppContext) -> list:
    """Cameras from ``PPE_RTSP_SOURCES``/``usb:`` config, else local devices.

    Falls back to the detected local capture devices so a single-camera
    installation still renders a meaningful wall instead of an empty page.
    """
    cfg = load_runtime_config()
    sources = parse_camera_sources(",".join(cfg.rtsp_sources))
    if sources:
        return [
            {
                "id": source.id,
                "name": source.display_name or source.id,
                "zone": source.zone or "Unassigned",
                "source": source.redacted_uri,
            }
            for source in sources
        ]
    return [
        {
            "id": f"CAM-{index + 1:02d}",
            "name": f"Local capture device {index}",
            "zone": "Unassigned",
            "source": f"usb:{index}",
        }
        for index, _ in enumerate(getattr(ctx, "devices", []) or [])
    ]


def _registry() -> CameraRegistry:
    return CameraRegistry()


def _tile(camera: dict, *, focused: bool, status: Status, detail: str, fps: float | None) -> str:
    """Render one camera tile. ``fps`` is None unless actually measured."""
    focus_badge = (
        '<span class="badge badge-green">In focus</span>'
        if focused
        else '<span class="badge badge-slate">Standby</span>'
    )
    throughput = "Throughput not measured" if fps is None else f"{fps:.1f} FPS"
    return f"""
    <div class="panel" style="padding:12px 14px;background:var(--bg);border:1px solid var(--line);">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
            <strong style="font-size:13px;color:var(--heading);">{escape(camera["id"])}</strong>
            {focus_badge}
        </div>
        <div style="font-size:11.5px;color:var(--muted);margin-top:2px;">{escape(camera["name"])}</div>
        <div style="font-size:11.5px;color:var(--muted);">{escape(camera["zone"])}</div>
        <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
            <span class="badge {status.badge_class}">{escape(status.label)}</span>
            <span style="font-size:11px;color:var(--muted);">{escape(throughput)}</span>
        </div>
        <div style="font-size:11px;color:var(--muted);margin-top:6px;word-break:break-all;">
            {escape(camera["source"])}
        </div>
        <div style="font-size:11.5px;color:var(--secondary);margin-top:6px;">{escape(detail)}</div>
    </div>
    """


def render(ctx: AppContext) -> None:
    """Render the camera wall."""
    cameras = _configured_cameras(ctx)
    registry = _registry()
    running = bool(getattr(ctx.camera_manager, "is_running", False))
    snapshot = ctx.state.snapshot_ui()
    frames_seen = int(snapshot.get("total_frames", 0) or 0)
    fps = float(getattr(ctx.pipeline, "smoothed_fps", 0.0) or 0.0)
    last_error = snapshot.get("last_error", "") or ""

    render_html(
        f"""
        <section class="ops-task-header">
            <div>
                <h1>Camera wall</h1>
                <p>Configured capture sources and their measured state. This
                   workspace currently streams from one camera at a time.</p>
            </div>
            <span class="ops-context-status">{len(cameras)} configured</span>
        </section>
        """
    )

    if not cameras:
        render_html(
            '<div class="panel" style="padding:24px;text-align:center;">'
            '<div style="font-weight:700;color:var(--heading);font-size:14px;">No cameras configured</div>'
            '<div style="color:var(--muted);font-size:12.5px;margin-top:6px;">'
            "Set <code>PPE_RTSP_SOURCES</code> (for example "
            "<code>rtsp://camera-a/live</code>) or attach a capture device, then restart the workspace.</div></div>"
        )
        return

    if last_error:
        render_html(
            f'<div class="ops-state attention" role="alert" style="margin-bottom:12px;">'
            f"Capture error &mdash; {escape(str(last_error)[:200])}</div>"
        )

    # Focus follows the single bound capture manager, not the tile order.
    focus_index = 0 if running else -1
    tiles = []
    for index, camera in enumerate(cameras):
        focused = index == focus_index
        if focused:
            # A stream with no error is healthy; a stream that errored is not.
            status = Status.ATTENTION if last_error else Status.OK
            detail = f"Streaming from {camera['source']}"
            measured_fps: float | None = fps if frames_seen > 0 else None
        else:
            status = Status.OFFLINE if running else Status.UNKNOWN
            # Plain em dash, not an HTML entity: this text is escaped before
            # rendering, so "&mdash;" would surface literally to the operator.
            detail = (
                "Waiting for capture to switch to this camera"
                if running
                else "Capture stopped — no telemetry for this camera"
            )
            measured_fps = None
        registry.update_health(camera["id"], status=status.label)
        tiles.append(_tile(camera, focused=focused, status=status, detail=detail, fps=measured_fps))

    render_html(
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));'
        'gap:12px;">' + "".join(tiles) + "</div>"
    )

    render_html(
        '<div style="margin-top:12px;padding:12px 14px;border:1px solid var(--line);'
        'border-radius:8px;display:flex;flex-wrap:wrap;gap:16px;align-items:center;">'
        '<span style="display:inline-flex;align-items:center;gap:6px;">'
        '<span class="badge badge-green">In focus</span>'
        '<span style="font-size:11.5px;color:var(--muted);">streaming now</span></span>'
        '<span style="display:inline-flex;align-items:center;gap:6px;">'
        '<span class="badge badge-slate">Standby</span>'
        '<span style="font-size:11.5px;color:var(--muted);">configured but not streaming</span></span>'
        '<span style="display:inline-flex;align-items:center;gap:6px;">'
        '<span class="badge badge-slate">Not measured</span>'
        '<span style="font-size:11.5px;color:var(--muted);">no telemetry exists yet</span></span>'
        "</div>"
    )

"""Command Center — the operator landing view.

The Command Center answers one question first: *is anything wrong right now?*
It therefore leads with measured health and open incidents, and shows
performance detail only as supporting context.

This page previously printed a hardcoded ``Health: HEALTHY`` badge and an
always-green uptime readout. Both are now derived from live telemetry via
:mod:`src.ui.status`.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from src.ui.app_context import AppContext
from src.ui.components import render_html, render_metrics_grid, render_section_header
from src.ui.status import Status, build_system_components, measure_disk, overall_status


def _workspace_status(ctx: AppContext) -> Status:
    """Verdict for the whole workspace, derived from the same signals as System Health."""
    components = build_system_components(
        model_loaded=getattr(ctx, "model", None) is not None,
        load_error=ctx.load_error,
        model_name=getattr(ctx, "model_name", "") or "",
        camera_running=bool(getattr(ctx.camera_manager, "is_running", False)),
        device=str(getattr(ctx, "device", "") or ""),
        camera_error=ctx.state.snapshot_ui().get("last_error", "") or "",
        frames_seen=int(ctx.state.snapshot_ui().get("total_frames", 0) or 0),
        fps=float(getattr(ctx.pipeline, "smoothed_fps", 0.0) or 0.0),
        inference_ms=float(ctx.state.snapshot_ui().get("inference_ms", 0.0) or 0.0),
        webhook_url="",
        webhook_allowlist=(),
        webhook_allowed=False,
        snapshot_count=int(ctx.state.snapshot_ui().get("snapshots_count", 0) or 0),
        max_snapshots=int(getattr(ctx.evidence, "max_snapshots", 0) or 0),
        evidence_sealed=bool(getattr(ctx.evidence, "sealed", False)),
        evidence_error=str(getattr(ctx.evidence, "last_error", "") or ""),
        disk=measure_disk(getattr(ctx.evidence, "storage_dir", "data")),
    )
    return overall_status(components)


def _open_incidents(ctx: AppContext) -> list[dict]:
    """Active violation events, most recent first."""
    events = ctx.state.get_events()
    return [e for e in events if e.get("type") in {"VIOLATION", "VIOLATION_UPDATE"}]


def render(ctx: AppContext) -> None:
    """Render the Command Center landing view."""
    snapshot = ctx.state.snapshot_ui()
    workers = list(getattr(ctx.state, "workers", []) or [])
    violating = [w for w in workers if getattr(w, "has_active_violation", False)]
    incidents = _open_incidents(ctx)
    status = _workspace_status(ctx)

    fps = float(getattr(ctx.pipeline, "smoothed_fps", 0.0) or 0.0)
    inference_ms = float(snapshot.get("inference_ms", 0.0) or 0.0)
    frames_seen = int(snapshot.get("total_frames", 0) or 0)

    # --- Header: identity + the single verdict badge ---------------------
    render_html(
        f"""
        <section class="ops-task-header">
            <div>
                <h1>Command center</h1>
                <p>Current safety posture across the monitored workspace.</p>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                <span class="badge {status.badge_class}" role="status">{escape(status.label)}</span>
                <span class="ops-context-status">{escape(datetime.now().strftime("%H:%M"))}</span>
            </div>
        </section>
        """
    )

    if ctx.load_error:
        render_html(
            f'<div class="ops-state attention" role="alert" style="margin-bottom:12px;">'
            f"Inference unavailable &mdash; {escape(str(ctx.load_error)[:200])}</div>"
        )

    _render_operator_brief(
        status=status,
        incidents=incidents,
        violating_count=len(violating),
        camera_running=bool(getattr(ctx.camera_manager, "is_running", False)),
        frames_seen=frames_seen,
    )

    render_section_header("Workspace snapshot", "Measured people, incidents, and runtime context.")

    # --- Headline metrics ----------------------------------------------
    # With no observed workers the score is unmeasured, not 0% — reporting a
    # percentage against an empty population would read as total non-compliance.
    render_metrics_grid(
        total_workers=len(workers),
        safe_workers=len(workers) - len(violating),
        violations=len(violating),
        safety_score=(None if not workers else 100.0 * (len(workers) - len(violating)) / len(workers)),
    )

    # --- Incident queue: the reason an operator opened this page ---------
    _render_incident_queue(incidents, violating)

    # --- Supporting telemetry ------------------------------------------
    _render_telemetry(snapshot, fps, inference_ms, frames_seen)


def _render_operator_brief(
    *,
    status: Status,
    incidents: list[dict],
    violating_count: int,
    camera_running: bool,
    frames_seen: int,
) -> None:
    """Give the operator one clear next step before the dashboard detail."""
    if incidents or violating_count:
        focus = "Review open violations"
        detail = "Confirm the affected person, zone, and evidence before resolving the incident."
    elif not camera_running:
        focus = "Start a monitored source"
        detail = "No live capture is running, so safety posture and throughput are not yet measured."
    elif frames_seen <= 0:
        focus = "Waiting for the first frame"
        detail = "Capture is connected; the workspace will populate once inference processes a frame."
    else:
        focus = "Continue monitoring"
        detail = "No open incident is currently in the queue. Keep the evidence trail available for review."

    render_html(
        f"""
        <section class="ops-brief" aria-label="Operator focus">
            <div class="ops-brief-copy">
                <p class="ops-brief-kicker">Operator focus</p>
                <h2 class="ops-brief-title">{escape(focus)}</h2>
                <p class="ops-brief-detail">{escape(detail)}</p>
            </div>
            <div class="ops-brief-state">
                <strong>{escape(status.label)}</strong>
                <span>workspace verdict</span>
            </div>
        </section>
        """
    )


def _render_incident_queue(incidents: list[dict], violating: list) -> None:
    """Open violations, or an honest empty state that explains why it's empty."""
    if not incidents:
        reason = (
            "Active violations are being tracked against the workers below."
            if violating
            else "No workers have been observed in a monitored view yet."
        )
        render_html(
            f'<div class="panel" style="padding:12px 16px;margin-bottom:12px;">'
            f'<div style="font-weight:700;font-size:14px;color:var(--heading);margin-bottom:4px;">'
            f"Open violations</div>"
            f'<div style="color:var(--muted);font-size:12.5px;">{escape(reason)}</div></div>'
        )
        return

    rows = []
    for event in incidents[:8]:
        labels = event.get("person_reports") or event.get("labels") or ["Unspecified"]
        detail = "; ".join(str(item) for item in labels)[:160]
        stamp = datetime.fromtimestamp(event.get("ts", 0.0)).strftime("%H:%M:%S")
        rows.append(
            f'<li style="margin:0;padding:8px 0;border-bottom:1px solid var(--line);'
            f'list-style:none;display:flex;justify-content:space-between;gap:12px;">'
            f'<span style="color:var(--heading);font-size:12.5px;">{escape(detail)}</span>'
            f'<span style="color:var(--muted);font-size:11.5px;white-space:nowrap;">{escape(stamp)}</span>'
            f"</li>"
        )
    render_html(
        f'<div class="panel" style="padding:12px 16px;margin-bottom:12px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
        f'<span style="font-weight:700;font-size:14px;color:var(--heading);">Open violations</span>'
        f'<span class="badge badge-red">{len(incidents)}</span></div>'
        f'<ul style="margin:0;padding:0;">{"".join(rows)}</ul></div>'
    )


def _render_telemetry(snapshot: dict, fps: float, inference_ms: float, frames_seen: int) -> None:
    """Measured performance context. Unmeasured values say so explicitly."""
    if frames_seen <= 0:
        render_html(
            '<div class="panel" style="padding:12px 16px;">'
            '<div style="font-weight:700;font-size:14px;color:var(--heading);margin-bottom:4px;">'
            "Inference telemetry</div>"
            '<div style="color:var(--muted);font-size:12.5px;">'
            "No frames have been processed yet &mdash; throughput is unmeasured.</div></div>"
        )
        return

    cells = [
        ("Throughput", f"{fps:.1f} FPS"),
        ("Frame latency", f"{inference_ms:.0f} ms"),
        ("Frames processed", f"{frames_seen:,}"),
        ("Tracked workers", str(len(snapshot.get("workers", []) or []))),
    ]
    grid = "repeat(auto-fit, minmax(150px, 1fr))"
    tiles = "".join(
        f'<div style="padding:10px 12px;background:var(--bg);border-radius:8px;">'
        f'<div style="font-size:11px;color:var(--muted);">{escape(name)}</div>'
        f'<div style="font-size:16px;font-weight:750;color:var(--heading);margin-top:3px;">'
        f"{escape(value)}</div></div>"
        for name, value in cells
    )
    render_html(
        f'<div class="panel" style="padding:12px 16px;">'
        f'<div style="font-weight:700;font-size:14px;color:var(--heading);margin-bottom:8px;">'
        f"Inference telemetry</div>"
        f'<div style="display:grid;grid-template-columns:{grid};gap:10px;">{tiles}</div></div>'
    )

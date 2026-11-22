"""System Health — measured subsystem status for the operations workspace.

Every value rendered here is derived from observed runtime state via
:mod:`src.ui.status`. Nothing is assumed healthy by default: subsystems that
cannot be measured are reported as "Not measured" with a neutral badge, so an
operator is never shown a reassuring readout that no probe actually produced.
"""

from __future__ import annotations

from html import escape

from src.config.runtime import RuntimeConfig, load_runtime_config
from src.ui.app_context import AppContext
from src.ui.components import render_html, render_section_header
from src.ui.status import (
    DiskStatus,
    build_system_components,
    measure_disk,
    overall_status,
    render_component_rows,
)


def _read_disk(ctx: AppContext) -> DiskStatus:
    """Measure the evidence volume, falling back to the app data directory."""
    for candidate in (getattr(ctx.evidence, "storage_dir", None), getattr(ctx.evidence, "db_path", None)):
        if candidate is None:
            continue
        disk = measure_disk(candidate)
        if disk.used_bytes is not None:
            return disk
    return DiskStatus(None, None)


def _webhook_allowed(cfg: RuntimeConfig) -> bool:
    """True when the configured webhook passes the same host/path guard as delivery."""
    if not cfg.webhook_url or not cfg.webhook_allowlist:
        return False
    from src.alerts.webhooks import _is_allowed

    return _is_allowed(cfg.webhook_url, cfg.webhook_allowlist)


def collect_status(ctx: AppContext, cfg: RuntimeConfig | None = None) -> list:
    """Gather every subsystem reading from live runtime state."""
    cfg = cfg or load_runtime_config()
    state = ctx.state
    snapshot = state.snapshot_ui()
    return build_system_components(
        model_loaded=getattr(ctx, "model", None) is not None,
        load_error=ctx.load_error,
        model_name=getattr(ctx, "model_name", "") or "",
        camera_running=bool(getattr(ctx.camera_manager, "is_running", False)),
        device=str(getattr(ctx, "device", "") or ""),
        camera_error=snapshot.get("last_error", "") or "",
        frames_seen=int(snapshot.get("total_frames", 0) or 0),
        fps=float(getattr(ctx.pipeline, "smoothed_fps", 0.0) or 0.0),
        inference_ms=float(snapshot.get("inference_ms", 0.0) or 0.0),
        webhook_url=cfg.webhook_url,
        webhook_allowlist=cfg.webhook_allowlist,
        webhook_allowed=_webhook_allowed(cfg),
        snapshot_count=int(snapshot.get("snapshots_count", 0) or 0),
        max_snapshots=int(getattr(ctx.evidence, "max_snapshots", 0) or 0),
        evidence_sealed=bool(getattr(ctx.evidence, "sealed", False)),
        evidence_error=str(getattr(ctx.evidence, "last_error", "") or ""),
        disk=_read_disk(ctx),
    )


def render(ctx: AppContext) -> None:
    """Render the System Health page."""
    components = collect_status(ctx)
    verdict = overall_status(components)

    render_html(
        f"""
        <section class="ops-task-header">
            <div>
                <h1>System health</h1>
                <p>Live subsystem readings measured from this workspace. Unmeasured
                   subsystems are reported as &ldquo;Not measured&rdquo; rather than healthy.</p>
            </div>
            <span class="badge {verdict.badge_class}" role="status">{escape(verdict.label)}</span>
        </section>
        """
    )

    render_section_header("Measured components", "Each status below is sourced from observed runtime state.")

    import streamlit as st
    
    tab1, tab2, tab3 = st.tabs(["Overview", "Hardware Telemetry", "Subsystem Details"])
    
    with tab1:
        # Headline tiles mirror the measured components so the verdict is legible
        # before the operator reads the detail table.
        tiles = []
        for component in components:
            tiles.append(
                f'<div class="panel" style="padding:12px 14px;background:var(--bg);">'
                f'<div style="font-size:11px;color:var(--muted);font-weight:700;">{escape(component.name)}</div>'
                f'<div style="font-size:15px;font-weight:750;color:var(--heading);margin-top:4px;">'
                f"{escape(component.status.label)}</div>"
                f'<div style="font-size:11px;color:var(--muted);margin-top:4px;">'
                f"{escape(component.detail)}</div>"
                f"</div>"
            )
        columns = "repeat(auto-fit, minmax(210px, 1fr))"
        render_html(
            f'<div class="panel" style="padding:12px 14px;margin-bottom:12px;">'
            f'<div style="display:grid;grid-template-columns:{columns};gap:12px;">'
            f"{''.join(tiles)}</div></div>"
        )
        _render_runtime_facts(ctx)

    with tab2:
        _render_resource_telemetry(ctx)

    with tab3:
        # Detail table: every component with its measured reason.
        render_html(
            f"""
            <div class="panel" style="padding:12px 16px;margin-bottom:12px;">
                <div style="font-weight:700;font-size:14px;color:var(--heading);margin-bottom:6px;">
                    Subsystem detail
                </div>
                <table style="width:100%;border-collapse:collapse;font-size:12.5px;">
                    <caption class="sr-only">Measured status of each workspace subsystem</caption>
                    <thead>
                        <tr>
                            <th scope="col" style="text-align:left;padding:8px 10px;color:var(--muted);
                                font-size:11px;letter-spacing:.08em;text-transform:uppercase;">Subsystem</th>
                            <th scope="col" style="text-align:left;padding:8px 10px;color:var(--muted);
                                font-size:11px;letter-spacing:.08em;text-transform:uppercase;">Status</th>
                            <th scope="col" style="text-align:left;padding:8px 10px;color:var(--muted);
                                font-size:11px;letter-spacing:.08em;text-transform:uppercase;">Measured value</th>
                        </tr>
                    </thead>
                    <tbody>{render_component_rows(components)}</tbody>
                </table>
            </div>
            """
        )


def _render_resource_telemetry(ctx: AppContext) -> None:
    """Live host metrics (CPU, RAM, Disk) and available inference backends."""
    from src.observability.system_health import resource_usage
    from src.vision.backends import probe_backends

    usage = resource_usage()
    backends = [b.name for b in probe_backends()]

    cpu_val = usage.get("cpu_percent")
    cpu_str = f"{cpu_val}%" if cpu_val is not None else "N/A"
    ram_val = usage.get("ram_percent")
    ram_used = usage.get("ram_used_mb", 0)
    ram_str = f"{ram_val}% ({ram_used:,.0f} MB)" if ram_val is not None else "N/A"
    disk_free = usage.get("disk_free_gb")
    disk_pct = usage.get("disk_percent", 0)
    disk_str = f"{disk_free} GB free ({disk_pct}% used)" if disk_free is not None else "N/A"
    backends_str = ", ".join(backends) if backends else "CPU"

    render_html(
        f"""
        <div class="panel" style="padding:14px 18px;margin-bottom:12px;">
            <div style="font-weight:700;font-size:14px;color:var(--heading);margin-bottom:8px;">
                Hardware & Resource Telemetry
            </div>
            <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:12px;">
                <div style="padding:10px 12px;background:var(--bg);border-radius:6px;border:1px solid var(--line);">
                    <div style="font-size:11px;color:var(--muted);text-transform:uppercase;font-weight:700;">CPU Utilization</div>
                    <div style="font-size:18px;font-weight:750;color:var(--heading);margin-top:2px;">{escape(cpu_str)}</div>
                </div>
                <div style="padding:10px 12px;background:var(--bg);border-radius:6px;border:1px solid var(--line);">
                    <div style="font-size:11px;color:var(--muted);text-transform:uppercase;font-weight:700;">RAM Memory</div>
                    <div style="font-size:18px;font-weight:750;color:var(--heading);margin-top:2px;">{escape(ram_str)}</div>
                </div>
                <div style="padding:10px 12px;background:var(--bg);border-radius:6px;border:1px solid var(--line);">
                    <div style="font-size:11px;color:var(--muted);text-transform:uppercase;font-weight:700;">Disk Storage</div>
                    <div style="font-size:18px;font-weight:750;color:var(--heading);margin-top:2px;">{escape(disk_str)}</div>
                </div>
                <div style="padding:10px 12px;background:var(--bg);border-radius:6px;border:1px solid var(--line);">
                    <div style="font-size:11px;color:var(--muted);text-transform:uppercase;font-weight:700;">Inference Backends</div>
                    <div style="font-size:14px;font-weight:700;color:var(--heading);margin-top:4px;">{escape(backends_str)}</div>
                </div>
            </div>
        </div>
        """
    )


def _render_runtime_facts(ctx: AppContext) -> None:
    """Deployment facts that are known statically but must still be sourced."""
    from src.__version__ import __release_channel__, __version__

    cfg = load_runtime_config()
    snapshot = ctx.state.snapshot_ui()

    facts = [
        ("Version", f"{__version__} ({__release_channel__})"),
        ("Environment", cfg.environment),
        ("Compute device", str(getattr(ctx, "device", "") or "unknown")),
        ("Frames processed", f"{int(snapshot.get('total_frames', 0) or 0):,}"),
        ("Configured cameras", str(len(getattr(ctx, "devices", []) or []))),
        ("Sign-in gate", "Enabled" if cfg.is_auth_enabled else "Disabled"),
        ("Maintenance mode", "ON — writes paused" if cfg.maintenance_mode else "Off"),
    ]
    rows = "".join(
        f'<div style="display:flex;justify-content:space-between;gap:12px;padding:7px 0;'
        f'border-bottom:1px solid var(--line);">'
        f'<span style="color:var(--muted);font-size:12px;">{escape(name)}</span>'
        f'<strong style="color:var(--heading);font-size:12px;text-align:right;">{escape(value)}</strong>'
        f"</div>"
        for name, value in facts
    )
    render_html(
        f'<div class="panel" style="padding:12px 16px;">'
        f'<div style="font-weight:700;font-size:14px;color:var(--heading);margin-bottom:4px;">'
        f"Runtime facts</div>{rows}</div>"
    )


__all__ = ["collect_status", "render"]

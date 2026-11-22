"""Shared UI primitives: HTML rendering, page/sidebar chrome, and loading,
empty, and performance feedback states."""

from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st


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
    eyebrow: str = "WORKSPACE OPERATIONS",
    tag: str = "OPERATOR VIEW",
    action_label: str = "Private workspace",
) -> None:
    """Render a calm, truthful page header for shift-based safety work.

    The header deliberately avoids claiming that inference is active: review,
    settings, and evidence pages can be open while every camera is idle.
    """
    render_html(
        f"""
        <header class="page-heading">
            <div>
                <h1>{escape(title)}</h1>
                <p>{escape(subtitle)}</p>
            </div>
            <div class="heading-actions" aria-label="Workspace context">
                <div class="badge badge-slate" style="padding: 7px 14px; font-size: 11px; font-weight: 600;">
                    {escape(tag)}
                </div>
                <div class="badge badge-slate" style="padding: 7px 14px; font-size: 11px; font-weight: 600;">
                    {escape(action_label)}
                </div>
                <div class="badge badge-blue" style="padding: 7px 14px; font-size: 11px; font-weight: 600;">
                    <span class="status-dot neutral"></span> PPE DECISION SUPPORT
                </div>
            </div>
        </header>
        """
    )


def render_section_header(title: str, description: str = "", badge: str = "") -> None:
    """Render a consistent subsection heading without introducing visual noise."""
    badge_html = f'<span class="section-badge">{escape(badge)}</span>' if badge else ""
    description_html = f"<p>{escape(description)}</p>" if description else ""
    render_html(
        f"""
        <div class="workspace-section-header">
            <div><h2>{escape(title)}</h2>{description_html}</div>
            {badge_html}
        </div>
        """
    )


def render_workspace_context(
    *,
    status_label: str,
    status_class: str,
    model_name: str,
    device: str,
    capture_label: str,
    evidence_label: str,
) -> None:
    """Render the persistent operational context strip above each page.

    Operators should not have to visit System Health to know which checkpoint,
    compute device, capture mode, and evidence state they are looking at.
    Values are supplied by the runtime and escaped at this HTML boundary.
    """
    dot_class = {
        "badge-green": "",
        "badge-amber": "amber",
        "badge-red": "red",
        "badge-slate": "neutral",
    }.get(status_class, "neutral")
    render_html(
        f"""
        <aside class="safesight-context-strip" aria-label="Workspace context">
            <div class="safesight-context-status">
                <span class="status-dot {dot_class}"></span>
                <span class="safesight-context-label">Workspace</span>
                <strong class="badge {escape(status_class)}">{escape(status_label)}</strong>
            </div>
            <div class="safesight-context-items">
                <span class="safesight-context-item">
                    <span class="safesight-context-label">Checkpoint</span>
                    <strong title="{escape(model_name)}">{escape(model_name)}</strong>
                </span>
                <span class="safesight-context-item">
                    <span class="safesight-context-label">Compute</span>
                    <strong>{escape(device or "Unknown")}</strong>
                </span>
                <span class="safesight-context-item">
                    <span class="safesight-context-label">Capture</span>
                    <strong>{escape(capture_label)}</strong>
                </span>
                <span class="safesight-context-item">
                    <span class="safesight-context-label">Evidence</span>
                    <strong>{escape(evidence_label)}</strong>
                </span>
            </div>
        </aside>
        """
    )


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
                        SAFETY REVIEW WORKSPACE.
                    </small>
                </div>
            </div>
        </div>
        """
    )


def render_sidebar_system_card(
    device_label: str = "",
    model_name: str = "",
    *,
    status_label: str = "Workspace ready",
    status_class: str = "neutral",
    capture_label: str = "Capture standby",
) -> None:
    """Render measured runtime context at the bottom of the navigation rail."""
    safe_class = status_class if status_class in {"ready", "attention", "neutral"} else "neutral"
    render_html(
        f"""
        <section class="sidebar-system-card" aria-label="Workspace status">
            <div class="sidebar-system-card-top">
                <span class="status-dot {"amber" if safe_class == "attention" else ("neutral" if safe_class == "neutral" else "")}"></span>
                <span>Workspace status</span>
                <span class="ops-state {safe_class}" style="margin-left:auto;">{escape(status_label)}</span>
            </div>
            <div class="sidebar-system-card-sub">{escape(capture_label)}</div>
            <div class="sidebar-system-mini">
                <span>Compute</span><strong>{escape(device_label or "Unknown")}</strong>
            </div>
            <div class="sidebar-system-mini">
                <span>Checkpoint</span><strong title="{escape(model_name)}">{escape(model_name or "Unavailable")}</strong>
            </div>
        </section>
        """
    )


def render_sidebar_profile(role: str = "operator") -> None:
    """Render a non-identifying operator session marker.

    The UI must not invent a named employee when identity is not configured by
    the deployment, but it can show the effective permission role.
    """
    safe_role = escape(role.replace("_", " ").title()) if role else "Operator"
    render_html(
        f"""
        <div class="sidebar-profile" aria-label="Operator session">
            <div class="sidebar-avatar" aria-hidden="true">
                OP
                <span></span>
            </div>
            <div class="sidebar-profile-info">
                <strong>Operator session</strong>
                <small>{safe_role} access</small>
            </div>
        </div>
        """
    )


def render_skeleton_block(title: str = "Loading…", subtitle: str = "") -> None:
    """Render a themed skeleton placeholder while content is loading."""
    sub_html = (
        f'<p style="margin:4px 0 0;font-size:12px;color:var(--muted);">{escape(subtitle)}</p>' if subtitle else ""
    )
    render_html(
        f"""
        <div style="background:var(--panel);border:1px solid var(--line);border-radius:10px;
                    padding:32px 24px;text-align:center;margin:12px 0;">
            <div style="font-size:14px;font-weight:600;color:var(--secondary);">{escape(title)}</div>
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

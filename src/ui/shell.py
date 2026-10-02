"""Task-first application chrome for the SAFE SIGHT operations workspace."""

from __future__ import annotations

from html import escape

import streamlit as st


def _render_html(markup: str) -> None:
    content = " ".join(line.strip() for line in markup.splitlines() if line.strip())
    if hasattr(st, "html"):
        st.html(content)
    else:
        st.markdown(content, unsafe_allow_html=True)


def _mark() -> str:
    return """<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false"><path d="M16 3 27 7v8c0 7.2-4.6 11.6-11 14-6.4-2.4-11-6.8-11-14V7l11-4Z" fill="none" stroke="currentColor" stroke-width="2.2"/><path d="m11.2 16.3 3.1 3.1 6.7-7" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>"""


def render_sidebar_identity() -> None:
    """Render compact identity without invented customer information."""
    _render_html(
        f"""<div class="ops-sidebar-brand"><div class="ops-brand-mark">{_mark()}</div><div><strong>SAFE SIGHT</strong><span>SAFETY OPERATIONS</span></div></div><div class="ops-sidebar-context"><span class="ops-dot" aria-hidden="true"></span><span>Private deployment</span></div>"""
    )


def render_workspace_header(current_page: str, health_ok: bool, model_name: str) -> None:
    """Render concise contextual chrome shared by every operations page."""
    state = "System ready" if health_ok else "Model attention needed"
    status_class = "is-ready" if health_ok else "is-attention"
    _render_html(
        f"""<header class="ops-header"><div class="ops-header-title"><span>{escape(current_page)}</span><small>Safety operations workspace</small></div><div class="ops-header-meta"><span class="ops-model">{escape(model_name)}</span><span class="ops-health {status_class}" role="status"><i aria-hidden="true"></i>{state}</span></div></header>"""
    )


def render_task_header(title: str, subtitle: str, status: str | None = None) -> None:
    """Render a purpose-led page heading without decorative labels."""
    status_markup = f'<span class="ops-context-status">{escape(status)}</span>' if status else ""
    _render_html(
        f"""<section class="ops-task-header"><div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>{status_markup}</section>"""
    )


def render_observation_strip(
    detection_count: int, worker_count: int, violation_count: int, fps: float, inference_ms: float, source: str
) -> None:
    """Make camera state and inference freshness readable at a glance."""
    state = "Attention required" if violation_count else ("Observing" if worker_count else "Waiting for an observation")
    tone = "attention" if violation_count else ("ready" if worker_count else "neutral")
    _render_html(
        f"""<div class="ops-observation-strip"><div><span class="ops-state {tone}">{state}</span><span class="ops-observation-detail">{detection_count} detections · {worker_count} workers · {violation_count} active issues</span></div><div class="ops-observation-meta">{escape(source)} · {fps:.1f} FPS · {inference_ms:.0f} ms</div></div>"""
    )

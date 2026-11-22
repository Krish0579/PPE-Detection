"""SAFE SIGHT AI component library.

Re-exports the public component API from focused submodules so callers keep a
single stable import surface (``from src.ui.components import ...``) while the
implementation stays split by concern:

- :mod:`~src.ui.components.base` — HTML/chrome primitives and feedback states
- :mod:`~src.ui.components.dashboard` — KPI, compliance, zone and trend panels
- :mod:`~src.ui.components.workers` — worker cards, status table, floor plan
- :mod:`~src.ui.components.alerts` — alert consolidation and analytics
- :mod:`~src.ui.components.reports` — exports and the safety certificate
- :mod:`~src.ui.components.audio` — browser chime and playback bridge
"""

from __future__ import annotations

from src.ui.components.alerts import consolidate_person_alerts, render_alerts_view
from src.ui.components.analytics import render_productivity_view, render_safety_analytics_view
from src.ui.components.audio import play_violation_chime, render_audio_alert_script
from src.ui.components.base import (
    render_empty_state,
    render_html,
    render_page_header,
    render_perf_chip,
    render_section_header,
    render_sidebar_header,
    render_sidebar_profile,
    render_sidebar_system_card,
    render_skeleton_block,
    render_workspace_context,
)
from src.ui.components.dashboard import (
    render_compliance_panel,
    render_metrics_grid,
    render_recent_events_table,
    render_trend_chart_panel,
    render_zone_occupancy_panel,
)
from src.ui.components.reports import render_printable_safety_certificate, render_reports_view
from src.ui.components.workers import build_workers_status_dataframe, render_workers_grid

# Grouped by concern for readability. RUF022 (sort __all__) is disabled for
# src/ui/** in pyproject.toml so the grouping stays legible to maintainers.
__all__ = [
    # base
    "render_html",
    "render_page_header",
    "render_sidebar_header",
    "render_sidebar_system_card",
    "render_sidebar_profile",
    "render_section_header",
    "render_workspace_context",
    "render_skeleton_block",
    "render_empty_state",
    "render_perf_chip",
    # dashboard
    "render_metrics_grid",
    "render_compliance_panel",
    "render_zone_occupancy_panel",
    "render_trend_chart_panel",
    "render_recent_events_table",
    # workers
    "render_workers_grid",
    "build_workers_status_dataframe",
    # alerts
    "consolidate_person_alerts",
    "render_alerts_view",
    "render_safety_analytics_view",
    "render_productivity_view",
    # reports
    "render_reports_view",
    "render_printable_safety_certificate",
    # audio
    "play_violation_chime",
    "render_audio_alert_script",
]

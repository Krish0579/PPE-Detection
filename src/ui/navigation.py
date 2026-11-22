"""Navigation metadata for the browser workspace.

Keeping route names and labels in one module prevents the sidebar, tests, and
future navigation surfaces from drifting apart.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NavigationItem:
    """One user-facing route in the workspace."""

    key: str
    page: str
    label: str


NAVIGATION_ITEMS: tuple[NavigationItem, ...] = (
    NavigationItem(
        "Overview",
        "Command Center",
        "📊  Command Center",
    ),
    NavigationItem(
        "Live operations",
        "Live Feed",
        "📹  Live Feed",
    ),
    NavigationItem(
        "Incidents",
        "Incidents",
        "⚠️  Incidents & Compliance",
    ),
    NavigationItem(
        "Reports",
        "Reports",
        "📑  Reports & Shifts",
    ),
    NavigationItem(
        "Incident evidence",
        "Evidence Log",
        "📋  Evidence Log",
    ),
    NavigationItem(
        "Review footage",
        "Video File",
        "🎬  Video File",
    ),
    NavigationItem(
        "Analyze image",
        "Image Analysis",
        "🖼️  Image Analysis",
    ),
    NavigationItem(
        "System policy",
        "System Settings",
        "⚙️  System Settings",
    ),
    NavigationItem(
        "System health",
        "System Health",
        "🩺  System Health",
    ),
)

NAV_PAGES: dict[str, str] = {item.key: item.page for item in NAVIGATION_ITEMS}
NAV_LABELS: dict[str, str] = {item.key: item.label for item in NAVIGATION_ITEMS}

NAV_SECTIONS: tuple[tuple[str, tuple[NavigationItem, ...]], ...] = (
    (
        "Monitor",
        (
            NAVIGATION_ITEMS[0],
            NAVIGATION_ITEMS[1],
        ),
    ),
    (
        "Review",
        (
            NAVIGATION_ITEMS[2],
            NAVIGATION_ITEMS[3],
            NAVIGATION_ITEMS[4],
            NAVIGATION_ITEMS[5],
            NAVIGATION_ITEMS[6],
        ),
    ),
    (
        "Configure",
        (
            NAVIGATION_ITEMS[7],
            NAVIGATION_ITEMS[8],
        ),
    ),
)


def navigation_keys() -> list[str]:
    """Return the stable option order used by the Streamlit radio control."""

    return [item.key for item in NAVIGATION_ITEMS]

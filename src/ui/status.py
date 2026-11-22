"""Measured subsystem status for operator-facing pages.

Every status shown to an operator must be *derived from observed state*. This
module is the single source of truth for those readouts and contains no
default "OK" fallbacks: when a signal cannot be measured the component is
reported as ``unknown`` rather than assumed healthy.

Design rules:
- Pure functions of explicit inputs so they are trivially testable.
- ``Status.UNKNOWN`` is a first-class outcome, never collapsed into healthy.
- Unknown states render with a neutral (not green) tone so an operator can
  never mistake "not measured" for "healthy".

This exists because the previous Command Center / Camera Wall / System Health
pages printed hardcoded values (``Storage: OK``, ``Uptime: LIVE``,
``Webhooks: OK``). For an evidence-first safety product, a fabricated
"healthy" readout is a credibility and liability defect, not a cosmetic bug.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import Enum


class Status(str, Enum):
    """Health of one measured subsystem."""

    OK = "ok"
    ATTENTION = "attention"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {
            Status.OK: "Healthy",
            Status.ATTENTION: "Needs attention",
            Status.OFFLINE: "Offline",
            Status.UNKNOWN: "Not measured",
        }[self]

    @property
    def badge_class(self) -> str:
        """CSS badge class. UNKNOWN never maps to a green badge."""
        return {
            Status.OK: "badge-green",
            Status.ATTENTION: "badge-amber",
            Status.OFFLINE: "badge-red",
            Status.UNKNOWN: "badge-slate",
        }[self]


@dataclass(frozen=True)
class ComponentStatus:
    """A single named subsystem reading."""

    name: str
    status: Status
    detail: str

    @property
    def is_measured(self) -> bool:
        return self.status is not Status.UNKNOWN


@dataclass(frozen=True)
class DiskStatus:
    """Measured evidence-volume usage. ``None`` when it cannot be measured."""

    used_bytes: int | None
    total_bytes: int | None

    @property
    def used_gb(self) -> float | None:
        return None if self.used_bytes is None else self.used_bytes / (1024**3)

    @property
    def total_gb(self) -> float | None:
        return None if self.total_bytes is None else self.total_bytes / (1024**3)

    @property
    def used_pct(self) -> float | None:
        if not self.used_bytes or not self.total_bytes:
            return None
        return 100.0 * self.used_bytes / self.total_bytes

    @property
    def status(self) -> Status:
        pct = self.used_pct
        if pct is None:
            return Status.UNKNOWN
        if pct >= 95.0:
            return Status.OFFLINE
        if pct >= 85.0:
            return Status.ATTENTION
        return Status.OK

    @property
    def detail(self) -> str:
        used, total = self.used_gb, self.total_gb
        if used is None or total is None:
            return "Usage not measurable"
        return f"{used:.1f} GB of {total:.1f} GB used ({self.used_pct:.0f}%)"


def measure_disk(path) -> DiskStatus:
    """Measure real filesystem usage for ``path``.

    Returns an unmeasured :class:`DiskStatus` when the volume is unavailable
    (missing mount, permissions, non-local path) rather than guessing.
    """
    try:
        usage = shutil.disk_usage(str(path))
    except (OSError, ValueError):
        return DiskStatus(None, None)
    return DiskStatus(usage.used, usage.total)


def model_component(*, model_loaded: bool, load_error: str | None = None, model_name: str = "") -> ComponentStatus:
    """Status of the inference checkpoint.

    A load error is always reported verbatim — an operator must be able to see
    *why* the model is unavailable rather than a generic "failed".
    """
    label = model_name or "checkpoint"
    if load_error:
        return ComponentStatus("Model", Status.OFFLINE, f"Load failed: {load_error[:180]}")
    if not model_loaded:
        return ComponentStatus("Model", Status.UNKNOWN, f"{label} not loaded")
    return ComponentStatus("Model", Status.OK, f"{label} loaded")


def camera_component(*, is_running: bool, device: str = "", last_error: str = "") -> ComponentStatus:
    """Status of the active capture source.

    Not-running is reported as ``offline`` with the device named, because a
    supervisor needs to distinguish "no camera selected" from "camera failed".
    """
    if last_error:
        return ComponentStatus("Camera", Status.OFFLINE, f"Capture error: {last_error[:180]}")
    if is_running:
        return ComponentStatus("Camera", Status.OK, f"Streaming from {device}" if device else "Streaming")
    return ComponentStatus("Camera", Status.OFFLINE, f"No camera running{f' ({device})' if device else ''}")


def inference_component(
    *, frames_seen: int, fps: float, inference_ms: float, minimum_fps: float = 15.0
) -> ComponentStatus:
    """Status of the inference loop, derived from actually-processed frames.

    ``frames_seen == 0`` means no frame has ever been inferred, so throughput
    is unmeasured — not zero, and not healthy.
    """
    if frames_seen <= 0:
        return ComponentStatus("Inference", Status.UNKNOWN, "No frames processed yet")
    if fps < minimum_fps:
        return ComponentStatus(
            "Inference", Status.ATTENTION, f"{fps:.1f} FPS below {minimum_fps:.0f} FPS target ({inference_ms:.0f} ms)"
        )
    return ComponentStatus("Inference", Status.OK, f"{fps:.1f} FPS · {inference_ms:.0f} ms per frame")


def webhook_component(
    *, webhook_url: str, allowlist: tuple[str, ...] = (), configured_ok: bool = True
) -> ComponentStatus:
    """Status of outbound violation webhooks.

    A webhook with no allowlist is reported as attention, not OK: on an
    internet-exposed instance that is an open egress path.
    """
    if not webhook_url:
        return ComponentStatus("Webhooks", Status.UNKNOWN, "Not configured")
    if not allowlist:
        return ComponentStatus("Webhooks", Status.ATTENTION, "Enabled without an allowlist")
    if not configured_ok:
        return ComponentStatus("Webhooks", Status.ATTENTION, "URL is outside the allowlist")
    return ComponentStatus("Webhooks", Status.OK, f"Delivery enabled to {len(allowlist)} allowed host(s)")


def evidence_component(
    *, snapshot_count: int, max_snapshots: int, sealed: bool = False, last_error: str = ""
) -> ComponentStatus:
    """Status of the evidence store, including hash-chain seal state."""
    if sealed:
        return ComponentStatus("Evidence", Status.ATTENTION, "Store sealed for maintenance — writes refused")
    if last_error:
        return ComponentStatus("Evidence", Status.ATTENTION, f"Store error: {last_error[:180]}")
    limit = max(1, int(max_snapshots))
    used = 100.0 * int(snapshot_count) / limit
    if used >= 100.0:
        return ComponentStatus("Evidence", Status.ATTENTION, f"Retention full — {snapshot_count} of {limit} snapshots")
    if used >= 80.0:
        return ComponentStatus(
            "Evidence", Status.ATTENTION, f"{snapshot_count} of {limit} snapshots ({used:.0f}% of retention)"
        )
    return ComponentStatus("Evidence", Status.OK, f"{snapshot_count} of {limit} snapshots retained")


def overall_status(components: list[ComponentStatus]) -> Status:
    """Roll component statuses up into a single workspace verdict.

    Order of precedence: any offline -> offline; any attention -> attention;
    any unmeasured (or nothing measured) -> unknown (we will not claim health
    we have not proven); otherwise ok.
    """
    if any(c.status is Status.OFFLINE for c in components):
        return Status.OFFLINE
    if any(c.status is Status.ATTENTION for c in components):
        return Status.ATTENTION
    if any(c.status is Status.UNKNOWN for c in components):
        return Status.UNKNOWN
    # No components measured at all is not evidence of health.
    return Status.UNKNOWN if not components else Status.OK


def build_system_components(
    *,
    model_loaded: bool,
    load_error: str | None,
    model_name: str,
    camera_running: bool,
    device: str,
    camera_error: str,
    frames_seen: int,
    fps: float,
    inference_ms: float,
    webhook_url: str,
    webhook_allowlist: tuple[str, ...],
    webhook_allowed: bool,
    snapshot_count: int,
    max_snapshots: int,
    evidence_sealed: bool,
    evidence_error: str,
    disk: DiskStatus,
) -> list[ComponentStatus]:
    """Assemble every measured component in display order."""
    return [
        model_component(model_loaded=model_loaded, load_error=load_error, model_name=model_name),
        camera_component(is_running=camera_running, device=device, last_error=camera_error),
        inference_component(frames_seen=frames_seen, fps=fps, inference_ms=inference_ms),
        evidence_component(
            snapshot_count=snapshot_count,
            max_snapshots=max_snapshots,
            sealed=evidence_sealed,
            last_error=evidence_error,
        ),
        webhook_component(webhook_url=webhook_url, allowlist=webhook_allowlist, configured_ok=webhook_allowed),
        ComponentStatus("Storage", disk.status, disk.detail),
    ]


def render_component_rows(components: list[ComponentStatus]) -> str:
    """Render component rows as themed HTML.

    Uses ``badge-slate`` for unknown states so an unmeasured subsystem is
    visually distinct from a measured-healthy one, and always shows the
    measured detail text rather than a bare label.
    """
    from html import escape

    rows = []
    for component in components:
        rows.append(
            f"<tr>"
            f'<td style="padding:9px 10px;border-bottom:1px solid var(--line);'
            f'font-weight:700;color:var(--heading);">{escape(component.name)}</td>'
            f'<td style="padding:9px 10px;border-bottom:1px solid var(--line);">'
            f'<span class="badge {component.status.badge_class}">{escape(component.status.label)}</span></td>'
            f'<td style="padding:9px 10px;border-bottom:1px solid var(--line);color:var(--muted);">'
            f"{escape(component.detail)}</td>"
            f"</tr>"
        )
    return "".join(rows)

"""System health snapshot for the System Health view (blueprint §13).

Distinguishes *application* health, *dependency* health (database, model,
notification queue) and *camera* health. Resource probes degrade gracefully
when psutil / torch are unavailable.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    category: str  # application | dependency | camera
    status: HealthStatus
    detail: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


def resource_usage(disk_path: str | Path = ".") -> dict[str, Any]:
    usage: dict[str, Any] = {}
    try:
        import psutil

        usage["cpu_percent"] = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        usage["ram_percent"] = mem.percent
        usage["ram_used_mb"] = round(mem.used / 1_048_576, 1)
    except Exception:
        usage["cpu_percent"] = None
        usage["ram_percent"] = None
    try:
        disk = shutil.disk_usage(str(disk_path))
        usage["disk_free_gb"] = round(disk.free / 1_073_741_824, 2)
        usage["disk_percent"] = round(100.0 * disk.used / disk.total, 1) if disk.total else None
    except OSError:
        usage["disk_free_gb"] = None
        usage["disk_percent"] = None
    usage.update(_gpu_usage())
    return usage


def _gpu_usage() -> dict[str, Any]:
    try:
        import importlib.util

        if importlib.util.find_spec("torch") is None:
            return {"gpu": None}
        import torch

        if torch.cuda.is_available():
            idx = torch.cuda.current_device()
            total = torch.cuda.get_device_properties(idx).total_memory
            used = torch.cuda.memory_allocated(idx)
            return {
                "gpu": torch.cuda.get_device_name(idx),
                "vram_used_mb": round(used / 1_048_576, 1),
                "vram_percent": round(100.0 * used / total, 1) if total else None,
            }
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            return {"gpu": "Apple Silicon (MPS)"}
    except Exception:
        import logging as _log

        _log.getLogger(__name__).debug("GPU probe failed", exc_info=True)
    return {"gpu": None}


def check(name: str, category: str, probe: Callable[[], bool], detail_on_fail: str = "") -> ComponentHealth:
    try:
        ok = bool(probe())
    except Exception as exc:
        return ComponentHealth(name, category, HealthStatus.DOWN, f"{type(exc).__name__}: {exc}"[:200])
    return ComponentHealth(name, category, HealthStatus.OK if ok else HealthStatus.DOWN, "" if ok else detail_on_fail)


def disk_health(path: str | Path = ".", min_free_gb: float = 2.0) -> ComponentHealth:
    try:
        free_gb = shutil.disk_usage(str(path)).free / 1_073_741_824
    except OSError as exc:
        return ComponentHealth("disk", "dependency", HealthStatus.DOWN, str(exc)[:200])
    status = HealthStatus.OK if free_gb >= min_free_gb else HealthStatus.DEGRADED
    detail = "" if status == HealthStatus.OK else f"low disk space: {free_gb:.2f} GB free"
    return ComponentHealth("disk", "dependency", status, detail, {"free_gb": round(free_gb, 2)})


def summarize(components: Iterable[ComponentHealth]) -> dict[str, Any]:
    items = list(components)
    by_category: dict[str, str] = {}
    for category in ("application", "dependency", "camera"):
        statuses = [c.status for c in items if c.category == category]
        if not statuses:
            continue
        if HealthStatus.DOWN in statuses:
            # A single down camera degrades the system; a down dependency/app is down.
            by_category[category] = (
                HealthStatus.DEGRADED.value
                if category == "camera" and HealthStatus.OK in statuses
                else HealthStatus.DOWN.value
            )
        elif HealthStatus.DEGRADED in statuses:
            by_category[category] = HealthStatus.DEGRADED.value
        else:
            by_category[category] = HealthStatus.OK.value
    values = set(by_category.values())
    overall = (
        HealthStatus.DOWN.value
        if by_category.get("application") == "down" or by_category.get("dependency") == "down"
        else HealthStatus.DEGRADED.value
        if values - {"ok"}
        else HealthStatus.OK.value
    )
    return {
        "status": overall,
        "categories": by_category,
        "components": [{**asdict(c), "status": c.status.value} for c in items],
    }

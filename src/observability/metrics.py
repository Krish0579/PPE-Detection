"""Dependency-free metrics registry with Prometheus text exposition (blueprint §13)."""

from __future__ import annotations

import math
import re
import threading
from collections import deque

_NAME_RE = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")


def _label_str(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    parts = []
    for key in sorted(labels):
        value = str(labels[key]).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
        parts.append(f'{key}="{value}"')
    return "{" + ",".join(parts) + "}"


class MetricsRegistry:
    def __init__(self, latency_window: int = 1024) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._samples: dict[str, deque[float]] = {}
        self._help: dict[str, tuple[str, str]] = {}
        self._window = latency_window

    @staticmethod
    def _check(name: str) -> None:
        if not _NAME_RE.match(name):
            raise ValueError(f"invalid metric name: {name!r}")

    def inc(self, name: str, value: float = 1.0, help_text: str = "", **labels: str) -> None:
        self._check(name)
        if value < 0:
            raise ValueError("counters can only increase")
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + value
            self._help.setdefault(name, ("counter", help_text))

    def set(self, name: str, value: float, help_text: str = "", **labels: str) -> None:
        self._check(name)
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._gauges[key] = float(value)
            self._help.setdefault(name, ("gauge", help_text))

    def observe(self, name: str, value: float) -> None:
        """Record a latency-style sample kept in a bounded window for percentile queries."""
        self._check(name)
        with self._lock:
            self._samples.setdefault(name, deque(maxlen=self._window)).append(float(value))

    def percentile(self, name: str, pct: float) -> float | None:
        with self._lock:
            data = sorted(self._samples.get(name, ()))
        if not data:
            return None
        rank = max(0, min(len(data) - 1, math.ceil(pct / 100.0 * len(data)) - 1))
        return data[rank]

    def counter(self, name: str, **labels: str) -> float:
        with self._lock:
            return self._counters.get((name, tuple(sorted(labels.items()))), 0.0)

    def gauge(self, name: str, **labels: str) -> float | None:
        with self._lock:
            return self._gauges.get((name, tuple(sorted(labels.items()))))

    def exposition(self) -> str:
        lines: list[str] = []
        with self._lock:
            series: dict[str, list[str]] = {}
            for (name, labels), value in [*self._counters.items(), *self._gauges.items()]:
                series.setdefault(name, []).append(f"{name}{_label_str(dict(labels))} {value:g}")
            for name, samples in self._samples.items():
                data = sorted(samples)
                if not data:
                    continue
                for q in (0.5, 0.95, 0.99):
                    idx = max(0, min(len(data) - 1, math.ceil(q * len(data)) - 1))
                    series.setdefault(name, []).append(f'{name}{{quantile="{q}"}} {data[idx]:g}')
                series[name].append(f"{name}_count {len(data)}")
                self._help.setdefault(name, ("summary", ""))
            for name in sorted(series):
                kind, text = self._help.get(name, ("untyped", ""))
                if text:
                    lines.append(f"# HELP {name} {text}")
                lines.append(f"# TYPE {name} {kind}")
                lines.extend(sorted(series[name]))
        return "\n".join(lines) + "\n"


REGISTRY = MetricsRegistry()

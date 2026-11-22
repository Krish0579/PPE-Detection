"""Tests for observability: metrics registry and system health."""

from __future__ import annotations

from src.observability.metrics import MetricsRegistry
from src.observability.system_health import (
    ComponentHealth,
    HealthStatus,
    check,
    disk_health,
    resource_usage,
    summarize,
)

# --- MetricsRegistry ---


class TestMetricsRegistry:
    def test_inc_and_counter(self):
        reg = MetricsRegistry()
        reg.inc("errors_total", help_text="Total errors")
        reg.inc("errors_total", 2.0)
        assert reg.counter("errors_total") == 3.0

    def test_set_and_gauge(self):
        reg = MetricsRegistry()
        reg.set("active_users", 5, help_text="Current users")
        assert reg.gauge("active_users") == 5.0
        reg.set("active_users", 3)
        assert reg.gauge("active_users") == 3.0

    def test_observe_and_percentile(self):
        reg = MetricsRegistry()
        for v in [0.1, 0.5, 1.0, 2.0, 5.0]:
            reg.observe("latency_ms", v)
        p50 = reg.percentile("latency_ms", 50)
        p95 = reg.percentile("latency_ms", 95)
        assert p50 is not None
        assert p95 is not None
        assert p95 >= p50

    def test_percentile_empty(self):
        reg = MetricsRegistry()
        assert reg.percentile("missing", 50) is None

    def test_exposition_format(self):
        reg = MetricsRegistry()
        reg.inc("requests_total", help_text="Total requests")
        reg.set("queue_depth", 4)
        text = reg.exposition()
        assert "# TYPE requests_total counter" in text
        assert "# TYPE queue_depth gauge" in text
        assert "requests_total 1" in text

    def test_labels(self):
        reg = MetricsRegistry()
        reg.inc("http_requests", 1, camera="CAM-01")
        reg.inc("http_requests", 1, camera="CAM-02")
        assert reg.counter("http_requests", camera="CAM-01") == 1.0
        assert reg.counter("http_requests", camera="CAM-02") == 1.0

    def test_negative_inc_raises(self):
        reg = MetricsRegistry()
        import pytest

        with pytest.raises(ValueError):
            reg.inc("bad", -1)


# --- System health ---


class TestResourceUsage:
    def test_returns_dict_with_keys(self):
        usage = resource_usage()
        assert isinstance(usage, dict)
        assert "cpu_percent" in usage
        assert "ram_percent" in usage
        assert "disk_free_gb" in usage
        assert "gpu" in usage


class TestCheck:
    def test_passing_probe(self):
        result = check("test", "application", lambda: True)
        assert result.status == HealthStatus.OK

    def test_failing_probe(self):
        result = check("test", "application", lambda: False, "it failed")
        assert result.status == HealthStatus.DOWN
        assert "it failed" in result.detail

    def test_exception_probe(self):
        def _boom():
            raise RuntimeError("boom")

        result = check("test", "application", _boom)
        assert result.status == HealthStatus.DOWN
        assert "RuntimeError" in result.detail


class TestDiskHealth:
    def test_returns_component_health(self):
        result = disk_health()
        assert isinstance(result, ComponentHealth)
        assert result.category == "dependency"
        assert result.status in (HealthStatus.OK, HealthStatus.DEGRADED, HealthStatus.DOWN)


class TestSummarize:
    def test_all_ok(self):
        components = [
            ComponentHealth("app", "application", HealthStatus.OK),
            ComponentHealth("db", "dependency", HealthStatus.OK),
        ]
        result = summarize(components)
        assert result["status"] == "ok"

    def test_degraded_dependency(self):
        components = [
            ComponentHealth("app", "application", HealthStatus.OK),
            ComponentHealth("disk", "dependency", HealthStatus.DEGRADED),
        ]
        result = summarize(components)
        assert result["status"] == "degraded"

    def test_down_camera_degrades(self):
        components = [
            ComponentHealth("app", "application", HealthStatus.OK),
            ComponentHealth("cam1", "camera", HealthStatus.OK),
            ComponentHealth("cam2", "camera", HealthStatus.DOWN),
        ]
        result = summarize(components)
        assert result["categories"]["camera"] == "degraded"
        assert result["status"] == "degraded"

    def test_down_application_is_down(self):
        components = [
            ComponentHealth("app", "application", HealthStatus.DOWN),
        ]
        result = summarize(components)
        assert result["status"] == "down"

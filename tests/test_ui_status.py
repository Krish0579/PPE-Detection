"""Tests for the operator-facing status layer.

The contract these tests protect: a subsystem that was not measured must never
be reported as healthy. Hardcoded "OK"/"LIVE" readouts were a defect in the
Command Center, Camera Wall, and System Health pages, so the guarantee is
locked in here rather than left to review.
"""

from __future__ import annotations

import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

from src.ui.components.dashboard import render_compliance_panel, render_metrics_grid
from src.ui.status import (
    ComponentStatus,
    DiskStatus,
    Status,
    build_system_components,
    camera_component,
    evidence_component,
    inference_component,
    measure_disk,
    model_component,
    overall_status,
    render_component_rows,
    webhook_component,
)

PAGE_DIR = Path(__file__).resolve().parent.parent / "src" / "ui" / "pages"


def _patched(captured: list[str]) -> ExitStack:
    """Capture the HTML a component renders instead of sending it to Streamlit.

    Each component module imports ``render_html`` into its own namespace, so
    every one of them has to be redirected for the capture to see anything.
    """
    from src.ui.components import alerts, analytics, base, dashboard

    stack = ExitStack()

    def _fake(html: str) -> None:
        captured.append(str(html))

    for module in (base, dashboard, alerts, analytics):
        if hasattr(module, "render_html"):
            stack.enter_context(_patch_attr(module, "render_html", _fake))
    return stack


class _patch_attr:
    """Minimal context manager that temporarily replaces one module attribute."""

    def __init__(self, module: object, name: str, value: object) -> None:
        self.module, self.name, self.value = module, name, value

    def __enter__(self) -> None:
        self._original = getattr(self.module, self.name)
        setattr(self.module, self.name, self.value)

    def __exit__(self, *exc: object) -> None:
        setattr(self.module, self.name, self._original)


class TestStatusVocabulary(unittest.TestCase):
    def test_unknown_never_uses_a_healthy_badge(self) -> None:
        """A neutral badge is what stops 'not measured' reading as 'healthy'."""
        for status in Status:
            with self.subTest(status=status):
                if status is Status.UNKNOWN:
                    self.assertNotEqual(status.badge_class, "badge-green")
                self.assertTrue(status.label)

    def test_labels_are_distinct(self) -> None:
        labels = {status.label for status in Status}
        self.assertEqual(len(labels), len(Status))

    def test_component_reports_measured_state(self) -> None:
        measured = ComponentStatus("Model", Status.OK, "loaded")
        self.assertTrue(measured.is_measured)
        self.assertFalse(ComponentStatus("Webhooks", Status.UNKNOWN, "n/a").is_measured)


class TestDiskStatus(unittest.TestCase):
    def test_unmeasurable_disk_is_unknown_not_ok(self) -> None:
        disk = DiskStatus(None, None)
        self.assertIs(disk.status, Status.UNKNOWN)
        self.assertIsNone(disk.used_pct)
        self.assertIn("not measurable", disk.detail.lower())

    def test_measures_real_filesystem(self) -> None:
        with TemporaryDirectory() as tmp:
            disk = measure_disk(tmp)
        self.assertIsNotNone(disk.used_bytes)
        self.assertIsNotNone(disk.total_bytes)
        self.assertGreater(disk.total_gb or 0.0, 0.0)

    def test_missing_path_is_unmeasured(self) -> None:
        disk = measure_disk("/definitely/not/a/real/path")
        self.assertIsNone(disk.used_bytes)
        self.assertIs(disk.status, Status.UNKNOWN)

    def test_thresholds_map_to_status(self) -> None:
        total = 100 * 1024**3
        cases = [(50, Status.OK), (90, Status.ATTENTION), (99, Status.OFFLINE)]
        for pct, expected in cases:
            with self.subTest(pct=pct):
                disk = DiskStatus(int(total * pct / 100), total)
                self.assertIs(disk.status, expected)


class TestComponentReadings(unittest.TestCase):
    def test_model_load_error_is_surfaced_verbatim(self) -> None:
        """An operator must see why the model failed, not a generic 'failed'."""
        component = model_component(model_loaded=False, load_error="CUDA out of memory", model_name="best.pt")
        self.assertIs(component.status, Status.OFFLINE)
        self.assertIn("CUDA out of memory", component.detail)

    def test_model_loaded_is_ok(self) -> None:
        component = model_component(model_loaded=True, model_name="best.pt")
        self.assertIs(component.status, Status.OK)
        self.assertIn("best.pt", component.detail)

    def test_camera_not_running_is_offline_not_unknown(self) -> None:
        component = camera_component(is_running=False, device="usb:0")
        self.assertIs(component.status, Status.OFFLINE)
        self.assertIn("usb:0", component.detail)

    def test_camera_error_wins_over_running_flag(self) -> None:
        component = camera_component(is_running=True, device="usb:0", last_error="device busy")
        self.assertIs(component.status, Status.OFFLINE)
        self.assertIn("device busy", component.detail)

    def test_no_frames_means_unmeasured_throughput(self) -> None:
        """0 FPS because nothing ran is not the same as 0 FPS from a stall."""
        component = inference_component(frames_seen=0, fps=0.0, inference_ms=0.0)
        self.assertIs(component.status, Status.UNKNOWN)
        self.assertIn("No frames processed", component.detail)

    def test_low_throughput_is_attention(self) -> None:
        component = inference_component(frames_seen=100, fps=4.0, inference_ms=250.0)
        self.assertIs(component.status, Status.ATTENTION)
        self.assertIn("below", component.detail)

    def test_healthy_throughput_is_ok(self) -> None:
        component = inference_component(frames_seen=100, fps=30.0, inference_ms=33.0)
        self.assertIs(component.status, Status.OK)

    def test_webhook_without_allowlist_is_attention(self) -> None:
        """On an internet-exposed node an allowlist-less webhook is open egress."""
        component = webhook_component(webhook_url="https://hooks.example.com/x", allowlist=())
        self.assertIs(component.status, Status.ATTENTION)

    def test_webhook_outside_allowlist_is_attention(self) -> None:
        component = webhook_component(
            webhook_url="https://evil.example.net/x",
            allowlist=("hooks.example.com",),
            configured_ok=False,
        )
        self.assertIs(component.status, Status.ATTENTION)
        self.assertIn("allowlist", component.detail)

    def test_unconfigured_webhook_is_unknown(self) -> None:
        self.assertIs(webhook_component(webhook_url="").status, Status.UNKNOWN)

    def test_sealed_evidence_store_is_attention(self) -> None:
        component = evidence_component(snapshot_count=0, max_snapshots=50, sealed=True)
        self.assertIs(component.status, Status.ATTENTION)
        self.assertIn("sealed", component.detail)

    def test_retention_pressure_is_attention(self) -> None:
        component = evidence_component(snapshot_count=49, max_snapshots=50)
        self.assertIs(component.status, Status.ATTENTION)

    def test_healthy_evidence_store_is_ok(self) -> None:
        self.assertIs(evidence_component(snapshot_count=3, max_snapshots=50).status, Status.OK)


class TestOverallRollup(unittest.TestCase):
    @staticmethod
    def _components(*statuses: Status) -> list[ComponentStatus]:
        return [ComponentStatus(f"c{i}", status, "detail") for i, status in enumerate(statuses)]

    def test_all_ok(self) -> None:
        self.assertIs(overall_status(self._components(Status.OK, Status.OK)), Status.OK)

    def test_offline_dominates(self) -> None:
        self.assertIs(overall_status(self._components(Status.OK, Status.OFFLINE)), Status.OFFLINE)

    def test_attention_beats_unknown(self) -> None:
        self.assertIs(overall_status(self._components(Status.UNKNOWN, Status.ATTENTION)), Status.ATTENTION)

    def test_unmeasured_blocks_a_healthy_verdict(self) -> None:
        """The core guarantee: no proof of health means no claim of health."""
        self.assertIs(overall_status(self._components(Status.OK, Status.UNKNOWN)), Status.UNKNOWN)

    def test_empty_is_unknown(self) -> None:
        self.assertIs(overall_status([]), Status.UNKNOWN)


class TestRendering(unittest.TestCase):
    def test_rows_include_name_status_and_detail(self) -> None:
        html = render_component_rows([ComponentStatus("Camera", Status.OFFLINE, "No camera running")])
        self.assertIn("Camera", html)
        self.assertIn("Offline", html)
        self.assertIn("No camera running", html)

    def test_rows_escape_untrusted_detail(self) -> None:
        html = render_component_rows([ComponentStatus("<script>", Status.OK, "<img onerror=x>")])
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)

    def test_unknown_row_is_not_green(self) -> None:
        html = render_component_rows([ComponentStatus("Webhooks", Status.UNKNOWN, "Not configured")])
        self.assertIn("badge-slate", html)
        self.assertNotIn("badge-green", html)


class TestSystemAssembly(unittest.TestCase):
    def test_builds_all_six_subsystems(self) -> None:
        components = build_system_components(
            model_loaded=True,
            load_error=None,
            model_name="best.pt",
            camera_running=True,
            device="cuda:0",
            camera_error="",
            frames_seen=500,
            fps=28.0,
            inference_ms=35.0,
            webhook_url="",
            webhook_allowlist=(),
            webhook_allowed=False,
            snapshot_count=4,
            max_snapshots=50,
            evidence_sealed=False,
            evidence_error="",
            disk=DiskStatus(1, 10),
        )
        self.assertEqual(
            [c.name for c in components],
            ["Model", "Camera", "Inference", "Evidence", "Webhooks", "Storage"],
        )

    def test_idle_workspace_does_not_claim_healthy(self) -> None:
        """A freshly started workspace must not report an all-green verdict."""
        components = build_system_components(
            model_loaded=False,
            load_error=None,
            model_name="",
            camera_running=False,
            device="cpu",
            camera_error="",
            frames_seen=0,
            fps=0.0,
            inference_ms=0.0,
            webhook_url="",
            webhook_allowlist=(),
            webhook_allowed=False,
            snapshot_count=0,
            max_snapshots=50,
            evidence_sealed=False,
            evidence_error="",
            disk=DiskStatus(None, None),
        )
        self.assertIsNot(overall_status(components), Status.OK)

    def test_healthy_workspace_is_ok(self) -> None:
        components = build_system_components(
            model_loaded=True,
            load_error=None,
            model_name="best.pt",
            camera_running=True,
            device="cuda:0",
            camera_error="",
            frames_seen=500,
            fps=28.0,
            inference_ms=35.0,
            webhook_url="https://hooks.example.com/x",
            webhook_allowlist=("hooks.example.com",),
            webhook_allowed=True,
            snapshot_count=4,
            max_snapshots=50,
            evidence_sealed=False,
            evidence_error="",
            disk=DiskStatus(1, 10),
        )
        self.assertIs(overall_status(components), Status.OK)


class TestEmptyPopulationIsNotAScore(unittest.TestCase):
    """An empty population is 'not measured', never 0% or 100% compliance.

    The pages previously computed ``100.0 if total == 0 else ...``, so an idle
    workspace claimed perfect safety while observing nobody, and the Command
    Center rendered ``0.0%`` which reads as total non-compliance.
    """

    def test_metrics_grid_omits_score_when_unmeasured(self) -> None:
        captured: list[str] = []
        with _patched(captured):
            render_metrics_grid(total_workers=0, safe_workers=0, violations=0, safety_score=None)
        markup = "".join(captured)
        self.assertIn("No observations", markup)
        self.assertNotIn("0.0", markup)

    def test_metrics_grid_shows_score_when_observed(self) -> None:
        captured: list[str] = []
        with _patched(captured):
            render_metrics_grid(total_workers=4, safe_workers=3, violations=1, safety_score=75.0)
        markup = "".join(captured)
        self.assertIn("75.0", markup)
        self.assertNotIn("No observations", markup)

    def test_compliance_panel_survives_unmeasured_score(self) -> None:
        """The donut formats the score, so None must not raise TypeError."""
        captured: list[str] = []
        with _patched(captured):
            render_compliance_panel({}, None, total_tracked=0, workers=[])
        self.assertIn("Not measured", "".join(captured))

    def test_pages_do_not_score_an_empty_population(self) -> None:
        for name in ("live_feed.py", "video_file.py", "image_analysis.py"):
            source = (PAGE_DIR / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                self.assertNotIn("= 100.0 if ", source)

    def test_compliance_panel_does_not_claim_ready_when_idle(self) -> None:
        """No workers must not render 'Ready · 100%' for every PPE item."""
        captured: list[str] = []
        with _patched(captured):
            render_compliance_panel({}, None, total_tracked=0, workers=[])
        markup = "".join(captured)

        self.assertNotIn("Ready · 100%", markup)
        self.assertIn("Not measured", markup)

    def test_compliance_panel_reports_observed_noncompliance(self) -> None:
        """A measured score must still render, not be suppressed as unknown."""
        captured: list[str] = []
        with _patched(captured):
            render_compliance_panel({"helmet": 1}, 50.0, total_tracked=1, workers=[])
        markup = "".join(captured)

        # The score renders as "50" with the percent sign in a nested tag.
        self.assertIn("Overall score", markup)
        self.assertIn(">50<", markup)
        self.assertNotIn("Ready · 100%", markup)


class TestNoFabricatedReadouts(unittest.TestCase):
    """Regression guard on the literal strings the old pages hardcoded."""

    def test_pages_do_not_hardcode_healthy_status_literals(self) -> None:
        for name in ("command_center.py", "camera_wall.py", "system_health.py"):
            source = (PAGE_DIR / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                for literal in ("Storage: OK", "Uptime: LIVE", "Webhooks: OK", "Status: LIVE"):
                    self.assertNotIn(literal, source)

    def test_pages_source_status_from_the_status_module(self) -> None:
        for name in ("command_center.py", "camera_wall.py", "system_health.py"):
            source = (PAGE_DIR / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                self.assertIn("src.ui.status", source)


if __name__ == "__main__":
    unittest.main()

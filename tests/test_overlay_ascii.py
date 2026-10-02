"""Regression: OpenCV ``putText`` renders ASCII only — HUD/badge/demo text must be ASCII.

Covers the ``Worker #01 ?? VIOLATION`` / ``YOLO PPE ?? N personnel`` /
``STANDARD ZONE ?? CAPACITY`` glitches caused by U+00B7 middle dots, plus the
SIM/LIVE HUD badge honesty flag.
"""

import cv2
import numpy as np
import pytest

from src.core.ppe_associator import WorkerStatus
from src.video.demo_feed import DemoShopfloorFeed
from src.video.renderer import get_default_renderer


@pytest.fixture()
def puttext_spy(monkeypatch):
    """Capture every string handed to cv2.putText."""
    texts: list[str] = []
    real_put = cv2.putText

    def spy(img, text, *args, **kwargs):
        texts.append(text)
        return real_put(img, text, *args, **kwargs)

    monkeypatch.setattr(cv2, "putText", spy)
    return texts


def _assert_ascii(texts: list[str]) -> None:
    assert texts, "expected cv2.putText to be called"
    for t in texts:
        assert all(ord(ch) < 128 for ch in t), f"non-ASCII text reaches putText: {t!r}"
        assert "??" not in t, f"unrenderable placeholder in text: {t!r}"


def test_hud_and_worker_badges_are_ascii(puttext_spy):
    renderer = get_default_renderer()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    worker = WorkerStatus(worker_id=1, box=(100, 100, 300, 600))
    renderer.draw_worker_badges(frame, [worker])
    renderer.draw_telemetry_hud(frame, fps=12.3, violations_count=1, workers_count=1, inference_ms=20.0, simulated=True)
    _assert_ascii(puttext_spy)


def test_simulated_hud_shows_sim_badge_not_live(puttext_spy):
    renderer = get_default_renderer()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    renderer.draw_telemetry_hud(frame, fps=10.0, violations_count=0, workers_count=2, inference_ms=15.0, simulated=True)
    assert "SIM" in puttext_spy
    assert "LIVE" not in puttext_spy


def test_hardware_hud_shows_live_badge(puttext_spy):
    renderer = get_default_renderer()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    renderer.draw_telemetry_hud(
        frame, fps=10.0, violations_count=0, workers_count=2, inference_ms=15.0, simulated=False
    )
    assert "LIVE" in puttext_spy


def test_render_8k_canvas_passes_simulated_flag(puttext_spy):
    renderer = get_default_renderer()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    renderer.render_8k_clarity_canvas(
        frame,
        workers=[],
        show_hud=True,
        fps=10.0,
        violations_count=0,
        inference_ms=15.0,
        simulated=True,
    )
    assert "SIM" in puttext_spy


def test_demo_feed_background_is_ascii(puttext_spy):
    feed = DemoShopfloorFeed(width=640, height=360)
    feed.get_frame()
    _assert_ascii(puttext_spy)

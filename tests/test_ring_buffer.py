"""Tests for the bounded frame ring buffer."""

from __future__ import annotations

import time

from src.video.ring_buffer import FrameRingBuffer


class TestFrameRingBuffer:
    def test_push_pop_latest_returns_newest(self):
        buf = FrameRingBuffer(capacity=4, max_age_sec=5.0)
        now = time.monotonic()
        buf.push("a", captured_at=now)
        buf.push("b", captured_at=now + 0.01)
        frame = buf.pop_latest(now=now + 0.02)
        assert frame is not None
        assert frame.data == "b"

    def test_pop_latest_clears_backlog(self):
        buf = FrameRingBuffer(capacity=4, max_age_sec=5.0)
        now = time.monotonic()
        buf.push("a", captured_at=now)
        buf.push("b", captured_at=now + 0.01)
        buf.pop_latest(now=now + 0.02)
        assert buf.depth == 0

    def test_overflow_drops_counted(self):
        buf = FrameRingBuffer(capacity=2, max_age_sec=5.0)
        now = time.monotonic()
        buf.push("a", captured_at=now)
        buf.push("b", captured_at=now + 0.01)
        buf.push("c", captured_at=now + 0.02)
        assert buf.dropped_overflow >= 1
        frame = buf.pop_latest(now=now + 0.03)
        assert frame is not None
        assert frame.data == "c"

    def test_stale_frame_dropped(self):
        buf = FrameRingBuffer(capacity=4, max_age_sec=1.0)
        old_time = time.monotonic() - 2.0
        buf.push("stale", captured_at=old_time)
        result = buf.pop_latest(now=time.monotonic())
        assert result is None
        assert buf.dropped_stale >= 1

    def test_fresh_frame_not_dropped(self):
        buf = FrameRingBuffer(capacity=4, max_age_sec=5.0)
        now = time.monotonic()
        buf.push("fresh", captured_at=now)
        frame = buf.pop_latest(now=now + 0.01)
        assert frame is not None
        assert frame.data == "fresh"

    def test_capacity_1_edge_case(self):
        buf = FrameRingBuffer(capacity=1, max_age_sec=5.0)
        now = time.monotonic()
        buf.push("a", captured_at=now)
        buf.push("b", captured_at=now + 0.01)
        frame = buf.pop_latest(now=now + 0.02)
        assert frame is not None
        assert frame.data == "b"

    def test_empty_pop_returns_none(self):
        buf = FrameRingBuffer(capacity=4, max_age_sec=5.0)
        assert buf.pop_latest() is None

    def test_stats(self):
        buf = FrameRingBuffer(capacity=2, max_age_sec=5.0)
        now = time.monotonic()
        buf.push("a", captured_at=now)
        buf.push("b", captured_at=now + 0.01)
        buf.push("c", captured_at=now + 0.02)
        stats = buf.stats()
        assert stats["capacity"] == 2
        assert stats["pushed"] == 3
        assert stats["dropped_overflow"] >= 1

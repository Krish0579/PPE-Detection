"""Rate limiting and per-identity login throttling (blueprint §11)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    tokens: float
    updated: float


class TokenBucketLimiter:
    """Per-key token bucket: ``capacity`` burst, refilled at ``rate_per_sec``."""

    def __init__(self, capacity: int = 10, rate_per_sec: float = 1.0, max_keys: int = 10_000) -> None:
        if capacity < 1 or rate_per_sec <= 0:
            raise ValueError("capacity must be >= 1 and rate_per_sec > 0")
        self.capacity = float(capacity)
        self.rate = float(rate_per_sec)
        self.max_keys = max_keys
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, cost: float = 1.0, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self.max_keys:
                    self._evict_full(now)
                bucket = _Bucket(self.capacity, now)
                self._buckets[key] = bucket
            bucket.tokens = min(self.capacity, bucket.tokens + (now - bucket.updated) * self.rate)
            bucket.updated = now
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True
            return False

    def _evict_full(self, now: float) -> None:
        for key, bucket in list(self._buckets.items()):
            if bucket.tokens + (now - bucket.updated) * self.rate >= self.capacity:
                del self._buckets[key]
        if len(self._buckets) >= self.max_keys:  # still saturated: drop oldest
            oldest = min(self._buckets, key=lambda k: self._buckets[k].updated)
            del self._buckets[oldest]


class LoginThrottle:
    """Exponential lockout keyed by identity (username and/or client address)."""

    def __init__(self, max_failures: int = 5, base_lock_sec: float = 5.0, max_lock_sec: float = 900.0) -> None:
        self.max_failures = max_failures
        self.base_lock_sec = base_lock_sec
        self.max_lock_sec = max_lock_sec
        self._failures: dict[str, int] = {}
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def remaining(self, key: str, now: float | None = None) -> float:
        now = time.time() if now is None else now
        with self._lock:
            return max(0.0, self._locked_until.get(key, 0.0) - now)

    def failure(self, key: str, now: float | None = None) -> float:
        now = time.time() if now is None else now
        with self._lock:
            count = self._failures.get(key, 0) + 1
            self._failures[key] = count
            if count < self.max_failures:
                return 0.0
            lock = min(self.base_lock_sec * (2.0 ** (count - self.max_failures)), self.max_lock_sec)
            self._locked_until[key] = now + lock
            return lock

    def success(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

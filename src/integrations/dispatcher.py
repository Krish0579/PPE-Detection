"""Bounded, non-blocking notification dispatcher with per-adapter isolation and retry."""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections import Counter
from collections.abc import Callable

from src.integrations.adapters import DeliveryResult, NotificationAdapter
from src.integrations.policy import Notification, NotificationPolicy

logger = logging.getLogger(__name__)

_STOP = object()


class NotificationDispatcher:
    def __init__(
        self,
        adapters: list[NotificationAdapter],
        policy: NotificationPolicy,
        *,
        max_queue: int = 256,
        max_attempts: int = 3,
        base_backoff_sec: float = 0.5,
        workers: int = 1,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_queue < 1 or max_attempts < 1 or workers < 1:
            raise ValueError("max_queue, max_attempts and workers must be >= 1")
        self._adapters = {a.name: a for a in adapters}
        self.policy = policy
        self.max_attempts = max_attempts
        self.base_backoff_sec = base_backoff_sec
        self._sleep = sleep
        self._queue: queue.Queue[object] = queue.Queue(maxsize=max_queue)
        self._threads: list[threading.Thread] = []
        self._workers = workers
        self._stats: Counter[str] = Counter()
        self._failures_by_adapter: Counter[str] = Counter()
        self._lock = threading.Lock()

    # --- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._threads:
            return
        for idx in range(self._workers):
            thread = threading.Thread(target=self._run, name=f"notify-{idx}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self, timeout: float = 5.0) -> None:
        for _ in self._threads:
            try:
                self._queue.put(_STOP, timeout=timeout)
            except queue.Full:
                break
        for thread in self._threads:
            thread.join(timeout)
        self._threads.clear()

    def flush(self, timeout: float = 5.0) -> bool:
        """Wait until the queue is drained (tests / graceful shutdown)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._queue.unfinished_tasks == 0:
                return True
            time.sleep(0.01)
        return self._queue.unfinished_tasks == 0

    # --- producer side (called from the safety engine; never blocks) -------
    def submit(self, notification: Notification) -> bool:
        targets = [t for t in self.policy.targets(notification) if t in self._adapters]
        if not targets:
            self._bump("filtered")
            return False
        try:
            self._queue.put_nowait((notification, tuple(targets)))
        except queue.Full:
            self._bump("dropped")
            logger.warning("Notification queue full; dropped %s", notification.dedupe_key)
            return False
        self._bump("queued")
        return True

    # --- consumer side -----------------------------------------------------
    def _run(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is _STOP:
                    return
                notification, targets = item  # type: ignore[misc]
                for name in targets:
                    self._deliver(self._adapters[name], notification)
            finally:
                self._queue.task_done()

    def _deliver(self, adapter: NotificationAdapter, notification: Notification) -> DeliveryResult:
        result = DeliveryResult(False, adapter.name, "not attempted")
        for attempt in range(1, self.max_attempts + 1):
            try:
                result = adapter.send(notification)
            except Exception as exc:
                result = DeliveryResult(False, adapter.name, f"{type(exc).__name__}: {exc}"[:300])
            if result.ok:
                self._bump("delivered")
                return result
            if attempt < self.max_attempts:
                self._sleep(self.base_backoff_sec * (2 ** (attempt - 1)))
        self._bump("failed")
        with self._lock:
            self._failures_by_adapter[adapter.name] += 1
        logger.warning("Notification delivery failed via %s: %s", adapter.name, result.reason)
        return result

    # --- observability -----------------------------------------------------
    def _bump(self, key: str) -> None:
        with self._lock:
            self._stats[key] += 1

    def stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "queue_depth": self._queue.qsize(),
                "queue_capacity": self._queue.maxsize,
                **{k: self._stats.get(k, 0) for k in ("queued", "delivered", "failed", "dropped", "filtered")},
                "failures_by_adapter": dict(self._failures_by_adapter),
            }

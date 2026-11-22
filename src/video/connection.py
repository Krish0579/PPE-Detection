"""Camera connection state machine with exponential backoff (blueprint §5).

DISCONNECTED → CONNECTING → CONNECTED → DEGRADED → RECONNECTING → CONNECTED

The machine is pure (time is injected) so reconnect behaviour is fully
testable without real cameras. Stream workers call :meth:`on_frame`,
:meth:`on_error` and :meth:`tick`; the machine decides when to retry.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum


class ConnectionState(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    DEGRADED = "DEGRADED"
    RECONNECTING = "RECONNECTING"


_ALLOWED: dict[ConnectionState, frozenset[ConnectionState]] = {
    ConnectionState.DISCONNECTED: frozenset({ConnectionState.CONNECTING}),
    ConnectionState.CONNECTING: frozenset(
        {ConnectionState.CONNECTED, ConnectionState.RECONNECTING, ConnectionState.DISCONNECTED}
    ),
    ConnectionState.CONNECTED: frozenset(
        {ConnectionState.DEGRADED, ConnectionState.RECONNECTING, ConnectionState.DISCONNECTED}
    ),
    ConnectionState.DEGRADED: frozenset(
        {ConnectionState.CONNECTED, ConnectionState.RECONNECTING, ConnectionState.DISCONNECTED}
    ),
    ConnectionState.RECONNECTING: frozenset(
        {ConnectionState.CONNECTING, ConnectionState.CONNECTED, ConnectionState.DISCONNECTED}
    ),
}


@dataclass(frozen=True)
class ReconnectPolicy:
    connect_timeout_sec: float = 10.0
    stale_after_sec: float = 2.0
    dead_after_sec: float = 10.0
    base_backoff_sec: float = 1.0
    max_backoff_sec: float = 60.0
    jitter_ratio: float = 0.2
    max_attempts: int | None = None

    def backoff(self, attempt: int, rng: random.Random | None = None) -> float:
        delay = min(self.max_backoff_sec, self.base_backoff_sec * (2.0 ** max(0, attempt - 1)))
        if self.jitter_ratio > 0:
            spread = delay * self.jitter_ratio
            delay += (rng or random).uniform(-spread, spread)
        return max(0.0, delay)


@dataclass
class CameraConnection:
    camera_id: str
    policy: ReconnectPolicy = field(default_factory=ReconnectPolicy)
    state: ConnectionState = ConnectionState.DISCONNECTED
    attempts: int = 0
    reconnects: int = 0
    ever_connected: bool = False
    last_frame_at: float | None = None
    state_since: float = 0.0
    next_retry_at: float | None = None
    last_error: str = ""
    history: list[tuple[float, str, str]] = field(default_factory=list)

    def _go(self, target: ConnectionState, now: float) -> None:
        if target == self.state:
            return
        if target not in _ALLOWED[self.state]:
            raise ValueError(f"Invalid connection transition: {self.state.value} -> {target.value}")
        self.history.append((now, self.state.value, target.value))
        del self.history[:-50]  # bounded history
        self.state = target
        self.state_since = now

    # --- worker events -----------------------------------------------------
    def start(self, now: float) -> None:
        self.attempts = 1
        self._go(ConnectionState.CONNECTING, now)

    def stop(self, now: float) -> None:
        self._go(ConnectionState.DISCONNECTED, now)
        self.next_retry_at = None

    def on_frame(self, now: float) -> None:
        self.last_frame_at = now
        if self.state in (ConnectionState.CONNECTING, ConnectionState.RECONNECTING, ConnectionState.DEGRADED):
            if self.state != ConnectionState.DEGRADED and self.ever_connected:
                self.reconnects += 1
            self._go(ConnectionState.CONNECTED, now)
            self.ever_connected = True
            self.attempts = 0
            self.next_retry_at = None

    def on_error(self, now: float, error: str = "") -> None:
        self.last_error = error[:300]
        if self.state == ConnectionState.DISCONNECTED:
            return
        self._schedule_retry(now)

    def tick(self, now: float) -> bool:
        """Advance timers. Returns ``True`` when the worker should attempt to (re)connect now."""
        if self.state == ConnectionState.CONNECTING and now - self.state_since >= self.policy.connect_timeout_sec:
            self.last_error = "connection timeout"
            self._schedule_retry(now)
        elif self.state in (ConnectionState.CONNECTED, ConnectionState.DEGRADED) and self.last_frame_at is not None:
            age = now - self.last_frame_at
            if age >= self.policy.dead_after_sec:
                self.last_error = "stream heartbeat lost"
                self._schedule_retry(now)
            elif age >= self.policy.stale_after_sec:
                self._go(ConnectionState.DEGRADED, now)
        if self.state == ConnectionState.RECONNECTING and self.next_retry_at is not None and now >= self.next_retry_at:
            if self.policy.max_attempts is not None and self.attempts >= self.policy.max_attempts:
                self.stop(now)
                return False
            self.attempts += 1
            self._go(ConnectionState.CONNECTING, now)
            return True
        return False

    def _schedule_retry(self, now: float) -> None:
        self._go(ConnectionState.RECONNECTING, now)
        self.next_retry_at = now + self.policy.backoff(max(1, self.attempts))

    @property
    def is_fresh(self) -> bool:
        return self.state == ConnectionState.CONNECTED

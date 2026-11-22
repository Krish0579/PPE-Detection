"""In-process publish/subscribe bus between platform layers.

Subscriber failures are isolated: one broken consumer (e.g. a notification
adapter) can never stop the safety engine or other subscribers.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[[Any], None]

TOPIC_DETECTION = "detection.result"
TOPIC_SAFETY_EVENT = "safety.event"
TOPIC_INCIDENT_OPENED = "incident.opened"
TOPIC_INCIDENT_UPDATED = "incident.updated"
TOPIC_INCIDENT_TRANSITION = "incident.transition"


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._lock = threading.Lock()
        self.failures = 0

    def subscribe(self, topic: str, handler: Handler) -> Callable[[], None]:
        """Register ``handler``; returns an unsubscribe callable."""
        with self._lock:
            self._handlers[topic].append(handler)

        def _unsubscribe() -> None:
            with self._lock:
                if handler in self._handlers[topic]:
                    self._handlers[topic].remove(handler)

        return _unsubscribe

    def publish(self, topic: str, payload: Any) -> int:
        """Deliver to every subscriber; returns the number of successful deliveries."""
        with self._lock:
            handlers = list(self._handlers.get(topic, ()))
        delivered = 0
        for handler in handlers:
            try:
                handler(payload)
                delivered += 1
            except Exception:
                self.failures += 1
                logger.exception("Event subscriber failed for topic %s", topic)
        return delivered

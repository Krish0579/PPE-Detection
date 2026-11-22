"""Non-blocking notification integrations (blueprint §12).

Incident → NotificationPolicy → NotificationDispatcher (bounded queue) →
Webhook / Slack / Teams / PagerDuty / Syslog adapters.

The vision pipeline never blocks on external services: submission is a
non-blocking enqueue, failures are isolated per adapter, retried according to
policy and surfaced through dispatcher statistics.
"""

from src.integrations.adapters import (
    DeliveryResult,
    NotificationAdapter,
    PagerDutyAdapter,
    SlackAdapter,
    SyslogAdapter,
    TeamsAdapter,
    WebhookAdapter,
)
from src.integrations.dispatcher import NotificationDispatcher
from src.integrations.policy import Notification, NotificationPolicy

__all__ = [
    "DeliveryResult",
    "Notification",
    "NotificationAdapter",
    "NotificationDispatcher",
    "NotificationPolicy",
    "PagerDutyAdapter",
    "SlackAdapter",
    "SyslogAdapter",
    "TeamsAdapter",
    "WebhookAdapter",
]

"""Reusable custom widgets for SAFE SIGHT AI desktop."""
from src.desktop.widgets.alert_panel import AlertPanel
from src.desktop.widgets.camera_selector import CameraSelector
from src.desktop.widgets.detection_panel import DetectionPanel
from src.desktop.widgets.metric_card import MetricCard
from src.desktop.widgets.status_badge import StatusBadge
from src.desktop.widgets.video_display import VideoDisplayWidget

__all__ = [
    "AlertPanel",
    "CameraSelector",
    "DetectionPanel",
    "MetricCard",
    "StatusBadge",
    "VideoDisplayWidget",
]

"""View modules for SAFE SIGHT AI desktop tabs."""
from src.desktop.views.dashboard_view import DashboardView
from src.desktop.views.evidence_view import EvidenceView
from src.desktop.views.image_view import ImageView
from src.desktop.views.live_feed_view import LiveFeedView
from src.desktop.views.settings_view import SettingsView
from src.desktop.views.video_review_view import VideoReviewView

__all__ = [
    "DashboardView",
    "EvidenceView",
    "ImageView",
    "LiveFeedView",
    "SettingsView",
    "VideoReviewView",
]

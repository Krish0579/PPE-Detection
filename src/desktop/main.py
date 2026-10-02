"""Main entry point for launching the SAFE SIGHT AI desktop application."""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from src.config.settings import CACHE_DIR, PROJECT_ROOT
from src.desktop.main_window import MainWindow

# Ensure Ultralytics config is local
os.environ["YOLO_CONFIG_DIR"] = str(CACHE_DIR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("safesight.desktop")


def load_stylesheet() -> str:
    """Load high-contrast industrial dark theme QSS stylesheet."""
    qss_path = PROJECT_ROOT / "src" / "desktop" / "styles" / "safesight.qss"
    if qss_path.exists():
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as exc:
            logger.warning("Could not read stylesheet from %s: %s", qss_path, exc)
    return ""


def main() -> int:
    """Run the PySide6 desktop application."""
    # Enable high-DPI scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("SAFE SIGHT AI")
    app.setOrganizationName("SafeSight")
    app.setFont(QFont("Helvetica Neue", 10))

    # Apply industrial stylesheet
    qss = load_stylesheet()
    if qss:
        app.setStyleSheet(qss)

    window = MainWindow()
    window.show()

    logger.info("SAFE SIGHT AI Desktop initialized and running.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

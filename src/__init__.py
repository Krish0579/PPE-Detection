"""SAFE SIGHT AI Platform package initialization.

Ensures Ultralytics config is confined to local workspace cache to avoid macOS permissions issues.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".cache" / "ultralytics"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ["YOLO_CONFIG_DIR"] = str(CACHE_DIR)

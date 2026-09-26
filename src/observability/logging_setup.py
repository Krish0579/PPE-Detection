"""Structured logging bootstrap for production operations."""
from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False


def configure_logging(level: str | None = None) -> logging.Logger:
    """Configure a single sane root handler (idempotent, Streamlit-safe)."""
    global _CONFIGURED
    raw = (level or os.environ.get("SAFE_SIGHT_LOG_LEVEL") or "INFO").upper()
    parsed = getattr(logging, raw, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root = logging.getLogger()
    if not _CONFIGURED:
        root.handlers.clear()
        root.addHandler(handler)
        root.setLevel(parsed)
        # Quiet noisy third-party chatter without hiding warnings.
        for noisy in ("urllib3", "PIL", "matplotlib", "ultralytics"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        _CONFIGURED = True
    else:
        root.setLevel(parsed)
    return logging.getLogger("safesight")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"safesight.{name}")

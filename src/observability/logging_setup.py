"""Structured logging bootstrap for production operations."""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_CONFIGURED = False

_FMT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATEFMT = "%Y-%m-%dT%H:%M:%S%z"

# 10 MiB x 5 files — matches the compose json-file rotation budget so native and
# container deployments keep a comparable on-disk log history.
_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 5


def _resolve_log_file() -> Path | None:
    """Return the rotating file-log target, or None for stdout-only logging.

    - ``SAFE_SIGHT_LOG_FILE=off|stdout`` disables file logging explicitly.
    - An explicit path enables file logging at that location.
    - Default: containers (``/app`` layout) log to stdout only — the runtime's
      log driver handles capture/rotation; native installs rotate under
      ``data/logs/safesight.log``.
    """
    raw = os.environ.get("SAFE_SIGHT_LOG_FILE", "").strip()
    if raw.lower() in {"off", "stdout", "none"}:
        return None
    if raw:
        return Path(raw).expanduser()
    if os.environ.get("SAFE_SIGHT_CONTAINER") == "1" or Path("/.dockerenv").exists():
        return None
    return Path(__file__).resolve().parents[2] / "data" / "logs" / "safesight.log"


def configure_logging(level: str | None = None) -> logging.Logger:
    """Configure sane root handlers (idempotent, Streamlit-safe)."""
    global _CONFIGURED
    raw = (level or os.environ.get("SAFE_SIGHT_LOG_LEVEL") or "INFO").upper()
    parsed = getattr(logging, raw, logging.INFO)
    formatter = logging.Formatter(fmt=_FMT, datefmt=_DATEFMT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    handlers: list[logging.Handler] = [stream_handler]

    log_file = _resolve_log_file()
    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
        except OSError as exc:  # never let logging setup crash the operator session
            print(f"logging: file handler disabled ({exc})", file=sys.stderr)

    root = logging.getLogger()
    if not _CONFIGURED:
        root.handlers.clear()
        for handler in handlers:
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

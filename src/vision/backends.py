"""Inference backend interface and hardware capability probing."""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class BackendKind(str, Enum):
    TENSORRT = "tensorrt"
    CUDA = "cuda"
    OPENVINO = "openvino"
    MPS = "mps"
    CPU = "cpu"


# Preference order when the operator asks for "auto".
PREFERENCE: tuple[BackendKind, ...] = (
    BackendKind.TENSORRT,
    BackendKind.CUDA,
    BackendKind.MPS,
    BackendKind.OPENVINO,
    BackendKind.CPU,
)


@dataclass(frozen=True)
class RawDetection:
    """Backend-neutral detection: class label, confidence and pixel box."""

    label: str
    confidence: float
    box: tuple[int, int, int, int]


@runtime_checkable
class InferenceBackend(Protocol):
    kind: BackendKind

    def warmup(self) -> None: ...

    def infer(self, frame: Any) -> list[RawDetection]: ...


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def probe_backends() -> set[BackendKind]:
    """Return the backends usable in this environment (never raises)."""
    found = {BackendKind.CPU}
    if _module_available("torch"):
        try:
            import torch

            if torch.cuda.is_available():
                found.add(BackendKind.CUDA)
                if _module_available("tensorrt"):
                    found.add(BackendKind.TENSORRT)
            mps = getattr(torch.backends, "mps", None)
            if mps is not None and mps.is_available():
                found.add(BackendKind.MPS)
        except Exception as exc:
            logger.warning("Torch backend probe failed: %s", exc)
    if _module_available("openvino"):
        found.add(BackendKind.OPENVINO)
    return found


def select_backend(requested: str = "auto", available: set[BackendKind] | None = None) -> BackendKind:
    """Resolve a requested backend, degrading gracefully to the best available one."""
    available = probe_backends() if available is None else set(available) | {BackendKind.CPU}
    text = (requested or "auto").strip().lower()
    if text.startswith("cuda:"):
        text = "cuda"
    if text != "auto":
        try:
            wanted = BackendKind(text)
        except ValueError:
            logger.warning("Unknown inference backend '%s'; using auto selection", requested)
        else:
            if wanted in available:
                return wanted
            logger.warning("Backend '%s' unavailable; falling back to best available", wanted.value)
    for kind in PREFERENCE:
        if kind in available:
            return kind
    return BackendKind.CPU

"""Hardware-aware vision core (blueprint §6).

Inference is abstracted behind :class:`InferenceBackend` so the pipeline is
independent of CPU / MPS / CUDA / TensorRT / OpenVINO specifics. Model
loading stays in :mod:`src.core.model_manager`; this package only defines the
contracts and capability probing.
"""

from src.vision.backends import (
    BackendKind,
    InferenceBackend,
    RawDetection,
    probe_backends,
    select_backend,
)
from src.vision.roi import crop_person_rois, expand_box

__all__ = [
    "BackendKind",
    "InferenceBackend",
    "RawDetection",
    "crop_person_rois",
    "expand_box",
    "probe_backends",
    "select_backend",
]

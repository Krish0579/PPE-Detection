"""Person ROI cropping for the two-stage person → PPE verification flow (blueprint §6)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def expand_box(
    box: Sequence[int], width: int, height: int, ratio: float = 0.1
) -> tuple[int, int, int, int]:
    """Grow a box by ``ratio`` on each side and clamp it to the frame."""
    x1, y1, x2, y2 = (int(v) for v in box[:4])
    pad_x = int((x2 - x1) * max(0.0, ratio))
    pad_y = int((y2 - y1) * max(0.0, ratio))
    return (
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(int(width), x2 + pad_x),
        min(int(height), y2 + pad_y),
    )


def crop_person_rois(
    frame: Any, boxes: Sequence[Sequence[int]], *, pad_ratio: float = 0.1, min_size: int = 16
) -> list[tuple[tuple[int, int, int, int], Any]]:
    """Return ``(box, crop)`` pairs for each person box large enough to verify PPE.

    ``frame`` is any HxW[xC] array supporting slicing (NumPy). Crops are views,
    not copies, to keep the hot path allocation-free.
    """
    height, width = int(frame.shape[0]), int(frame.shape[1])
    rois = []
    for box in boxes:
        x1, y1, x2, y2 = expand_box(box, width, height, pad_ratio)
        if x2 - x1 < min_size or y2 - y1 < min_size:
            continue
        rois.append(((x1, y1, x2, y2), frame[y1:y2, x1:x2]))
    return rois

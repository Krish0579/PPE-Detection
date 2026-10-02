"""Privacy helpers — irreversible face/person-region blur for exports.

Used when evidence snapshots leave the on-prem workstation (incident hand-off,
email, audit ZIP). Blurring is applied to copies only; the sealed SQLite audit
trail keeps the original capture.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2
except ImportError:  # headless/test environments without OpenCV
    cv2 = None  # type: ignore[assignment]


def blur_regions(frame: np.ndarray, boxes: list[tuple[int, int, int, int]], strength: int = 31) -> np.ndarray:
    if frame is None or frame.size == 0 or not boxes:
        return frame
    out = frame.copy()
    height, width = out.shape[:2]
    kernel = max(3, int(strength) | 1)  # odd kernel required by GaussianBlur
    if cv2 is None:
        return out
    for x1, y1, x2, y2 in boxes:
        xa, ya = max(0, int(x1)), max(0, int(y1))
        xb, yb = min(width, int(x2)), min(height, int(y2))
        if xb - xa < 4 or yb - ya < 4:
            continue
        roi = out[ya:yb, xa:xb]
        try:
            out[ya:yb, xa:xb] = cv2.GaussianBlur(roi, (kernel, kernel), 0)
        except Exception as exc:  # intentional per-region best-effort — see per-file-ignores (BLE001)
            logger.debug("Skipping unblurable region (%s,%s,%s,%s): %s", xa, ya, xb, yb, exc)
            continue
    return out


def blur_person_boxes(frame: np.ndarray, detections: list[dict], strength: int = 31) -> np.ndarray:
    boxes = [
        (int(d.get("x1", 0)), int(d.get("y1", 0)), int(d.get("x2", 0)), int(d.get("y2", 0)))
        for d in (detections or [])
        if str(d.get("label", "")).lower() == "person"
    ]
    return blur_regions(frame, boxes, strength=strength)

"""YOLO inference engine, bounding box normalization, and detection filtering.

Provides high-throughput prediction with per-class confidence thresholding.
"""
from __future__ import annotations

import numpy as np
from ultralytics import YOLO

from src.config.settings import MAX_DETECTIONS
from src.core.class_semantics import format_label, get_category, is_compliance, is_violation, normalize


def run_inference(
    model: YOLO,
    image: np.ndarray,
    conf_threshold: float = 0.30,
    iou_threshold: float = 0.45,
    per_class_conf: dict[str, float] | None = None,
    image_size: int = 640,
    max_detections: int = MAX_DETECTIONS,
    device: str = "cpu",
    half: bool = False,
) -> tuple[np.ndarray, np.ndarray, list[str], list[dict]]:
    """Execute YOLO prediction and filter results by per-class confidence.

    Returns:
        (boxes, scores, labels, detections_list)
    """
    if model is None or image is None or image.size == 0:
        return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.float32), [], []

    per_class = per_class_conf or {}
    floor_conf = min([conf_threshold, *per_class.values()]) if per_class else conf_threshold
    floor_conf = float(max(0.01, min(0.99, floor_conf)))

    results = model.predict(
        image,
        conf=floor_conf,
        iou=float(max(0.01, min(0.99, iou_threshold))),
        imgsz=int(image_size),
        max_det=int(max_detections),
        device=device,
        half=half,
        verbose=False,
    )

    if not results or len(results) == 0:
        return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.float32), [], []

    r = results[0]
    if r.boxes is None or len(r.boxes) == 0:
        return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.float32), [], []

    names = r.names if hasattr(r, "names") else getattr(model, "names", {})
    boxes_np = r.boxes.xyxy.detach().cpu().numpy()
    scores_np = r.boxes.conf.detach().cpu().numpy()
    cls_ids = r.boxes.cls.detach().cpu().numpy().astype(int)

    raw_labels = [str(names.get(int(c), int(c))) for c in cls_ids]

    # Filter detections using per-class thresholds (skip non-PPE background 'none' class)
    keep = []
    for i, (lab, sc) in enumerate(zip(raw_labels, scores_np)):
        norm_lab = normalize(lab)
        if norm_lab in ("none", "null", "background"):
            continue
        req_conf = float(per_class.get(norm_lab, per_class.get(norm_lab.replace("-", "_"), conf_threshold)))
        if float(sc) >= req_conf:
            keep.append(i)

    if not keep:
        return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.float32), [], []

    filtered_boxes = boxes_np[keep]
    filtered_scores = scores_np[keep]
    filtered_labels = [raw_labels[i] for i in keep]

    detections = []
    for box, lab, score in zip(filtered_boxes, filtered_labels, filtered_scores):
        x1, y1, x2, y2 = [round(float(v)) for v in box]
        detections.append({
            "label": normalize(lab),
            "display_label": format_label(lab),
            "confidence": round(float(score), 4),
            "conf": round(float(score), 4),
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "violation": is_violation(lab),
            "compliance": is_compliance(lab),
            "category": get_category(lab),
        })

    return filtered_boxes, filtered_scores, filtered_labels, detections

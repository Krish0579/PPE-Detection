"""YOLO inference engine, bounding box normalization, and detection filtering.

Provides high-throughput prediction with per-class confidence thresholding.
"""
from __future__ import annotations

import logging

import numpy as np
from ultralytics import YOLO

from src.config.settings import MAX_DETECTIONS
from src.core.class_semantics import (
    format_label,
    get_category,
    is_compliance,
    is_person,
    is_violation,
    normalize,
)

logger = logging.getLogger(__name__)


def nms_merge_detections(
    boxes: np.ndarray,
    scores: np.ndarray,
    labels: list[str],
    iou_threshold: float = 0.45,
) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Per-class Non-Maximum Suppression to fuse multiple inference passes."""
    if len(boxes) == 0:
        return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.float32), []

    keep_indices: list[int] = []
    unique_labels = set(labels)

    for ul in unique_labels:
        cls_idx = np.where(np.array(labels) == ul)[0]
        cls_boxes = boxes[cls_idx]
        cls_scores = scores[cls_idx]

        x1 = cls_boxes[:, 0]
        y1 = cls_boxes[:, 1]
        x2 = cls_boxes[:, 2]
        y2 = cls_boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = cls_scores.argsort()[::-1]

        cls_keep: list[int] = []
        while order.size > 0:
            i = order[0]
            cls_keep.append(cls_idx[i])
            if order.size == 1:
                break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            inter = w * h
            ovr = inter / np.maximum(areas[i] + areas[order[1:]] - inter, 1e-6)

            inds = np.where(ovr <= iou_threshold)[0]
            order = order[inds + 1]

        keep_indices.extend(cls_keep)

    keep_indices = sorted(keep_indices, key=lambda k: scores[k], reverse=True)
    return boxes[keep_indices], scores[keep_indices], [labels[k] for k in keep_indices]


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
    augment: bool = False,
    enable_crop_refinement: bool = False,
    crop_imgsz: int = 640,
) -> tuple[np.ndarray, np.ndarray, list[str], list[dict]]:
    """Execute YOLO prediction and filter results by per-class confidence.

    Supports multi-scale Test-Time Augmentation (TTA) and two-pass hierarchical
    worker-crop refinement to boost detection of small PPE (goggles, gloves, boots).

    Returns:
        (boxes, scores, labels, detections_list)
    """
    if model is None or image is None or image.size == 0:
        return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=np.float32), [], []

    per_class = per_class_conf or {}
    floor_conf = min([conf_threshold, *per_class.values()]) if per_class else conf_threshold
    floor_conf = float(max(0.01, min(0.99, floor_conf)))

    predict_kwargs = {
        "conf": floor_conf,
        "iou": float(max(0.01, min(0.99, iou_threshold))),
        "imgsz": int(image_size),
        "max_det": int(max_detections),
        "device": device,
        "half": half,
        "verbose": False,
    }
    if augment:
        predict_kwargs["augment"] = True

    try:
        results = model.predict(image, **predict_kwargs)
    except TypeError:
        predict_kwargs.pop("augment", None)
        predict_kwargs.pop("half", None)
        predict_kwargs.pop("device", None)
        results = model.predict(image, **predict_kwargs)

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

    # Hierarchical Two-Pass Scan: Crop each detected worker at native resolution
    # to catch small objects (goggles, gloves, boots, helmet details) that may be missed full-frame.
    if enable_crop_refinement and len(filtered_boxes) > 0 and getattr(image, "ndim", 0) == 3:
        H, W = image.shape[:2]
        crop_boxes: list[np.ndarray] = []
        crop_scores: list[float] = []
        crop_labels: list[str] = []

        person_indices = [i for i, lab in enumerate(filtered_labels) if is_person(lab)]
        for p_idx in person_indices[:6]:
            p_box = filtered_boxes[p_idx]
            px1, py1, px2, py2 = [float(v) for v in p_box]
            pw, ph = px2 - px1, py2 - py1
            if pw < 20 or ph < 20:
                continue

            cx1 = max(0, int(px1 - 0.10 * pw))
            cy1 = max(0, int(py1 - 0.10 * ph))
            cx2 = min(W, int(px2 + 0.10 * pw))
            cy2 = min(H, int(py2 + 0.10 * ph))

            if (cy2 - cy1) < 40 or (cx2 - cx1) < 40:
                continue

            crop = image[cy1:cy2, cx1:cx2]
            c_kwargs = {
                "conf": floor_conf,
                "iou": float(max(0.01, min(0.99, iou_threshold))),
                "imgsz": int(crop_imgsz),
                "device": device,
                "half": half,
                "verbose": False,
            }
            if augment:
                c_kwargs["augment"] = True
            try:
                c_results = model.predict(crop, **c_kwargs)
            except (TypeError, ValueError, RuntimeError) as exc:
                logger.debug("Crop prediction skipped: %s", exc)
                continue

            if not c_results or len(c_results) == 0:
                continue
            cr = c_results[0]
            if not hasattr(cr, "boxes") or cr.boxes is None or len(cr.boxes) == 0:
                continue

            c_names = cr.names if hasattr(cr, "names") else getattr(model, "names", {})
            c_boxes_np = cr.boxes.xyxy.detach().cpu().numpy()
            c_scores_np = cr.boxes.conf.detach().cpu().numpy()
            c_cls_ids = cr.boxes.cls.detach().cpu().numpy().astype(int)
            c_raw_labels = [str(c_names.get(int(c), int(c))) for c in c_cls_ids]

            for cb, csc, clab in zip(c_boxes_np, c_scores_np, c_raw_labels):
                c_norm = normalize(clab)
                if c_norm in ("none", "null", "background") or is_person(c_norm):
                    continue
                req_c = float(per_class.get(c_norm, per_class.get(c_norm.replace("-", "_"), conf_threshold)))
                if float(csc) >= req_c:
                    mapped_b = np.array([cb[0] + cx1, cb[1] + cy1, cb[2] + cx1, cb[3] + cy1], dtype=np.float32)
                    crop_boxes.append(mapped_b)
                    crop_scores.append(float(csc))
                    crop_labels.append(clab)

        if crop_boxes:
            all_b = np.vstack([filtered_boxes, np.array(crop_boxes, dtype=np.float32)])
            all_s = np.concatenate([filtered_scores, np.array(crop_scores, dtype=np.float32)])
            all_l = filtered_labels + crop_labels
            filtered_boxes, filtered_scores, filtered_labels = nms_merge_detections(
                all_b, all_s, all_l, iou_threshold=iou_threshold
            )

    if len(filtered_boxes) > max_detections:
        filtered_boxes = filtered_boxes[:max_detections]
        filtered_scores = filtered_scores[:max_detections]
        filtered_labels = filtered_labels[:max_detections]

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

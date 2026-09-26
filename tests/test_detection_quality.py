"""Regression tests for detection quality, display labels, and audit timestamps.

Covers fixes for:
- Raw model labels (e.g. ``no_goggle``) leaking into UI violation lists
  instead of human-readable names ("No Goggles").
- Naive datetimes in evidence/report export payloads (must be tz-aware UTC).
- False "No Gloves" violations on close-up webcam views where hands are
  physically out of frame.
- Per-class confidence floors covering every class the 11-class model emits.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import ClassVar

import numpy as np
import torch

from src.config.settings import DEFAULT_PER_CLASS_CONF, DEFAULT_REQUIRED_PPE
from src.core.class_semantics import format_label
from src.core.detector import run_inference
from src.core.ppe_associator import associate_ppe_to_workers
from src.storage.evidence import EvidenceManager


class _FakeBoxes:
    def __init__(self, xyxy, conf, cls):
        self.xyxy = torch.tensor(xyxy, dtype=torch.float32)
        self.conf = torch.tensor(conf, dtype=torch.float32)
        self.cls = torch.tensor(cls, dtype=torch.float32)

    def __len__(self):
        return len(self.cls)


class _FakeResult:
    def __init__(self, boxes, names):
        self.boxes = boxes
        self.names = names


class _FakeModel:
    """Minimal YOLO stand-in that emits the real model's 11 class names."""

    NAMES: ClassVar[dict[int, str]] = {
        0: "helmet", 1: "gloves", 2: "vest", 3: "boots", 4: "goggles",
        5: "none", 6: "Person", 7: "no_helmet", 8: "no_goggle",
        9: "no_gloves", 10: "no_boots",
    }

    def predict(self, image, **kwargs):
        boxes = _FakeBoxes(
            xyxy=[[10, 10, 110, 410], [20, 20, 100, 80]],
            conf=[0.90, 0.80],
            cls=[6, 9],  # Person + no_gloves
        )
        return [_FakeResult(boxes, self.NAMES)]


def test_display_labels_are_human_readable():
    """display_label must be formatted ('No Gloves'), not raw ('no_gloves')."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    _, _, _, dets = run_inference(_FakeModel(), img, conf_threshold=0.25)
    by_label = {d["label"]: d["display_label"] for d in dets}
    assert by_label["person"] == "Worker"
    assert by_label["no-gloves"] == "No Gloves"
    for d in dets:
        assert "_" not in d["display_label"], f"raw label leaked to UI: {d['display_label']}"


def test_per_class_conf_covers_all_model_classes():
    """Every detectable class the shipped 11-class model can emit has a
    calibrated floor. ('none' is intentionally excluded: run_inference drops
    background 'none' boxes before thresholding.)"""
    model_labels = {
        "helmet", "gloves", "vest", "boots", "goggles", "person",
        "no_helmet", "no_goggle", "no_gloves", "no_boots",
    }
    for raw in model_labels:
        norm = raw.replace("_", "-")
        assert (
            raw in DEFAULT_PER_CLASS_CONF or norm in DEFAULT_PER_CLASS_CONF
        ), f"missing per-class confidence floor for model class: {raw}"


def test_required_ppe_defaults_cover_all_five_categories():
    assert set(DEFAULT_REQUIRED_PPE) == {"helmet", "vest", "boots", "gloves", "goggles"}


def test_report_payload_timestamps_are_tz_aware():
    store = EvidenceManager()
    _, json_bytes = store.generate_report_payload(
        total_frames=10, fps=5.0, model_name="best.pt",
        counts={"violation": 1, "compliance": 2}, detections=[], events=[],
    )
    payload = json.loads(json_bytes.decode("utf-8"))
    ts = datetime.fromisoformat(payload["generated_at"])
    assert ts.tzinfo is not None, "report generated_at must be timezone-aware"


def test_no_false_gloves_violation_on_closeup_worker():
    """A wide/short close-up person box (head-and-shoulders webcam view) must
    NOT auto-flag 'No Gloves' when no gloves region is visible."""
    dets = [
        {"label": "person", "violation": False, "confidence": 0.9,
         "x1": 100, "y1": 40, "x2": 560, "y2": 300},  # w_h/w_w = 0.57 < 1.0
    ]
    workers = associate_ppe_to_workers(
        dets, frame_w=640, frame_h=480,
        required_ppe={"helmet": True, "vest": True, "boots": True,
                      "gloves": True, "goggles": True},
    )
    assert len(workers) == 1
    w = workers[0]
    assert w.gloves_status != "VIOLATION"
    assert not any("glove" in v.lower() for v in w.violations)


def test_explicit_no_gloves_still_flags_closeup_worker():
    """An explicit no_gloves detection must flag even on a close-up view."""
    dets = [
        {"label": "person", "violation": False, "confidence": 0.9,
         "x1": 100, "y1": 40, "x2": 560, "y2": 300},
        {"label": "no-gloves", "display_label": format_label("no_gloves"),
         "violation": True, "confidence": 0.8,
         "x1": 200, "y1": 150, "x2": 320, "y2": 240},
    ]
    workers = associate_ppe_to_workers(
        dets, frame_w=640, frame_h=480,
        required_ppe={"helmet": True, "vest": True, "boots": True,
                      "gloves": True, "goggles": True},
    )
    assert workers[0].gloves_status == "VIOLATION"


def test_full_body_worker_missing_gloves_still_flags():
    """A full-body worker (tall box) with no gloves detected must flag."""
    dets = [
        {"label": "person", "violation": False, "confidence": 0.9,
         "x1": 200, "y1": 20, "x2": 360, "y2": 440},  # w_h/w_w = 2.6
    ]
    workers = associate_ppe_to_workers(
        dets, frame_w=640, frame_h=480,
        required_ppe={"helmet": True, "vest": True, "boots": True,
                      "gloves": True, "goggles": True},
    )
    assert workers[0].gloves_status == "VIOLATION"
    assert any("glove" in v.lower() for v in workers[0].violations)

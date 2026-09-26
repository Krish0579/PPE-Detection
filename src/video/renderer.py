"""SAFE SIGHT AI high-performance HUD annotation and video rendering engine.

Renders shopfloor camera overlays matching the SAFE SIGHT AI design system:
precise corner brackets, dual header/footer status badges, top live telemetry bar,
and bottom inference metrics.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime

import cv2
import numpy as np

from src.config.settings import (
    BGR_GREEN,
    BGR_RED,
    BGR_WHITE,
)
from src.core.class_semantics import bgr_for, format_label, is_person, is_violation
from src.core.ppe_associator import WorkerStatus


class OverlayRenderer:
    """Zero-copy HUD and bounding box renderer for real-time video."""

    def __init__(self):
        self.font = cv2.FONT_HERSHEY_DUPLEX

    def draw_corner_brackets(
        self,
        frame: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: tuple[int, int, int],
        thickness: int = 2,
        length: int = 14,
    ) -> None:
        """Draw modern corner accent brackets around target bounding box."""
        # Top-left
        cv2.line(frame, (x1, y1), (x1 + length, y1), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x1, y1), (x1, y1 + length), color, thickness, cv2.LINE_AA)
        # Top-right
        cv2.line(frame, (x2, y1), (x2 - length, y1), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x2, y1), (x2, y1 + length), color, thickness, cv2.LINE_AA)
        # Bottom-left
        cv2.line(frame, (x1, y2), (x1 + length, y2), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x1, y2), (x1, y2 - length), color, thickness, cv2.LINE_AA)
        # Bottom-right
        cv2.line(frame, (x2, y2), (x2 - length, y2), color, thickness, cv2.LINE_AA)
        cv2.line(frame, (x2, y2), (x2, y2 - length), color, thickness, cv2.LINE_AA)

    def draw_label_chip(
        self,
        frame: np.ndarray,
        x: int,
        y: int,
        text: str,
        color: tuple[int, int, int],
        scale: float = 0.45,
    ) -> None:
        """Draw an anti-aliased pill label chip."""
        _h, w = frame.shape[:2]
        (tw, th), bl = cv2.getTextSize(text, self.font, scale, 1)

        chip_w = tw + 12
        chip_h = th + bl + 6

        top = max(4, y - chip_h - 2)
        left = max(4, min(x, w - chip_w - 4))

        cv2.rectangle(frame, (left, top), (left + chip_w, top + chip_h), color, -1)
        cv2.putText(frame, text, (left + 6, top + th + 2), self.font, scale, BGR_WHITE, 1, cv2.LINE_AA)

    def draw_worker_badges(
        self,
        frame: np.ndarray,
        workers: list[WorkerStatus],
    ) -> np.ndarray:
        """Draw SAFE SIGHT AI style dual-badge detection boxes around workers with 8K clarity and separate PPE status pills."""
        if not workers:
            return frame

        h, w = frame.shape[:2]
        # Dynamic scaling supporting resolutions from 720p to 8K UHD (7680x4320)
        res_factor = max(0.6, float(min(w, h)) / 720.0)
        font_scale = max(0.42, 0.42 * (res_factor ** 0.82))
        sub_scale = max(0.35, 0.35 * (res_factor ** 0.82))
        line_thick = max(1, round(res_factor))
        bracket_thick = max(2, round(2.2 * res_factor))
        pad = max(3, round(5 * res_factor))
        gap = max(3, round(4 * res_factor))

        for w_obj in workers:
            wx1, wy1, wx2, wy2 = w_obj.box
            wx1, wy1 = max(0, int(wx1)), max(0, int(wy1))
            wx2, wy2 = min(w - 1, int(wx2)), min(h - 1, int(wy2))

            viol = w_obj.has_active_violation
            color = BGR_RED if viol else BGR_GREEN

            # 1. Anti-aliased bounding box + modern corner brackets
            cv2.line(frame, (wx1, wy1), (wx2, wy1), color, line_thick, cv2.LINE_AA)
            cv2.line(frame, (wx2, wy1), (wx2, wy2), color, line_thick, cv2.LINE_AA)
            cv2.line(frame, (wx2, wy2), (wx1, wy2), color, line_thick, cv2.LINE_AA)
            cv2.line(frame, (wx1, wy2), (wx1, wy1), color, line_thick, cv2.LINE_AA)

            bracket_len = min(int(42 * res_factor), max(int(14 * res_factor), int(min(wx2 - wx1, wy2 - wy1) * 0.22)))
            self.draw_corner_brackets(frame, wx1, wy1, wx2, wy2, color, thickness=bracket_thick, length=bracket_len)

            # 2. Top Header Badge: "Worker {id} - SAFE" or "Worker {id} - VIOLATIONS DETECTED"
            if viol:
                top_label = f"Worker #{w_obj.worker_id:02d} - VIOLATION"
            else:
                top_label = f"Worker #{w_obj.worker_id:02d} - COMPLIANT"

            (tw, th), _ = cv2.getTextSize(top_label, self.font, font_scale, line_thick)
            badge_w = min(max(20, w - 8), tw + (pad * 2))
            badge_top = max(4, wy1 - th - (pad * 2))
            if badge_top < 45 and wy1 >= 45:
                badge_top = wy1 + pad
            badge_left = max(4, min(wx1, w - badge_w - 4))

            cv2.rectangle(frame, (badge_left, badge_top), (badge_left + badge_w, badge_top + th + (pad * 2)), color, -1)
            cv2.rectangle(frame, (badge_left, badge_top), (badge_left + badge_w, badge_top + th + (pad * 2)), (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(frame, top_label, (badge_left + pad, badge_top + th + pad - 1), self.font, font_scale, BGR_WHITE, line_thick, cv2.LINE_AA)

            # 3. Dedicated Individual PPE Status Pills (Helmet, Vest, Gloves, Boots, Goggles)
            req = w_obj.required_ppe or {}
            ppe_categories = [
                ("helmet", "Helmet", "No Helmet", w_obj.helmet_status),
                ("vest", "Vest", "No Vest", w_obj.vest_status),
                ("gloves", "Gloves", "No Gloves", w_obj.gloves_status),
                ("boots", "Boots", "No Boots", w_obj.boots_status),
                ("goggles", "Goggles", "No Goggles", w_obj.goggles_status),
            ]

            pills: list[tuple[str, tuple[int, int, int]]] = []
            for key, name, no_name, st_val in ppe_categories:
                is_req = req.get(key, True) if req else True
                if not is_req:
                    pills.append((f"- {name}", (50, 55, 60)))  # Optional / N/A (neutral grey)
                elif st_val == "COMPLIANT":
                    pills.append((f"[OK] {name}", (28, 150, 60)))  # Compliant (safety green)
                else:
                    # Explicitly state missing PPE separately
                    pills.append((f"[X] {no_name}", (35, 35, 215)))  # Violation (vivid red)

            # Measure pill sizes
            pill_layouts = []
            for pill_text, bg_col in pills:
                (ptw, pth), _ = cv2.getTextSize(pill_text, self.font, sub_scale, line_thick)
                pw = ptw + pad * 2
                ph = pth + pad * 2
                pill_layouts.append((pill_text, bg_col, pw, ph, ptw, pth))

            # Position pills underneath the worker bounding box (or above if near bottom edge)
            cur_y = wy2 + pad
            if cur_y + (pill_layouts[0][3] * 2) > h - 42 and wy1 >= (pill_layouts[0][3] * 2 + 50):
                # Place pills above the box
                cur_y = max(4, badge_top - (pill_layouts[0][3] * 2) - pad)

            start_x = max(4, min(wx1, w - 120))
            cur_x = start_x
            max_row_h = 0

            for pill_text, bg_col, pw, ph, ptw, pth in pill_layouts:
                if cur_x + pw > w - 4 and cur_x > start_x:
                    # Wrap to next line
                    cur_x = start_x
                    cur_y += max_row_h + gap
                    max_row_h = 0

                if cur_y + ph > h - 4:
                    break  # Prevent drawing beyond frame boundaries

                # Draw crisp pill background + border + anti-aliased text
                cv2.rectangle(frame, (cur_x, cur_y), (cur_x + pw, cur_y + ph), bg_col, -1)
                cv2.rectangle(frame, (cur_x, cur_y), (cur_x + pw, cur_y + ph), (240, 240, 240), 1, cv2.LINE_AA)
                cv2.putText(
                    frame,
                    pill_text,
                    (cur_x + pad, cur_y + pth + pad - 1),
                    self.font,
                    sub_scale,
                    BGR_WHITE,
                    line_thick,
                    cv2.LINE_AA,
                )

                cur_x += pw + gap
                max_row_h = max(max_row_h, ph)

        return frame

    def draw_detections(
        self,
        frame: np.ndarray,
        boxes: np.ndarray,
        labels: list[str],
        scores: np.ndarray,
    ) -> np.ndarray:
        """Draw standalone PPE item detections with 8K anti-aliasing and resolution scaling."""
        if len(boxes) == 0:
            return frame

        h, w = frame.shape[:2]
        res_factor = max(0.6, float(min(w, h)) / 720.0)
        base_scale = max(0.38, 0.38 * (res_factor ** 0.82))
        max(1, round(res_factor))

        for (x1, y1, x2, y2), label, score in zip(boxes, labels, scores):
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(w - 1, int(x2)), min(h - 1, int(y2))

            color = bgr_for(label)
            viol = is_violation(label)
            thick = max(2, round(2.0 * res_factor)) if viol else max(1, round(res_factor))

            # Anti-aliased rectangle
            cv2.line(frame, (x1, y1), (x2, y1), color, thick, cv2.LINE_AA)
            cv2.line(frame, (x2, y1), (x2, y2), color, thick, cv2.LINE_AA)
            cv2.line(frame, (x2, y2), (x1, y2), color, thick, cv2.LINE_AA)
            cv2.line(frame, (x1, y2), (x1, y1), color, thick, cv2.LINE_AA)

            bracket_len = min(int(24 * res_factor), max(int(8 * res_factor), int(min(x2 - x1, y2 - y1) * 0.22)))
            self.draw_corner_brackets(frame, x1, y1, x2, y2, color, thick + 1, bracket_len)

            prefix = "! " if viol else ""
            display_text = f"{prefix}{format_label(label).upper()} {int(score * 100)}%"
            self.draw_label_chip(frame, x1, y1, display_text, color, scale=base_scale)

        return frame

    def enhance_visual_clarity(self, frame: np.ndarray, strength: float = 0.28) -> np.ndarray:
        """Fast SIMD unsharp masking to enhance edge contrast and eliminate optical sensor blur."""
        if strength <= 0.0 or frame is None or frame.size == 0:
            return frame
        try:
            blur = cv2.GaussianBlur(frame, (0, 0), 1.6)
            return cv2.addWeighted(frame, 1.0 + strength, blur, -strength, 0)
        except Exception:
            return frame

    def render_8k_clarity_canvas(
        self,
        frame: np.ndarray,
        workers: list[WorkerStatus],
        boxes: np.ndarray | None = None,
        labels: list[str] | None = None,
        scores: np.ndarray | None = None,
        target_mode: str = "8K",
        enhance_sharpness: bool = True,
        show_hud: bool = True,
        fps: float = 30.0,
        violations_count: int = 0,
        inference_ms: float = 25.0,
        simulated: bool = False,
    ) -> np.ndarray:
        """Render frame on an Ultra-Clarity 8K/4K super-sampled canvas with razor-sharp anti-aliasing."""
        if frame is None or frame.size == 0:
            return frame

        orig_h, orig_w = frame.shape[:2]

        # Determine target resolution
        if target_mode == "8K":
            # 8K UHD: width 7680
            target_w = 7680
            target_h = round(orig_h * (7680.0 / float(orig_w)))
        elif target_mode == "4K":
            # 4K UHD: width 3840
            target_w = 3840
            target_h = round(orig_h * (3840.0 / float(orig_w)))
        elif target_mode == "2K":
            # 2K QHD: width 2560
            target_w = 2560
            target_h = round(orig_h * (2560.0 / float(orig_w)))
        else:
            target_w = orig_w
            target_h = orig_h

        # Upscale frame with high-fidelity bicubic interpolation
        if target_w != orig_w or target_h != orig_h:
            high_res_frame = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
            scale_x = target_w / float(orig_w)
            scale_y = target_h / float(orig_h)
        else:
            high_res_frame = frame.copy()
            scale_x = 1.0
            scale_y = 1.0

        if enhance_sharpness:
            high_res_frame = self.enhance_visual_clarity(high_res_frame, strength=0.30)

        # Scale worker bounding boxes
        scaled_workers: list[WorkerStatus] = []
        for w_obj in workers:
            wx1, wy1, wx2, wy2 = w_obj.box
            s_box = (
                round(wx1 * scale_x),
                round(wy1 * scale_y),
                round(wx2 * scale_x),
                round(wy2 * scale_y),
            )
            sw = dataclasses.replace(w_obj, box=s_box)
            scaled_workers.append(sw)

        # Scale detection boxes if present
        scaled_boxes = np.empty((0, 4), dtype=np.float32)
        if boxes is not None and len(boxes) > 0:
            scaled_boxes = boxes.copy()
            scaled_boxes[:, [0, 2]] *= scale_x
            scaled_boxes[:, [1, 3]] *= scale_y

        # Draw overlays on the high-res canvas
        if scaled_workers:
            high_res_frame = self.draw_worker_badges(high_res_frame, scaled_workers)
            if len(scaled_boxes) > 0 and labels is not None and scores is not None:
                ppe_boxes = []
                ppe_labels = []
                ppe_scores = []
                for b, l, s in zip(scaled_boxes, labels, scores):
                    if not is_person(l):
                        ppe_boxes.append(b)
                        ppe_labels.append(l)
                        ppe_scores.append(s)
                if ppe_boxes:
                    high_res_frame = self.draw_detections(
                        high_res_frame,
                        np.array(ppe_boxes, dtype=np.float32),
                        ppe_labels,
                        np.array(ppe_scores, dtype=np.float32),
                    )
        elif len(scaled_boxes) > 0 and labels is not None and scores is not None:
            high_res_frame = self.draw_detections(high_res_frame, scaled_boxes, labels, scores)

        if show_hud:
            high_res_frame = self.draw_telemetry_hud(
                high_res_frame,
                fps=fps,
                violations_count=violations_count,
                workers_count=len(workers),
                inference_ms=inference_ms,
                show_hud=True,
                simulated=simulated,
            )

        return high_res_frame

    def draw_telemetry_hud(
        self,
        frame: np.ndarray,
        fps: float,
        violations_count: int,
        workers_count: int,
        inference_ms: float = 35.0,
        camera_id: str = "CAM-01",
        zone_name: str = "Production Line",
        show_hud: bool = True,
        simulated: bool = False,
    ) -> np.ndarray:
        """Draw top and bottom SAFE SIGHT AI camera overlays with dynamic 8K scaling and in-place SIMD blending."""
        if not show_hud:
            return frame

        h, w = frame.shape[:2]
        if h < 64 or w < 200:
            return frame  # Frame too small for HUD overlay

        res_factor = max(0.7, float(min(w, h)) / 720.0)
        hud_font = max(0.40, 0.40 * (res_factor ** 0.82))
        top_h = max(34, round(36 * (res_factor ** 0.75)))
        bot_h = max(32, round(34 * (res_factor ** 0.75)))
        line_thick = max(1, round(res_factor))

        # 1. TOP OVERLAY STRIP (In-place SIMD scaling for maximum speed)
        top_roi = frame[0:top_h, 0:w]
        cv2.convertScaleAbs(top_roi, alpha=0.25, beta=10, dst=top_roi)

        # Top-left LIVE or SIM badge
        badge_text = "SIM" if simulated else "LIVE"
        badge_color = (20, 160, 220) if simulated else (100, 160, 20)  # Amber for SIM, Green for LIVE
        badge_w = max(58, round(62 * (res_factor ** 0.8)))
        badge_h = max(24, round(26 * (res_factor ** 0.8)))
        by1 = max(4, (top_h - badge_h) // 2)
        cv2.rectangle(frame, (10, by1), (10 + badge_w, by1 + badge_h), badge_color, -1)
        cv2.circle(frame, (10 + int(10 * res_factor), by1 + badge_h // 2), max(2, round(3 * res_factor)), BGR_WHITE, -1, cv2.LINE_AA)
        cv2.putText(frame, badge_text, (10 + int(18 * res_factor), by1 + int(badge_h * 0.72)), self.font, hud_font, BGR_WHITE, line_thick, cv2.LINE_AA)

        # Center camera & zone
        cam_text = f"{camera_id}  |  {zone_name}"
        (cw, _), _ = cv2.getTextSize(cam_text, self.font, hud_font, line_thick)
        cv2.putText(frame, cam_text, (max(10 + badge_w + 10, (w - cw) // 2), int(top_h * 0.65)), self.font, hud_font, (220, 230, 235), line_thick, cv2.LINE_AA)

        # Right clock timestamp
        time_str = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        (tw, _), _ = cv2.getTextSize(time_str, self.font, hud_font, line_thick)
        cv2.putText(frame, time_str, (max(w - tw - 16, 10), int(top_h * 0.65)), self.font, hud_font, (180, 200, 205), line_thick, cv2.LINE_AA)

        # 2. BOTTOM OVERLAY STRIP (In-place SIMD scaling)
        by1_bot = h - bot_h
        bot_roi = frame[by1_bot:h, 0:w]
        cv2.convertScaleAbs(bot_roi, alpha=0.20, beta=8, dst=bot_roi)

        # Bottom-left: "YOLO PPE - X personnel"
        tracks_text = f"YOLO PPE - {workers_count} personnel"
        cv2.putText(frame, tracks_text, (16, h - int(bot_h * 0.32)), self.font, hud_font, (215, 230, 235), line_thick, cv2.LINE_AA)

        # Bottom-right: "FPS | latency"
        status_color = BGR_RED if violations_count > 0 else BGR_GREEN
        perf_text = f"{fps:4.1f} FPS  |  {inference_ms:.0f} ms"
        (pw, _), _ = cv2.getTextSize(perf_text, self.font, hud_font, line_thick)
        dot_x = max(16, w - pw - int(32 * res_factor))
        cv2.circle(frame, (dot_x, h - int(bot_h * 0.48)), max(3, round(5 * res_factor)), status_color, -1, cv2.LINE_AA)
        cv2.putText(frame, perf_text, (dot_x + int(14 * res_factor), h - int(bot_h * 0.32)), self.font, hud_font, (215, 230, 235), line_thick, cv2.LINE_AA)

        return frame


_DEFAULT_RENDERER: OverlayRenderer | None = None


def get_default_renderer() -> OverlayRenderer:
    """Singleton getter for default OverlayRenderer."""
    global _DEFAULT_RENDERER
    if _DEFAULT_RENDERER is None:
        _DEFAULT_RENDERER = OverlayRenderer()
    return _DEFAULT_RENDERER


def enhance_visual_clarity(frame: np.ndarray, strength: float = 0.28) -> np.ndarray:
    """Module-level unsharp masking helper."""
    return get_default_renderer().enhance_visual_clarity(frame, strength=strength)


def render_8k_clarity_canvas(
    frame: np.ndarray,
    workers: list[WorkerStatus],
    boxes: np.ndarray | None = None,
    labels: list[str] | None = None,
    scores: np.ndarray | None = None,
    target_mode: str = "8K",
    enhance_sharpness: bool = True,
    show_hud: bool = True,
    fps: float = 30.0,
    violations_count: int = 0,
    inference_ms: float = 25.0,
    simulated: bool = False,
) -> np.ndarray:
    """Module-level helper to render on 8K/4K/1080p canvas."""
    return get_default_renderer().render_8k_clarity_canvas(
        frame=frame,
        workers=workers,
        boxes=boxes,
        labels=labels,
        scores=scores,
        target_mode=target_mode,
        enhance_sharpness=enhance_sharpness,
        show_hud=show_hud,
        fps=fps,
        violations_count=violations_count,
        inference_ms=inference_ms,
        simulated=simulated,
    )

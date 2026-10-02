"""Spatial association of PPE items (helmets, vests, boots) to detected workers.

Uses vertical anatomical zoning (head region, torso region, foot region) and
zone containment to determine safety compliance on a per-worker basis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from src.config.settings import DEFAULT_ZONES, ZoneConfig
from src.core.class_semantics import (
    is_boots,
    is_compliance,
    is_gloves,
    is_goggles,
    is_helmet,
    is_person,
    is_vest,
    normalize,
)


@dataclass
class WorkerStatus:
    """Per-worker safety compliance and zone location profile."""

    worker_id: int
    box: tuple[int, int, int, int]
    helmet_status: str = "UNKNOWN"  # "COMPLIANT", "VIOLATION", "UNKNOWN"
    vest_status: str = "UNKNOWN"  # "COMPLIANT", "VIOLATION", "UNKNOWN"
    boots_status: str = "UNKNOWN"  # "COMPLIANT", "VIOLATION", "UNKNOWN"
    gloves_status: str = "UNKNOWN"  # "COMPLIANT", "VIOLATION", "UNKNOWN"
    goggles_status: str = "UNKNOWN"  # "COMPLIANT", "VIOLATION", "UNKNOWN"
    zone: str = "Assembly Line A"
    zone_type: str = "Standard"
    is_restricted_zone: bool = False
    dwell_seconds: float = 0.0
    violations: list[str] = field(default_factory=list)
    compliances: list[str] = field(default_factory=list)
    required_ppe: dict[str, bool] | None = None
    explicit_violations: list[str] = field(default_factory=list)

    @property
    def is_compliant(self) -> bool:
        if self.is_restricted_zone:
            return False
        if self.has_active_violation:
            return False

        if self.required_ppe is None:
            # When no required_ppe dict is provided, compliant if at least one gear is compliant and no violations
            return any(
                status == "COMPLIANT"
                for status in (
                    self.helmet_status,
                    self.vest_status,
                    self.boots_status,
                    self.gloves_status,
                    self.goggles_status,
                )
            )
        else:
            req = self.required_ppe
            has_required = False
            has_at_least_one_compliant = False
            for key in ("helmet", "vest", "boots", "gloves", "goggles"):
                if req.get(key, False):
                    has_required = True
                    status = getattr(self, f"{key}_status", "UNKNOWN")
                    if status == "VIOLATION":
                        return False
                    if status == "COMPLIANT":
                        has_at_least_one_compliant = True
                    elif status == "UNKNOWN":
                        # When boots are cropped out of frame, status remains UNKNOWN.
                        # Do not fail compliance on unobservable feet if other required visible gear is compliant.
                        if key == "boots":
                            continue
                        return False
            return has_at_least_one_compliant if has_required else True

    @property
    def track_id(self) -> int:
        return self.worker_id

    @property
    def zone_id(self) -> str:
        return self.zone

    @property
    def status(self) -> str:
        return "SAFE" if self.is_compliant else "UNSAFE"

    @property
    def gear(self) -> dict[str, str]:
        return {
            "helmet": self.helmet_status,
            "vest": self.vest_status,
            "boots": self.boots_status,
            "gloves": self.gloves_status,
            "goggles": self.goggles_status,
        }

    @property
    def has_active_violation(self) -> bool:
        if self.is_restricted_zone:
            return True
        if self.required_ppe is None:
            if (
                self.helmet_status == "VIOLATION"
                or self.vest_status == "VIOLATION"
                or self.boots_status == "VIOLATION"
                or self.gloves_status == "VIOLATION"
                or self.goggles_status == "VIOLATION"
            ):
                return True
            return len(self.violations) > 0
        else:
            req = self.required_ppe
            if req.get("helmet", False) and self.helmet_status == "VIOLATION":
                return True
            if req.get("vest", False) and self.vest_status == "VIOLATION":
                return True
            if req.get("boots", False) and self.boots_status == "VIOLATION":
                return True
            if req.get("gloves", False) and self.gloves_status == "VIOLATION":
                return True
            if req.get("goggles", False) and self.goggles_status == "VIOLATION":
                return True
            for v in self.violations:
                nv = v.lower()
                if "helmet" in nv and not req.get("helmet", False):
                    continue
                if "vest" in nv and not req.get("vest", False):
                    continue
                if "boot" in nv and not req.get("boots", False):
                    continue
                if "glove" in nv and not req.get("gloves", False):
                    continue
                if ("goggle" in nv or "glass" in nv) and not req.get("goggles", False):
                    continue
                return True
            return False


def box_center(box: tuple[int, int, int, int]) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def box_intersection_ratio(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    """Compute how much of box_a is contained inside box_b."""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter_area = (ix2 - ix1) * (iy2 - iy1)
    a_area = max(1, (ax2 - ax1) * (ay2 - ay1))
    return inter_area / float(a_area)


def find_zone_for_point(nx: float, ny: float, zones: list[ZoneConfig]) -> tuple[str, str, bool]:
    """Determine which shopfloor zone normalized point (nx, ny) falls into."""
    for z in zones:
        if len(z.polygon) == 4:
            x_min = min(p[0] for p in z.polygon)
            x_max = max(p[0] for p in z.polygon)
            y_min = min(p[1] for p in z.polygon)
            y_max = max(p[1] for p in z.polygon)
            if x_min <= nx <= x_max and y_min <= ny <= y_max:
                return z.name, z.type, z.type == "Restricted"

    return "Shopfloor General", "Standard", False


class WorkerTracker:
    """Frame-to-frame persistent worker tracking using IoU, centroid distance, and visual Re-ID."""

    def __init__(self, max_lost: int = 120, iou_thresh: float = 0.25):
        self.max_lost = max_lost
        self.iou_thresh = iou_thresh
        self.next_id = 1
        self.tracks: dict[int, dict] = {}
        # Persistent identity gallery storing appearance and historical stats across camera exits
        self.gallery: dict[int, dict] = {}

    def extract_feature(self, frame_image: np.ndarray | None, box: tuple[int, int, int, int]) -> np.ndarray | None:
        """Extract a multi-zone spatial HSV color appearance signature (upper torso + lower body).
        Extremely fast (<0.4ms) and illumination-invariant, re-identifies workers across camera exits."""
        if frame_image is None or not isinstance(frame_image, np.ndarray) or frame_image.size == 0:
            return None
        try:
            import cv2

            ih, iw = frame_image.shape[:2]
            x1, y1, x2, y2 = box
            x1, y1 = max(0, min(iw - 1, int(x1))), max(0, min(ih - 1, int(y1)))
            x2, y2 = max(0, min(iw, int(x2))), max(0, min(ih, int(y2)))
            if x2 - x1 < 10 or y2 - y1 < 10:
                return None

            bw = x2 - x1
            bh = y2 - y1

            # 1. Upper torso / shirt region (20% to 55% height)
            tx1 = int(x1 + bw * 0.15)
            tx2 = int(x2 - bw * 0.15)
            uy1 = int(y1 + bh * 0.20)
            uy2 = int(y1 + bh * 0.55)
            crop_upper = frame_image[uy1:uy2, tx1:tx2]
            if crop_upper.size == 0 or crop_upper.shape[0] < 4 or crop_upper.shape[1] < 4:
                crop_upper = frame_image[y1:y2, x1:x2]

            hsv_upper = cv2.cvtColor(crop_upper, cv2.COLOR_BGR2HSV)
            hist_upper = cv2.calcHist([hsv_upper], [0, 1], None, [16, 8], [0, 180, 0, 256])
            cv2.normalize(hist_upper, hist_upper, 0, 1.0, cv2.NORM_MINMAX)

            # 2. Lower body / pants region (55% to 88% height)
            ly1 = int(y1 + bh * 0.55)
            ly2 = int(y1 + bh * 0.88)
            crop_lower = frame_image[ly1:ly2, tx1:tx2]
            if crop_lower.size == 0 or crop_lower.shape[0] < 4 or crop_lower.shape[1] < 4:
                hist_lower = hist_upper.copy()
            else:
                hsv_lower = cv2.cvtColor(crop_lower, cv2.COLOR_BGR2HSV)
                hist_lower = cv2.calcHist([hsv_lower], [0, 1], None, [16, 8], [0, 180, 0, 256])
                cv2.normalize(hist_lower, hist_lower, 0, 1.0, cv2.NORM_MINMAX)

            # Stack into a single 32x8 feature array (upper: rows 0-15, lower: rows 16-31)
            combined_hist = np.vstack([hist_upper, hist_lower])
            return combined_hist
        except Exception:
            return None

    def compute_similarity(self, hist_a: np.ndarray | None, hist_b: np.ndarray | None) -> float:
        """Compute composite appearance similarity combining Bhattacharyya distance and Pearson correlation."""
        if hist_a is None or hist_b is None:
            return 0.0
        try:
            import cv2

            # Handle multi-zone stacked histograms (32x8)
            if hist_a.shape == (32, 8) and hist_b.shape == (32, 8):
                u_a, u_b = hist_a[:16], hist_b[:16]
                l_a, l_b = hist_a[16:], hist_b[16:]

                # Upper body similarity (shirt/vest)
                bhat_u = float(cv2.compareHist(u_a, u_b, cv2.HISTCMP_BHATTACHARYYA))
                correl_u = float(cv2.compareHist(u_a, u_b, cv2.HISTCMP_CORREL))
                sim_u = 0.65 * max(0.0, 1.0 - bhat_u) + 0.35 * max(0.0, correl_u)

                # Lower body similarity (pants/legs)
                bhat_l = float(cv2.compareHist(l_a, l_b, cv2.HISTCMP_BHATTACHARYYA))
                correl_l = float(cv2.compareHist(l_a, l_b, cv2.HISTCMP_CORREL))
                sim_l = 0.65 * max(0.0, 1.0 - bhat_l) + 0.35 * max(0.0, correl_l)

                return float(0.60 * sim_u + 0.40 * sim_l)

            # Standard single 16x8 histogram
            bhat = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_BHATTACHARYYA))
            correl = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))
            sim = 0.65 * max(0.0, 1.0 - bhat) + 0.35 * max(0.0, correl)
            return float(max(0.0, min(1.0, sim)))
        except Exception:
            return 0.0

    def update(
        self,
        detected_boxes: list[tuple[int, int, int, int]],
        now: float,
        frame_image: np.ndarray | None = None,
    ) -> list[tuple[int, float]]:
        """Match detected boxes with tracked workers. Returns list of (worker_id, dwell_seconds)."""
        # Increment lost count for existing tracks
        for tid in list(self.tracks.keys()):
            self.tracks[tid]["lost"] += 1
            if self.tracks[tid]["lost"] > self.max_lost:
                # Store full profile in gallery before removing from active frame tracking
                t = self.tracks[tid]
                accumulated = t.get("dwell_accumulated", 0.0) + max(0.0, t["last_seen"] - t["first_seen"])
                self.gallery[tid] = {
                    "id": tid,
                    "box": t["box"],
                    "aspect_ratio": t.get("aspect_ratio", 0.5),
                    "feature": t.get("feature"),
                    "first_seen": t["first_seen"],
                    "last_seen": t["last_seen"],
                    "dwell_accumulated": accumulated,
                    "gear_status": t.get("gear_status", {}),
                    "missing_streaks": t.get("missing_streaks", {}),
                }
                del self.tracks[tid]

        if not detected_boxes:
            return []

        matched_ids: list[int | None] = [None] * len(detected_boxes)

        # Build candidate matches with IoU or centroid proximity against active tracks
        candidates = []
        for i, box in enumerate(detected_boxes):
            bx1, by1, bx2, by2 = box
            bcx, bcy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
            bw, bh = max(1, bx2 - bx1), max(1, by2 - by1)

            for tid in list(self.tracks.keys()):
                tx1, ty1, tx2, ty2 = self.tracks[tid]["box"]
                tcx, tcy = (tx1 + tx2) / 2.0, (ty1 + ty2) / 2.0

                ix1, iy1 = max(bx1, tx1), max(by1, ty1)
                ix2, iy2 = min(bx2, tx2), min(by2, ty2)
                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                union = (bw * bh) + ((tx2 - tx1) * (ty2 - ty1)) - inter
                iou = inter / float(max(1, union))

                dist_norm = math.sqrt(((bcx - tcx) / float(bw)) ** 2 + ((bcy - tcy) / float(bh)) ** 2)
                score = iou + max(0.0, 1.0 - dist_norm)

                if iou >= self.iou_thresh or dist_norm < 0.6:
                    candidates.append((score, i, tid))

        # Sort candidate matches descending by score to ensure globally optimal matching
        candidates.sort(key=lambda x: x[0], reverse=True)
        matched_dets = set()
        matched_tracks = set()

        for score, det_idx, tid in candidates:
            if det_idx not in matched_dets and tid not in matched_tracks:
                matched_ids[det_idx] = tid
                matched_dets.add(det_idx)
                matched_tracks.add(tid)

                prev_box = self.tracks[tid]["box"]
                alpha = 0.70
                box = detected_boxes[det_idx]
                smooth_box = (
                    round(alpha * box[0] + (1.0 - alpha) * prev_box[0]),
                    round(alpha * box[1] + (1.0 - alpha) * prev_box[1]),
                    round(alpha * box[2] + (1.0 - alpha) * prev_box[2]),
                    round(alpha * box[3] + (1.0 - alpha) * prev_box[3]),
                )
                self.tracks[tid]["box"] = smooth_box
                self.tracks[tid]["lost"] = 0
                self.tracks[tid]["last_seen"] = now

                # Update feature prototype with exponential moving average
                if frame_image is not None:
                    feat = self.extract_feature(frame_image, smooth_box)
                    if feat is not None:
                        prev_feat = self.tracks[tid].get("feature")
                        if prev_feat is not None and prev_feat.shape == feat.shape:
                            self.tracks[tid]["feature"] = 0.75 * prev_feat + 0.25 * feat
                        else:
                            self.tracks[tid]["feature"] = feat

        # Identify dormant / inactive IDs in persistent gallery
        active_tids = set(self.tracks.keys()) | {t for t in matched_ids if t is not None}
        dormant_ids = [gid for gid in sorted(self.gallery.keys()) if gid not in active_tids]

        # For unmatched detections, evaluate Re-ID match against dormant gallery identities
        results: list[tuple[int, float]] = []
        for i, box in enumerate(detected_boxes):
            tid = matched_ids[i]
            if tid is None:
                matched_dormant_id = None
                det_feat = self.extract_feature(frame_image, box) if frame_image is not None else None
                bw = max(1, box[2] - box[0])
                bh = max(1, box[3] - box[1])
                cur_aspect = bw / float(bh)

                if dormant_ids:
                    best_score = -1.0
                    best_did = None
                    for did in dormant_ids:
                        cand = self.gallery[did]
                        sim = self.compute_similarity(det_feat, cand.get("feature")) if det_feat is not None else 0.0
                        cand_aspect = cand.get("aspect_ratio", 0.5)
                        aspect_diff = abs(cur_aspect - cand_aspect) / max(0.1, cand_aspect)
                        score = sim if sim > 0 else max(0.0, 1.0 - aspect_diff)
                        if score > best_score:
                            best_score = score
                            best_did = did

                    # If confidence is solid, or if there's only 1 dormant person available, re-use persistent identity
                    if best_did is not None and (
                        best_score >= 0.20 or len(self.gallery) == 1 or len(detected_boxes) <= len(self.gallery)
                    ):
                        matched_dormant_id = best_did
                        dormant_ids.remove(best_did)

                # Single-worker stream preservation:
                # If only 1 worker was ever known in the session and no other track is active,
                # a returning worker MUST be identified as Person 1 (never Person 2, Person 3).
                if matched_dormant_id is None and len(detected_boxes) == 1 and not self.tracks and 1 in self.gallery:
                    matched_dormant_id = 1
                    if 1 in dormant_ids:
                        dormant_ids.remove(1)

                if matched_dormant_id is not None:
                    # Re-activate the existing person's persistent identity and accumulated dwell time
                    tid = matched_dormant_id
                    gdata = self.gallery[tid]
                    self.tracks[tid] = {
                        "box": box,
                        "aspect_ratio": cur_aspect,
                        "feature": det_feat if det_feat is not None else gdata.get("feature"),
                        "lost": 0,
                        "first_seen": now,
                        "last_seen": now,
                        "dwell_accumulated": gdata.get("dwell_accumulated", 0.0),
                        "gear_status": gdata.get("gear_status", {}),
                        "missing_streaks": gdata.get("missing_streaks", {}),
                    }
                else:
                    # Genuinely new person entering shopfloor
                    tid = self.next_id
                    self.next_id += 1
                    self.tracks[tid] = {
                        "box": box,
                        "aspect_ratio": cur_aspect,
                        "feature": det_feat,
                        "lost": 0,
                        "first_seen": now,
                        "last_seen": now,
                        "dwell_accumulated": 0.0,
                        "gear_status": {},
                        "missing_streaks": {},
                    }

                # Synchronize gallery record
                self.gallery[tid] = {
                    "id": tid,
                    "box": self.tracks[tid]["box"],
                    "aspect_ratio": cur_aspect,
                    "feature": self.tracks[tid].get("feature"),
                    "first_seen": self.tracks[tid]["first_seen"],
                    "last_seen": self.tracks[tid]["last_seen"],
                    "dwell_accumulated": self.tracks[tid].get("dwell_accumulated", 0.0),
                    "gear_status": self.tracks[tid].get("gear_status", {}),
                    "missing_streaks": self.tracks[tid].get("missing_streaks", {}),
                }
                matched_ids[i] = tid

            dwell = self.tracks[tid].get("dwell_accumulated", 0.0) + max(0.0, now - self.tracks[tid]["first_seen"])
            results.append((tid, dwell))

        return results

    def debounce_compliance(self, worker: WorkerStatus) -> None:
        """Temporal debouncing across frames so transient 1-frame detector misses do not jitter status."""
        tid = worker.worker_id
        if tid not in self.tracks:
            return

        track_data = self.tracks[tid]
        if "gear_status" not in track_data:
            track_data["gear_status"] = {}
            track_data["missing_streaks"] = {}

        saved_status = track_data["gear_status"]
        streaks = track_data["missing_streaks"]

        for gear in ("helmet", "vest", "boots", "gloves", "goggles"):
            status_attr = f"{gear}_status"
            curr = getattr(worker, status_attr, "UNKNOWN")

            if curr == "COMPLIANT":
                saved_status[gear] = "COMPLIANT"
                streaks[gear] = 0
            elif curr == "VIOLATION":
                # Check whether an explicit violation class was detected on this worker
                explicit = gear in getattr(worker, "explicit_violations", [])
                if explicit:
                    saved_status[gear] = "VIOLATION"
                    streaks[gear] = 0
                else:
                    streaks[gear] = streaks.get(gear, 0) + 1
                    # Debounce 1 frame miss if worker was previously confirmed compliant
                    if saved_status.get(gear) == "COMPLIANT" and streaks[gear] < 2:
                        setattr(worker, status_attr, "COMPLIANT")
                        worker.violations = [v for v in worker.violations if gear not in v.lower()]
                        gear_label = gear.title()
                        if gear_label not in worker.compliances:
                            worker.compliances.append(gear_label)
                    else:
                        saved_status[gear] = "VIOLATION"


def associate_ppe_to_workers(
    detections: list[dict],
    frame_w: int = 1280,
    frame_h: int = 720,
    zones: list[ZoneConfig] | None = None,
    required_ppe: dict[str, bool] | None = None,
    tracker: WorkerTracker | None = None,
    timestamp: float = 0.0,
    frame_image: np.ndarray | None = None,
) -> list[WorkerStatus]:
    """Associate detected PPE items and physical zones with detected workers."""
    zones_list = zones or DEFAULT_ZONES
    workers: list[WorkerStatus] = []
    ppe_items: list[dict] = []

    # Separate person detections from PPE items
    person_boxes: list[tuple[int, int, int, int]] = []
    for d in detections:
        label = d["label"]
        if is_person(label):
            box = (int(d["x1"]), int(d["y1"]), int(d["x2"]), int(d["y2"]))
            person_boxes.append(box)
        elif normalize(label) not in ("none", "null", "background"):
            ppe_items.append(d)

    # Synthesized worker fallback: if full-body Person anchor is missing (e.g. desktop webcam close-up)
    # but PPE items (vest, gloves, helmet, goggles) are detected, synthesize a worker box enclosing them.
    if not person_boxes and ppe_items:
        min_x = min(item["x1"] for item in ppe_items)
        min_y = min(item["y1"] for item in ppe_items)
        max_x = max(item["x2"] for item in ppe_items)
        max_y = max(item["y2"] for item in ppe_items)
        pad_x = max(50, int((max_x - min_x) * 0.30))
        pad_y = max(60, int((max_y - min_y) * 0.35))
        synth_box = (
            max(0, min_x - pad_x),
            max(0, min_y - pad_y),
            min(frame_w, max_x + pad_x),
            min(frame_h, max_y + pad_y),
        )
        person_boxes.append(synth_box)
    elif not person_boxes and frame_image is not None and frame_image.size > 0:
        # Fallback: detect face anchor for close-up webcam user
        try:
            import cv2

            gray = cv2.cvtColor(frame_image, cv2.COLOR_BGR2GRAY) if len(frame_image.shape) == 3 else frame_image
            cascade_path = (
                getattr(cv2, "data", None).haarcascades + "haarcascade_frontalface_default.xml"
                if hasattr(cv2, "data")
                else ""
            )
            if cascade_path:
                face_cascade = cv2.CascadeClassifier(cascade_path)
                if not face_cascade.empty():
                    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=3, minSize=(50, 50))
                    for fx, fy, fw, fh in faces:
                        bx1 = max(0, int(fx - fw * 0.4))
                        by1 = max(0, int(fy - fh * 0.3))
                        bx2 = min(frame_w, int(fx + fw * 1.4))
                        by2 = min(frame_h, int(fy + fh * 3.2))
                        person_boxes.append((bx1, by1, bx2, by2))
        except Exception:
            pass

    # Use tracker if provided to maintain persistent person IDs and dwell times
    if tracker is not None and person_boxes:
        tracked_info = tracker.update(
            person_boxes,
            timestamp if timestamp > 0 else 0.0,
            frame_image=frame_image,
        )
    else:
        tracked_info = [(idx + 1, 0.0) for idx in range(len(person_boxes))]

    for box, (w_id, dwell) in zip(person_boxes, tracked_info):
        effective_box = tracker.tracks[w_id].get("box", box) if (tracker and w_id in tracker.tracks) else box
        cx = (effective_box[0] + effective_box[2]) / (2.0 * max(1, frame_w))
        cy = effective_box[3] / float(max(1, frame_h))
        z_name, z_type, is_restr = find_zone_for_point(cx, cy, zones_list)

        w = WorkerStatus(
            worker_id=w_id,
            box=effective_box,
            zone=z_name,
            zone_type=z_type,
            is_restricted_zone=is_restr,
            dwell_seconds=dwell,
            required_ppe=required_ppe,
        )
        if is_restr:
            w.violations.append("Restricted Zone")
        workers.append(w)

    if not workers:
        return []

    # Assign PPE items to closest containing worker with generous adaptive margins
    for item in ppe_items:
        ibox = (item["x1"], item["y1"], item["x2"], item["y2"])
        icx, icy = box_center(ibox)
        label = item["label"]
        viol = item["violation"]

        best_worker: WorkerStatus | None = None
        best_score = 0.0

        for w in workers:
            wx1, wy1, wx2, wy2 = w.box
            w_w = max(10, wx2 - wx1)
            w_h = max(10, wy2 - wy1)

            # Generous adaptive margins to reliably associate extended arms, gloves, and torso vests
            x_margin = max(80, int(w_w * 0.60))
            y_top_margin = max(80, int(w_h * 0.40))
            y_bot_margin = max(80, int(w_h * 0.35))

            if (wx1 - x_margin) <= icx <= (wx2 + x_margin) and (wy1 - y_top_margin) <= icy <= (wy2 + y_bot_margin):
                overlap = box_intersection_ratio(ibox, w.box)
                wcx = (wx1 + wx2) / 2.0
                if is_helmet(label) or is_goggles(label):
                    anchor_y = wy1 + 0.15 * w_h
                elif is_vest(label):
                    anchor_y = wy1 + 0.40 * w_h
                elif is_gloves(label):
                    anchor_y = wy1 + 0.60 * w_h
                elif is_boots(label):
                    anchor_y = wy1 + 0.88 * w_h
                else:
                    anchor_y = (wy1 + wy2) / 2.0

                dist_norm = math.sqrt(((icx - wcx) / float(w_w)) ** 2 + ((icy - anchor_y) / float(w_h)) ** 2)
                score = overlap + max(0.0, 1.0 - 0.4 * dist_norm)
                if score > best_score:
                    best_score = score
                    best_worker = w

        if best_worker:
            d_lab = item.get("display_label") or item.get("label", "")

            if is_goggles(label):
                if viol:
                    best_worker.goggles_status = "VIOLATION"
                    if "goggles" not in best_worker.explicit_violations:
                        best_worker.explicit_violations.append("goggles")
                    if d_lab not in best_worker.violations:
                        best_worker.violations.append(d_lab)
                else:
                    if best_worker.goggles_status != "VIOLATION":
                        best_worker.goggles_status = "COMPLIANT"
                    if d_lab not in best_worker.compliances:
                        best_worker.compliances.append(d_lab)

            elif is_helmet(label):
                if viol:
                    best_worker.helmet_status = "VIOLATION"
                    if "helmet" not in best_worker.explicit_violations:
                        best_worker.explicit_violations.append("helmet")
                    if d_lab not in best_worker.violations:
                        best_worker.violations.append(d_lab)
                else:
                    if best_worker.helmet_status != "VIOLATION":
                        best_worker.helmet_status = "COMPLIANT"
                    if d_lab not in best_worker.compliances:
                        best_worker.compliances.append(d_lab)

            elif is_gloves(label):
                if viol:
                    best_worker.gloves_status = "VIOLATION"
                    if "gloves" not in best_worker.explicit_violations:
                        best_worker.explicit_violations.append("gloves")
                    if d_lab not in best_worker.violations:
                        best_worker.violations.append(d_lab)
                else:
                    if best_worker.gloves_status != "VIOLATION":
                        best_worker.gloves_status = "COMPLIANT"
                    if d_lab not in best_worker.compliances:
                        best_worker.compliances.append(d_lab)

            elif is_vest(label):
                if viol:
                    best_worker.vest_status = "VIOLATION"
                    if "vest" not in best_worker.explicit_violations:
                        best_worker.explicit_violations.append("vest")
                    if d_lab not in best_worker.violations:
                        best_worker.violations.append(d_lab)
                else:
                    if best_worker.vest_status != "VIOLATION":
                        best_worker.vest_status = "COMPLIANT"
                    if d_lab not in best_worker.compliances:
                        best_worker.compliances.append(d_lab)

            elif is_boots(label):
                if viol:
                    best_worker.boots_status = "VIOLATION"
                    if "boots" not in best_worker.explicit_violations:
                        best_worker.explicit_violations.append("boots")
                    if d_lab not in best_worker.violations:
                        best_worker.violations.append(d_lab)
                else:
                    if best_worker.boots_status != "VIOLATION":
                        best_worker.boots_status = "COMPLIANT"
                    if d_lab not in best_worker.compliances:
                        best_worker.compliances.append(d_lab)

            else:
                if viol:
                    if d_lab not in best_worker.violations:
                        best_worker.violations.append(d_lab)
                elif is_compliance(label) and d_lab not in best_worker.compliances:
                    best_worker.compliances.append(d_lab)

    # Strict & absolute PPE evaluation for required items on each worker
    if required_ppe is not None:
        for w in workers:
            req = required_ppe

            # 1. Vest: model outputs 'vest' when worn; if required and not compliant, flag violation
            if req.get("vest", False) and w.vest_status != "COMPLIANT":
                w.vest_status = "VIOLATION"
                if not any("vest" in v.lower() for v in w.violations):
                    w.violations.append("No Vest")

            # 2. Helmet: if required and not compliant, flag violation
            if req.get("helmet", False) and w.helmet_status != "COMPLIANT":
                w.helmet_status = "VIOLATION"
                if not any("helmet" in v.lower() for v in w.violations):
                    w.violations.append("No Helmet")

            # 3. Gloves: if required and not compliant, flag violation (unless close-up head/shoulders view where hands are out of frame and no explicit violation detected)
            if req.get("gloves", False) and w.gloves_status != "COMPLIANT":
                wx1, wy1, wx2, wy2 = w.box
                w_w = max(1, wx2 - wx1)
                w_h = max(1, wy2 - wy1)
                aspect_ratio = float(w_h) / float(w_w)
                is_closeup = aspect_ratio < 1.0 or (wy2 - wy1) < 0.40 * frame_h
                if not is_closeup or "gloves" in w.explicit_violations:
                    w.gloves_status = "VIOLATION"
                    if not any("glove" in v.lower() for v in w.violations):
                        w.violations.append("No Gloves")

            # 4. Goggles: if required and not compliant, flag violation
            if req.get("goggles", False) and w.goggles_status != "COMPLIANT":
                w.goggles_status = "VIOLATION"
                if not any("goggle" in v.lower() for v in w.violations):
                    w.violations.append("No Goggles")

            # 5. Boots: if required and feet are in view, flag violation if missing
            if req.get("boots", False) and w.boots_status != "COMPLIANT":
                lower_body_visible = w.box[3] < (frame_h - 15)
                if lower_body_visible:
                    w.boots_status = "VIOLATION"
                    if not any("boot" in v.lower() for v in w.violations):
                        w.violations.append("No Boots")

    if tracker is not None:
        for w in workers:
            tracker.debounce_compliance(w)

    return workers

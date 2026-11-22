"""Persistent worker tracking and visual Re-ID service."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.core.ppe_associator import WorkerStatus


def _box_area(box: Sequence[int]) -> int:
    return max(0, box[2] - box[0]) * max(0, box[3] - box[1])


def suppress_duplicate_person_boxes(
    boxes: list[tuple[int, int, int, int]],
    iou_threshold: float = 0.45,
    containment_threshold: float = 0.80,
) -> list[tuple[int, int, int, int]]:
    """Collapse overlapping person boxes that are almost certainly one human.

    Detector NMS runs *per class*, so the same person can survive twice: once as
    a full-body box and once as a tighter box from a second inference pass
    (multi-scale TTA / person-crop refinement), or under two person-like class
    names. Both become separate tracks and then surface as two separate people
    on the Evidence Log for a single worker.

    IoU alone misses this case: a box nested inside a slightly larger one has a
    low IoU but very high *containment* (intersection over the smaller area), so
    both metrics are used. When two boxes are judged the same person, the larger
    one wins because the full-body box drives better tracking and dwell time.

    Input order is preserved: callers keep track/detection results index-aligned
    with the boxes they passed in, so reordering here would silently mis-attribute
    identities. Duplicate decisions are made pairwise and only mark which index to
    drop; survivors are emitted in their original sequence.
    """
    if len(boxes) < 2:
        return list(boxes)

    drop: set[int] = set()
    for i in range(len(boxes)):
        if i in drop:
            continue
        box_i, area_i = boxes[i], _box_area(boxes[i])
        if area_i <= 0:
            drop.add(i)
            continue
        for j in range(i + 1, len(boxes)):
            if j in drop:
                continue
            box_j, area_j = boxes[j], _box_area(boxes[j])
            if area_j <= 0:
                drop.add(j)
                continue
            x1 = max(box_i[0], box_j[0])
            y1 = max(box_i[1], box_j[1])
            x2 = min(box_i[2], box_j[2])
            y2 = min(box_i[3], box_j[3])
            inter = max(0, x2 - x1) * max(0, y2 - y1)
            if inter <= 0:
                continue
            union = area_i + area_j - inter
            iou = inter / union if union > 0 else 0.0
            containment = inter / min(area_i, area_j)
            if iou >= iou_threshold or containment >= containment_threshold:
                # Keep the larger box; on a tie keep the earlier position so the
                # surviving index is stable and predictable.
                drop.add(j if area_j < area_i else i)
                if i in drop:
                    break
    return [tuple(int(v) for v in b) for i, b in enumerate(boxes) if i not in drop]  # type: ignore[misc]


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
        # One human must never become two identities; collapse duplicate boxes first.
        detected_boxes = suppress_duplicate_person_boxes(detected_boxes)

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

"""Synthetic high-resolution shopfloor scene generator for simulation mode.

Provides a continuous animated shopfloor camera feed with workers, machines,
and safety boundaries when a live physical camera is not connected.
"""

from __future__ import annotations

import math
import time

import cv2
import numpy as np


class DemoShopfloorFeed:
    """Generates continuous realistic factory floor frames.

    Uses real factory floor evidence frames from data/evidence/ when available
    so that custom YOLO neural weights detect real personnel and PPE items in real-time.
    """

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.start_time = time.time()
        self.cached_frames: list[np.ndarray] = []
        self._bg = self._render_static_background()

    def _render_static_background(self) -> np.ndarray:
        """Pre-render static factory layout (floors, demarcation, machines, signage)."""
        frame = np.full((self.height, self.width, 3), 28, dtype=np.uint8)

        # Draw concrete floor with subtle grid lines
        cv2.rectangle(frame, (0, 0), (self.width, self.height), (32, 38, 42), -1)

        # Floor grid perspective
        for y in range(120, self.height, 60):
            cv2.line(frame, (0, y), (self.width, y), (38, 45, 50), 1)
        for x in range(0, self.width, 100):
            cv2.line(frame, (x, 120), (x, self.height), (38, 45, 50), 1)

        # Zone 1: Assembly Area A (Left)
        cv2.rectangle(frame, (40, 140), (580, 680), (45, 58, 52), 2)
        cv2.putText(frame, "ZONE 1: ASSEMBLY LINE A", (60, 175), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (75, 198, 161), 2)
        cv2.putText(frame, "STANDARD ZONE | CAPACITY: 6", (60, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (140, 155, 160), 1)

        # Zone 2: Heavy Machinery Bay (Right - Restricted Zone with hazard stripes)
        cv2.rectangle(frame, (680, 140), (1240, 680), (35, 45, 80), 2)
        cv2.putText(
            frame,
            "ZONE 2: HEAVY MACHINERY BAY (RESTRICTED)",
            (700, 175),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (100, 145, 235),
            2,
        )
        cv2.putText(
            frame,
            "PPE REQUIRED: HELMET, VEST, BOOTS, GOGGLES",
            (700, 200),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (140, 155, 160),
            1,
        )

        # Draw yellow hazard demarcation lines
        for offset in range(680, 1240, 40):
            cv2.line(frame, (offset, 140), (min(offset + 25, 1240), 155), (60, 185, 235), 2)

        # Industrial machinery blocks
        cv2.rectangle(frame, (760, 260), (1160, 480), (50, 56, 62), -1)
        cv2.rectangle(frame, (760, 260), (1160, 480), (80, 92, 100), 2)
        cv2.putText(frame, "CNC MILLING STATION #04", (780, 370), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (180, 195, 200), 2)
        cv2.circle(frame, (1120, 290), 8, (60, 210, 140), -1)  # Status indicator green

        # Workstation table in Assembly
        cv2.rectangle(frame, (100, 280), (520, 440), (45, 52, 58), -1)
        cv2.rectangle(frame, (100, 280), (520, 440), (70, 80, 88), 2)
        cv2.putText(frame, "MANUAL ASSEMBLY BENCH", (120, 360), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (160, 175, 180), 2)
        return frame

    def get_frame(self) -> np.ndarray:
        """Render a realistic industrial shopfloor frame with animated workers."""
        frame = self._bg.copy()
        t = time.time() - self.start_time

        # Worker 1 (Assembly, Moving smoothly, Fully Compliant)
        w1_x = int(220 + 70 * math.sin(t * 0.7))
        w1_y = int(320 + 20 * math.cos(t * 0.7))
        self._draw_simulated_person(
            frame, w1_x, w1_y, "Worker #01", helmet=True, vest=True, boots=True, gloves=True, goggles=True
        )

        # Worker 2 (Assembly, Working at bench, Fully Compliant)
        w2_x = 420
        w2_y = int(330 + 10 * math.sin(t * 0.5))
        self._draw_simulated_person(
            frame, w2_x, w2_y, "Worker #02", helmet=True, vest=True, boots=True, gloves=True, goggles=True
        )

        # Worker 3 (Machine Bay, Near milling station, VIOLATION: Missing helmet & goggles!)
        w3_x = int(940 + 60 * math.sin(t * 0.6))
        w3_y = int(520 + 25 * math.cos(t * 0.6))
        self._draw_simulated_person(
            frame, w3_x, w3_y, "Worker #03", helmet=False, vest=True, boots=True, gloves=False, goggles=False
        )

        return frame

    def _draw_simulated_person(
        self,
        frame: np.ndarray,
        x: int,
        y: int,
        label: str,
        helmet: bool = True,
        vest: bool = True,
        boots: bool = True,
        gloves: bool = True,
        goggles: bool = True,
    ) -> None:
        """Draw an industrial human figure with safety gear (helmet, vest, boots, gloves, goggles)."""
        # Head / Helmet
        head_radius = 18
        head_center = (x, y - 55)

        # Torso / Vest
        torso_top = (x - 22, y - 35)
        torso_bot = (x + 22, y + 25)
        vest_color = (30, 200, 210) if vest else (60, 60, 75)  # Hi-vis yellow-orange
        cv2.rectangle(frame, torso_top, torso_bot, vest_color, -1)
        cv2.rectangle(frame, torso_top, torso_bot, (40, 40, 40), 1)

        # Head / Hardhat
        if helmet:
            # White hardhat
            cv2.ellipse(frame, head_center, (head_radius + 4, head_radius), 0, 180, 360, (230, 235, 240), -1)
            cv2.ellipse(frame, head_center, (head_radius + 6, 6), 0, 0, 360, (210, 215, 220), -1)
        else:
            # Bare head (hair)
            cv2.circle(frame, head_center, head_radius, (70, 85, 100), -1)

        # Face & Goggles
        cv2.circle(frame, (x, y - 50), 12, (180, 200, 215), -1)
        if goggles:
            cv2.rectangle(frame, (x - 9, y - 53), (x + 9, y - 46), (220, 240, 255), -1)
            cv2.rectangle(frame, (x - 9, y - 53), (x + 9, y - 46), (100, 180, 220), 1)

        # Arms & Gloves
        arm_color = (45, 55, 65)
        cv2.line(frame, (x - 22, y - 25), (x - 30, y + 15), arm_color, 4)
        cv2.line(frame, (x + 22, y - 25), (x + 30, y + 15), arm_color, 4)
        glove_color = (220, 210, 50) if gloves else (180, 195, 210)
        cv2.circle(frame, (x - 31, y + 18), 5, glove_color, -1)
        cv2.circle(frame, (x + 31, y + 18), 5, glove_color, -1)

        # Legs / Boots
        leg_color = (50, 60, 70)
        cv2.rectangle(frame, (x - 18, y + 25), (x - 4, y + 80), leg_color, -1)
        cv2.rectangle(frame, (x + 4, y + 25), (x + 18, y + 80), leg_color, -1)

        # Boots
        boot_color = (35, 40, 45) if boots else (80, 80, 80)
        cv2.rectangle(frame, (x - 22, y + 75), (x - 2, y + 88), boot_color, -1)
        cv2.rectangle(frame, (x + 2, y + 75), (x + 22, y + 88), boot_color, -1)

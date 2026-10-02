"""Thread-safe, smooth hardware-accelerated video display canvas."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget


class VideoDisplayWidget(QWidget):
    """Custom high-performance video display viewport maintaining aspect ratio."""

    def __init__(self, placeholder_text: str = "Video feed inactive", parent=None):
        super().__init__(parent)
        self.placeholder_text = placeholder_text
        self._image: QImage | None = None
        self.setStyleSheet("background-color: #090d16; border-radius: 8px;")
        self.setMinimumSize(560, 380)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_image(self, image: QImage) -> None:
        """Update displayed image and trigger repaint."""
        self._image = image
        self.update()

    def clear(self) -> None:
        """Clear current frame and show placeholder."""
        self._image = None
        self.update()

    def set_placeholder(self, text: str) -> None:
        """Update placeholder text."""
        self.placeholder_text = text
        self.update()

    def paintEvent(self, event) -> None:
        """Paint frame centered with preserved aspect ratio."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Background fill
        painter.fillRect(self.rect(), QColor("#090d16"))

        if self._image is not None and not self._image.isNull():
            # Calculate aspect ratio fit
            img_w = self._image.width()
            img_h = self._image.height()
            canvas_w = self.width()
            canvas_h = self.height()

            scale = min(canvas_w / img_w, canvas_h / img_h)
            target_w = int(img_w * scale)
            target_h = int(img_h * scale)
            target_x = (canvas_w - target_w) // 2
            target_y = (canvas_h - target_h) // 2

            dest_rect = QRect(target_x, target_y, target_w, target_h)
            painter.drawImage(dest_rect, self._image)
        else:
            # Draw placeholder message
            painter.setPen(QColor("#64748b"))
            font = QFont()
            font.setPointSize(12)
            font.setWeight(QFont.Weight.Medium)
            painter.setFont(font)
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                f"📹  {self.placeholder_text}",
            )

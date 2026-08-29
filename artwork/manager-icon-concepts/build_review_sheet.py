"""Compose the generated icon concepts into one lossless review sheet."""

from pathlib import Path
import sys

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen


ROOT = Path(__file__).resolve().parent
CONCEPTS = (
    ("01-royal-scribe.png", "1  Royal Scribe"),
    ("02-arcane-convergence.png", "2  Arcane Convergence"),
    ("03-builders-keep.png", "3  Builder's Keep"),
    ("04-royal-mod-chest.png", "4  Royal Mod Chest"),
    ("05-royal-astrolabe.png", "5  Royal Astrolabe"),
)


def main() -> None:
    application = QGuiApplication.instance() or QGuiApplication(sys.argv)
    canvas = QImage(900, 650, QImage.Format.Format_ARGB32)
    canvas.fill(QColor("#12100c"))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))

    cells = (
        QRect(25, 25, 270, 285),
        QRect(315, 25, 270, 285),
        QRect(605, 25, 270, 285),
        QRect(170, 335, 270, 285),
        QRect(460, 335, 270, 285),
    )
    for (filename, label), cell in zip(CONCEPTS, cells):
        painter.setPen(QPen(QColor("#5a482b"), 2))
        painter.setBrush(QColor("#1b1814"))
        painter.drawRoundedRect(cell, 10, 10)
        source = QImage(str(ROOT / filename))
        icon = source.scaled(
            220,
            220,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = cell.x() + (cell.width() - icon.width()) // 2
        y = cell.y() + 14 + (220 - icon.height()) // 2
        painter.drawImage(x, y, icon)
        painter.setPen(QColor("#f2ddad"))
        painter.drawText(
            QRect(cell.x() + 8, cell.bottom() - 46, cell.width() - 16, 32),
            Qt.AlignmentFlag.AlignCenter,
            label,
        )
    painter.end()
    if not canvas.save(str(ROOT / "manager-icon-concepts-review.png"), "PNG"):
        raise RuntimeError("Could not save the icon review sheet")
    del application


if __name__ == "__main__":
    main()

"""Build the manager's Windows icon from its project-owned PNG source."""

from __future__ import annotations

from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage


ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _png_bytes(image: QImage) -> bytes:
    payload = QByteArray()
    buffer = QBuffer(payload)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise RuntimeError("Could not open the in-memory icon buffer.")
    if not image.save(buffer, "PNG"):
        raise RuntimeError("Qt could not encode an icon frame as PNG.")
    buffer.close()
    return bytes(payload)


def build_icon(source_path: Path, png_path: Path, ico_path: Path) -> None:
    source = QImage(str(source_path))
    if source.isNull():
        raise RuntimeError(f"Could not read icon source: {source_path}")

    frames: list[tuple[int, bytes]] = []
    for size in ICON_SIZES:
        scaled = source.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        frames.append((size, _png_bytes(scaled)))

    png_path.parent.mkdir(parents=True, exist_ok=True)
    preview = source.scaled(
        256,
        256,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if not preview.save(str(png_path), "PNG"):
        raise RuntimeError(f"Could not write manager icon PNG: {png_path}")

    header_size = 6 + (16 * len(frames))
    offset = header_size
    directory = bytearray(struct.pack("<HHH", 0, 1, len(frames)))
    payloads = bytearray()
    for size, payload in frames:
        dimension = 0 if size == 256 else size
        directory.extend(
            struct.pack(
                "<BBBBHHII",
                dimension,
                dimension,
                0,
                0,
                1,
                32,
                len(payload),
                offset,
            )
        )
        payloads.extend(payload)
        offset += len(payload)
    ico_path.write_bytes(directory + payloads)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    asset_root = repo_root / "src" / "majesty_cam" / "manager" / "assets"
    build_icon(
        repo_root / "artwork" / "manager-icon-source.png",
        asset_root / "manager-icon.png",
        asset_root / "manager-icon.ico",
    )


if __name__ == "__main__":
    main()

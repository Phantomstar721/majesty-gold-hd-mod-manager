from __future__ import annotations

from pathlib import Path
import struct
import unittest


class ManagerIconAssetTests(unittest.TestCase):
    def test_windows_icon_contains_expected_png_frames(self) -> None:
        asset_root = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "majesty_cam"
            / "manager"
            / "assets"
        )
        payload = (asset_root / "manager-icon.ico").read_bytes()
        reserved, kind, count = struct.unpack_from("<HHH", payload)
        self.assertEqual((reserved, kind, count), (0, 1, 9))

        dimensions: list[int] = []
        for index in range(count):
            entry = struct.unpack_from("<BBBBHHII", payload, 6 + index * 16)
            width, height, _, _, planes, bits, length, offset = entry
            dimensions.append(256 if width == 0 else width)
            self.assertEqual(height, width)
            self.assertEqual((planes, bits), (1, 32))
            self.assertEqual(payload[offset : offset + 8], b"\x89PNG\r\n\x1a\n")
            self.assertLessEqual(offset + length, len(payload))
        self.assertEqual(dimensions, [16, 20, 24, 32, 40, 48, 64, 128, 256])

    def test_window_icon_png_has_transparency(self) -> None:
        try:
            from PySide6.QtGui import QImage
        except ImportError:
            self.skipTest("optional PySide6 desktop runtime is unavailable")
        asset = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "majesty_cam"
            / "manager"
            / "assets"
            / "manager-icon.png"
        )
        image = QImage(str(asset))
        self.assertFalse(image.isNull())
        self.assertEqual((image.width(), image.height()), (256, 256))
        self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)


if __name__ == "__main__":
    unittest.main()

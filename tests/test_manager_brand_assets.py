from pathlib import Path
import struct
import sys
import unittest
import zlib


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.brand_assets import (
    _HEADER,
    _decode_v1_embedded_palette,
    _decode_v1_external_palette,
    _decode_v1_rgb565,
    _png_rgba,
    _prepare_header_texture,
)


class ManagerBrandAssetTests(unittest.TestCase):
    def test_header_uses_stock_main_menu_study_with_versioned_cache_name(self):
        self.assertEqual(_HEADER.relative_cam, Path("DataMX/mx_interfacedata.cam"))
        self.assertEqual(_HEADER.tile_index, 580)
        self.assertEqual(_HEADER.output_name, "majesty-main-menu-header-v3.png")
        self.assertIsNone(_HEADER.relative_palette_cam)

    def test_decodes_strided_embedded_palette_with_transparency(self):
        palette = bytearray(1032)
        palette[8 + 4 : 8 + 7] = bytes((10, 20, 30))
        palette[8 + 8 : 8 + 11] = bytes((40, 50, 60))
        pixels = bytes((1, 2, 0, 2, 1, 0))
        header = bytearray(26)
        struct.pack_into("<HHHH", header, 0, 1, 2, 2, 3)
        struct.pack_into("<H", header, 16, 0)
        struct.pack_into("<H", header, 20, 1)
        struct.pack_into("<I", header, 22, 32)

        width, height, rgba = _decode_v1_embedded_palette(
            bytes(header) + pixels + bytes(palette)
        )

        self.assertEqual((width, height), (2, 2))
        self.assertEqual(
            rgba,
            bytes(
                (
                    10, 20, 30, 255,
                    40, 50, 60, 255,
                    40, 50, 60, 255,
                    10, 20, 30, 255,
                )
            ),
        )

    def test_png_encoder_writes_valid_rgba_scanline(self):
        encoded = _png_rgba(1, 1, bytes((1, 2, 3, 4)))
        self.assertTrue(encoded.startswith(b"\x89PNG\r\n\x1a\n"))
        idat = encoded.index(b"IDAT")
        length = struct.unpack_from(">I", encoded, idat - 4)[0]
        payload = encoded[idat + 4 : idat + 4 + length]
        self.assertEqual(zlib.decompress(payload), bytes((0, 1, 2, 3, 4)))

    def test_decodes_stock_style_external_palette(self):
        palette = bytearray(1032)
        palette[12:15] = bytes((20, 40, 60))
        header = bytearray(26)
        struct.pack_into("<HHHH", header, 0, 1, 1, 2, 2)
        struct.pack_into("<H", header, 16, 0)
        struct.pack_into("<H", header, 20, 0)
        struct.pack_into("<I", header, 22, 17)

        width, height, rgba = _decode_v1_external_palette(
            bytes(header) + bytes((1, 1)),
            bytes(palette),
        )

        self.assertEqual((width, height), (2, 1))
        self.assertEqual(rgba, bytes((20, 40, 60, 255)) * 2)

    def test_decodes_full_background_rgb565_without_dropping_black(self):
        header = bytearray(26)
        struct.pack_into("<HHHH", header, 0, 1, 1, 2, 4)
        # Black and full-bright RGB565 white.  Black is real menu background,
        # rather than sprite cutout transparency.
        pixels = struct.pack("<HH", 0x0000, 0xFFFF)

        width, height, rgba = _decode_v1_rgb565(bytes(header) + pixels)

        self.assertEqual((width, height), (2, 1))
        self.assertEqual(
            rgba,
            bytes((0, 0, 0, 255, 255, 255, 255, 255)),
        )

    def test_header_crop_mirrors_source_pixels_for_a_continuous_join(self):
        red = bytes((255, 0, 0, 255))
        green = bytes((0, 255, 0, 255))
        blue = bytes((0, 0, 255, 255))
        white = bytes((255, 255, 255, 255))

        width, height, rgba = _prepare_header_texture(
            2,
            2,
            red + green + blue + white,
            crop_height=1,
        )

        self.assertEqual((width, height), (4, 1))
        self.assertEqual(rgba, red + green + green + red)

    def test_menu_transparency_keeps_enclosed_palette_color(self):
        palette = bytearray(1032)
        palette[8:11] = bytes((70, 80, 90))
        palette[12:15] = bytes((10, 20, 30))
        pixels = bytearray((1,) * 25)
        pixels[0] = 0
        pixels[12] = 0
        header = bytearray(26)
        struct.pack_into("<HHHH", header, 0, 1, 5, 5, 5)
        struct.pack_into("<H", header, 16, 0)
        struct.pack_into("<H", header, 20, 1)
        struct.pack_into("<I", header, 22, 51)

        _width, _height, rgba = _decode_v1_embedded_palette(
            bytes(header) + bytes(pixels) + bytes(palette)
        )

        self.assertEqual(rgba[:4], bytes((0, 0, 0, 0)))
        center = (2 * 5 + 2) * 4
        self.assertEqual(rgba[center : center + 4], bytes((70, 80, 90, 255)))


if __name__ == "__main__":
    unittest.main()

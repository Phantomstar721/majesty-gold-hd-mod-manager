"""Exact-profile offline UI geometry and production toolbar guards."""
import hashlib
import os
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage


class CompactToolbarProfiles(unittest.TestCase):
    def test_exact_images_and_ui_guards(self):
        root = Path(__file__).parents[1]
        header = (root / "runtime/CompactToolbarDiagnostic.h").read_text()
        runtime = (root / "runtime/CompactSovereignToolbar.inl").read_text()
        helpers = [int(v,16) for v in re.search(r'helpRvas\[\]=\{([^}]+)',runtime)[1].split(',')]
        hashes = [int(v,16) for v in re.search(r'helpHashes\[\]=\{([^}]+)',runtime)[1].split(',')]
        rows = re.findall(r"\{0x([0-9a-f]+),\{([^}]+)\},0x([0-9a-f]+),0x([0-9a-f]+)\}", header)
        self.assertEqual(len(rows), 3)
        profiles = (
            ("PUBLIC", "255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4", 0x250211),
            ("BETA2", "05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82", 0x265671),
            ("GOG", "65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792", 0x265af1),
        )
        geometry = bytes.fromhex("8b56048b1a83c2048956048b2a83c2048956048d142903d82bd12bd8894704894f0889570c895f10")
        for index, (name, digest, address) in enumerate(profiles):
            with self.subTest(profile=name):
                value = os.environ.get("MAJESTY_" + name + "_EXE")
                self.assertTrue(value, name + " executable fixture required")
                self.assertEqual(hashlib.sha256(Path(value).read_bytes()).hexdigest(), digest)
                image = PeImage(value)
                # Root token 2 consumes width/height and writes owner x/y/h/w;
                # negative centering coordinates are values, not sentinels.
                self.assertEqual(image.read(address, len(geometry)), geometry)
                table, slots, event_hash, setup_hash = rows[index]
                slots = [int(v, 16) for v in slots.split(",")]
                # The original compact hover's last direct call owns the helper.
                hover = image.read(slots[2], 0x45)
                self.assertEqual(hover[0x34], 0xe8)
                self.assertEqual(slots[2]+0x39+struct.unpack_from('<i',hover,0x35)[0], helpers[index])
                result = 2166136261
                for byte in image.read(helpers[index], 0xf0):
                    result = ((result ^ byte) * 16777619) & 0xffffffff
                self.assertEqual(result, hashes[index])
                self.assertEqual(struct.unpack("<9I", image.read(int(table, 16), 36)),
                                 tuple(0x400000 + v for v in slots))
                for slot, size, expected in ((1, 0x89, setup_hash), (8, 0x43, event_hash)):
                    result = 2166136261
                    for byte in image.read(slots[slot], size):
                        result = ((result ^ byte) * 16777619) & 0xffffffff
                    self.assertEqual(result, int(expected, 16))

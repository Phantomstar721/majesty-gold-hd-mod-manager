"""Read-only checks of each installed beta2 equipment registration boundary."""
import os
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage


class EquipmentRuntimeProfileTests(unittest.TestCase):
    def test_all_install_guards_match_beta2(self):
        path = os.environ.get("MAJESTY_BETA2_EXE")
        if not path:
            self.skipTest("MAJESTY_BETA2_EXE is not set")
        image = PeImage(path)
        source = (Path(__file__).resolve().parents[1] / "runtime/EquipmentRuntime.cpp").read_text()
        for rva, raw, count in re.findall(r'!Bytes\((0x[0-9A-F]+), "([^"]+)", (\d+)\)', source):
            expected = bytes(int(value, 16) for value in re.findall(r'\\x([0-9a-f]{2})', raw))
            self.assertEqual(len(expected), int(count))
            self.assertEqual(image.read(int(rva, 16), int(count)), expected, rva)
        for rva, target in re.findall(r'!Call\((0x[0-9A-F]+), (0x[0-9A-F]+)\)', source):
            self.assertEqual(image.target(int(rva, 16)), int(target, 16), rva)
        for rva, target in re.findall(r'!Pointer\((0x[0-9A-F]+), (0x[0-9A-F]+)\)', source):
            self.assertEqual(struct.unpack("<I", image.read(int(rva, 16), 4))[0], image.base + int(target, 16), rva)
        # Literal stock frame-zero overflow; no runtime patch is needed here.
        self.assertEqual(image.read(0x287A39, 7), bytes.fromhex("c7 45 1c 00 00 00 00"))

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import os
import unittest
import struct

from majesty_cam.manager.quest_dataset import (
    ENVIRONMENT, configure_launch, enabled, set_enabled,
)


class QuestDatasetTests(unittest.TestCase):
    def test_stock_and_expansion_launch_views(self):
        with TemporaryDirectory() as directory:
            paths = SimpleNamespace(profile_path=Path(directory) / "manager/profile.json")
            environment = {ENVIRONMENT: "1"}
            configure_launch(paths, environment)
            self.assertNotIn(ENVIRONMENT, environment)
            set_enabled(paths, True)
            self.assertTrue(enabled(paths))
            configure_launch(paths, environment)
            self.assertEqual(environment[ENVIRONMENT], "1")
            set_enabled(paths, False)
            configure_launch(paths, environment)
            self.assertNotIn(ENVIRONMENT, environment)

    def test_native_sites_in_each_supported_executable(self):
        from majesty_cam.manager.qol_service import detect_majesty_branch
        profiles = (
            ("PUBLIC", 0x12618c, 0x1261c6, 0x126244, 0x125f40, 0xef2c0, 0xbcc02),
            ("BETA2", 0x13aa4c, 0x13aa86, 0x13ab04, 0x13a800, 0xef880, 0xbd642),
            ("GOG", 0x139d4c, 0x139d86, 0x139e04, 0x139b00, 0xf0030, 0xbdc42),
        )
        for name, selected, direct, base_only, compose, lookup, bar in profiles:
            path = Path(os.environ["MAJESTY_" + name + "_EXE"])
            image = path.read_bytes()
            profile = detect_majesty_branch(path)
            def at(rva, size):
                section = next(s for s in profile.stock_sections if s.rva <= rva < s.rva + s.virtual_size)
                pos = section.raw_offset + rva - section.rva
                return image[pos:pos+size]
            def call_target(site):
                call = at(site, 5)
                self.assertEqual(call[0], 0xe8)
                return site + 5 + struct.unpack_from("<i", call, 1)[0]
            for site, target in ((selected, compose), (base_only, compose), (direct, lookup)):
                self.assertEqual(call_target(site), target)
            # Stock lookup maps the two release codes to distinct configurations.
            lookup_code = bytes.fromhex("8b4424043d52656c0075068d4150c204003d52656c4075098d814c010000c2040033c0c20400")
            self.assertEqual(at(lookup, len(lookup_code)), lookup_code)
            self.assertEqual(call_target(compose + 0x65), lookup)
            # Active mods match the requested argument or ANY, independently
            # of which files the built-in base configuration contains.
            self.assertEqual(at(compose + 0xe5, 9), bytes.fromhex("3b842428010000740e"))
            self.assertEqual(at(compose + 0xf5, 5), bytes.fromhex("3d414e5920"))
            code = bytes.fromhex("3d52656c0074183d52656c0274118b4b248b018b50206a006880250000ffd2")
            self.assertEqual(at(bar-5, len(code)), code)

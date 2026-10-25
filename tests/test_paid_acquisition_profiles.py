"""Exact three-build evidence for the stock clicked-unit acquisition route."""
import hashlib
import os
from pathlib import Path
import re
import unittest

from test_occupant_runtime_profiles import PeImage


class PaidAcquisitionProfiles(unittest.TestCase):
    def test_production_windows_and_original_mode_calls(self):
        source = (Path(__file__).parents[1] / 'runtime/PaidSourceTargetProfiles.h').read_text()
        body = source.split('constexpr NativeWindow AcquisitionWindows')[1].split('};', 1)[0]
        windows = [tuple(int(x, 16) for x in r) for r in re.findall(
            r'\{0x([0-9A-F]+)u,0x([0-9A-F]+)u,0x([0-9A-F]+)u\}', body)]
        self.assertEqual(len(windows), 30)
        profiles = (
            ('MAJESTY_PUBLIC_EXE', '255957fb09a4f8d5db6dde6d4127943dea965fa71c1da5db57951302b92e40b4', 0x65954, 0x65996, 0x5C790, 0x65360),
            ('MAJESTY_BETA2_EXE', '05dbd67ae90b2cc14370dabcf3f9e4f9de5dd12c17f85730ac3d237fceec2f82', 0x66984, 0x669C6, 0x5D7C0, 0x66390),
            ('MAJESTY_GOG_EXE', '65c6dd32c3d873c2e320bdaa2de1b00488af85b44573fd0fd82f79a2ffd37792', 0x668A4, 0x668E6, 0x5D6E0, 0x662B0),
        )
        for index, (variable, digest, choice, unit, picker, predicate) in enumerate(profiles):
            with self.subTest(profile=variable):
                self.assertTrue(os.environ.get(variable), f'{variable} is required')
                image = PeImage(os.environ[variable])
                from majesty_cam.manager.qol_service import detect_majesty_branch
                self.assertEqual(detect_majesty_branch(Path(os.environ[variable])).key,
                                 ('public', 'beta2', 'gog')[index])
                self.assertEqual(image.read(choice, 6), bytes.fromhex('81fe53703234'))
                for address, size, expected in windows[index*10:(index+1)*10]:
                    h = 2166136261
                    for byte in image.read(address, size):
                        h = ((h ^ byte)*16777619) & 0xffffffff
                    self.assertEqual(h, expected, hex(address))
                self.assertEqual(image.target(unit+19), picker)
                self.assertEqual(image.target(unit+37), predicate)
                # The original mode in ESI reaches the predicate, not Sp12.
                self.assertEqual(image.read(unit+35, 2), bytes.fromhex('8bc6'))
                self.assertEqual(image.read(unit+4, 7), bytes.fromhex('6a046830000080'))

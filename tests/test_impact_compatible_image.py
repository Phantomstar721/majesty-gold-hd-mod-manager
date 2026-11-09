import os
import tempfile
import unittest
from pathlib import Path
from majesty_cam.native_impact import require_exact_profile
from majesty_cam.native_impact_profiles import PROFILES
from majesty_cam.manager.qol_service import detect_majesty_branch

class CompatibleImageTests(unittest.TestCase):
    def test_supported_images_and_targeted_corruption(self):
        for key in ('PUBLIC', 'BETA2', 'GOG'):
            original = Path(os.environ['MAJESTY_' + key + '_EXE'])
            with self.subTest(build=key):
                require_exact_profile(original)
                branch = detect_majesty_branch(original)
                with tempfile.TemporaryDirectory() as folder:
                    candidate = Path(folder) / 'MajestyHD.exe'
                    data = original.read_bytes()
                    candidate.write_bytes(data + b'unrelated trailing data')
                    require_exact_profile(candidate)
                    address, size, expected = PROFILES[branch.key]['bodies'][0]
                    rva = address - 0x400000
                    section = next(s for s in branch.stock_sections if s.rva <= rva < s.rva + s.raw_size)
                    changed = bytearray(data)
                    changed[section.raw_offset + rva - section.rva] ^= 1
                    candidate.write_bytes(changed)
                    with self.assertRaisesRegex(ValueError, 'specific helper'):
                        require_exact_profile(candidate)
                    candidate.write_bytes(b'not an executable')
                    with self.assertRaises(ValueError):
                        require_exact_profile(candidate)

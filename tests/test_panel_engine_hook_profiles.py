import json
import os
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from verify_panel_engine_hooks import verify, transfer


class HookProfileTests(unittest.TestCase):
    def test_three_owner_profiles_and_sdk_sites(self):
        fixtures = {name: Path(os.environ['MAJESTY_' + name.upper() + '_EXE']) for name in ('public', 'beta2', 'gog')}
        expected = json.loads((ROOT / 'profiles/panel-engine/hook-sites.json').read_bytes())
        self.assertEqual(verify(fixtures), expected)
        for profile in expected['profiles'].values():
            window = profile['windowFactoryCall']
            self.assertEqual(window['rva'] + 5, profile['postFactoryOwnerSite']['rva'])
            registration = profile['stockRegistrationCall']
            self.assertEqual(registration['rva'] + 5, profile['scriptRegistrationTail']['rva'])

    def test_rejects_wrong_opcode_truncated_instruction_and_wrong_provider(self):
        class Image:
            class OPTIONAL_HEADER:
                ImageBase = 0x400000
            def get_data(self, rva, length):
                return self.data
        image = Image()
        for data in (b'\xe9\0\0\0\0', b'\xe8\0\0'):
            image.data = data
            with self.assertRaises(ValueError):
                transfer(image, 0x1000, 0xe8)
        image.data = b'\xe8' + struct.pack('<i', 0x1234)
        with self.assertRaises(ValueError):
            transfer(image, 0x1000, 0xe8, 0x401005)

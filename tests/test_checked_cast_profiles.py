"""Three-build cast entry/ABI evidence; does not enable the shared observer."""
import os
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage
from test_fade_persistence_profiles import fingerprint


class CheckedCastProfilesTests(unittest.TestCase):
    def test_pending_turn_profiles(self):
        text = (Path(__file__).parents[1] / 'runtime/PendingCastProfiles.h').read_text()
        for env, name in (('MAJESTY_PUBLIC_EXE','pub'), ('MAJESTY_BETA2_EXE','beta'), ('MAJESTY_GOG_EXE','gog')):
            self.assertTrue(os.environ.get(env), env + ' is required')
            im = PeImage(os.environ[env])
            process, table, expected = [int(v,16) for v in re.search(r'PendingCastProfile '+name+r'\{([^}]+)\}',text)[1].split(',')]
            def read(va,n): return im.read(va-im.base,n)
            def word(va): return struct.unpack('<I',read(va,4))[0]
            self.assertEqual(fingerprint(read(process,380)),expected)
            self.assertEqual(word(table+0x18),process)
            self.assertEqual(read(process,6),bytes.fromhex('51538b5c2414'))
            descriptor=word(word(table-4)+12)
            name_bytes=b'.?AVOrderTurn@@\0'
            self.assertEqual(read(descriptor+8,len(name_bytes)),name_bytes)

    def test_explicit_profiles_and_stock_calls(self):
        text = (Path(__file__).parents[1] / 'runtime/CheckedCastProfiles.h').read_text()
        schedules, actions = [], []
        for env, name, variable, schedule_hash, action_hash, registration in (
            ('MAJESTY_PUBLIC_EXE', 'Public', 'publicBuild', 0x4BD691BF, 0x29D7DF25, 0x5C0E56),
            ('MAJESTY_BETA2_EXE', 'Beta2', 'betaBuild', 0xCF9A30E2, 0x0C37F3B6, 0x5D6036),
            ('MAJESTY_GOG_EXE', 'Gog', 'gogBuild', 0x53084F82, 0x6F16CFFC, 0x5D5386),
        ):
            self.assertTrue(os.environ.get(env), env + ' is required')
            image = PeImage(os.environ[env])
            def read(va, size): return image.read(va - image.base, size)
            def word(va): return struct.unpack('<I', read(va, 4))[0]
            def target(va): return image.target(va - image.base) + image.base
            block = re.search(r'kCast' + name + r'Windows\[\]=\{(.*?)\n\};', text, re.S)[1]
            entries = re.findall(r'\{(0x[0-9A-F]+),(\d+),\{([^}]+)\}\}', block)
            self.assertEqual(len(entries), 17)
            addresses = []
            for address, size, values in entries:
                address = int(address, 16); size = int(size)
                expected = bytes(int(value, 16) for value in values.split(','))
                self.assertEqual(len(expected), size)
                self.assertEqual(read(address, size), expected)
                addresses.append(address)
            values = re.search(r'CastNativeProfile ' + variable + r'\{[^,]+,([^}]+)\}', text)[1]
            table, invoke, release, action, cancel = [int(v, 16) for v in values.split(',')]
            self.assertEqual(target(addresses[15]), release)
            self.assertEqual(target(addresses[16]), invoke)
            self.assertEqual(read(addresses[16] - 7, 7), bytes.fromhex('8b4e088d461050'))
            locator = word(table - 4); descriptor = word(locator + 12)
            type_name = b'.?AVGplFunction@@\0'
            self.assertEqual(read(descriptor + 8, len(type_name)), type_name)
            self.assertEqual(read(registration, 1), b'\x68')
            self.assertEqual(read(word(registration + 1), 10), b'RunThread\0')
            self.assertEqual(read(registration + 0x26, 1), b'\x68')
            self.assertEqual(word(registration + 0x27), addresses[1])
            schedule = bytearray(read(addresses[1], 0x78))
            self.assertEqual(fingerprint(schedule), schedule_hash)
            for offset in (0xC, 0x20, 0x32, 0x42, 0x4B, 0x54, 0x5D, 0x6D):
                schedule[offset:offset + 4] = bytes(4)
            schedules.append(bytes(schedule))
            body = bytearray(read(action, 0xE5))
            self.assertEqual(fingerprint(body), action_hash)
            for offset in (0xD, 0x13, 0x1F, 0x33, 0x39, 0x41, 0x4B, 0x58,
                           0x71, 0x77, 0x7F, 0x89, 0xAE, 0xC9, 0xCF, 0xD7, 0xE1):
                body[offset:offset + 4] = bytes(4)
            actions.append(bytes(body))
            self.assertEqual(fingerprint(read(cancel, 0x2D)), 0xECE9FD91)
        self.assertEqual(schedules[0], schedules[1]); self.assertEqual(schedules[0], schedules[2])
        self.assertEqual(actions[0], actions[1]); self.assertEqual(actions[0], actions[2])

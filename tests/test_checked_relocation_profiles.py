"""Full relocation bodies and call-frame invariants on all three builds."""
import os
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage


class CheckedRelocationProfilesTests(unittest.TestCase):
    def verify(self, env, name):
        path = os.environ.get(env)
        if not path:
            self.skipTest(env + ' is required for three-version acceptance')
        image = PeImage(path)
        source = (Path(__file__).parents[1] / 'runtime/CheckedRelocationProfiles.h').read_text()
        values = re.search(r'RelocationProfile ' + name + r'\{([^}]+)\}', source)[1]
        convert, write, expected = [int(value, 16) for value in values.split(',')]
        def at(va, count):
            return image.read(va - image.base, count)
        def fingerprint(blob):
            value = 2166136261
            for byte in blob:
                value = ((value ^ byte) * 16777619) & 0xffffffff
            return value
        self.assertEqual(fingerprint(at(convert, 0x59)), expected)
        self.assertEqual(fingerprint(at(write, 0xB4)), 0xDA557991)
        self.assertEqual(image.target(convert + 0x4D - image.base) + image.base, write)
        self.assertEqual(at(convert + 4, 4), bytes.fromhex('83ec0c56'))
        self.assertEqual(at(write, 4), bytes.fromhex('83ec1456'))
        self.assertEqual(at(write + 0x2F, 6), bytes.fromhex('8b44241c8b08'))
        self.assertEqual(at(write + 0x35, 6), bytes.fromhex('894e588b5004'))
        self.assertEqual(at(write + 0xAD, 7), bytes.fromhex('5e83c414c20400'))

    def test_beta2(self): self.verify('MAJESTY_BETA2_EXE', 'betaBuild')
    def test_public(self): self.verify('MAJESTY_PUBLIC_EXE', 'publicBuild')
    def test_gog(self): self.verify('MAJESTY_GOG_EXE', 'gogBuild')

    def test_three_build_query_bodies(self):
        source = (Path(__file__).parents[1] / 'runtime/CheckedPlacementProfiles.h').read_text()
        normalized = []
        for env, name in (('MAJESTY_BETA2_EXE', 'betaBuild'),
                          ('MAJESTY_PUBLIC_EXE', 'publicBuild'),
                          ('MAJESTY_GOG_EXE', 'gogBuild')):
            self.assertTrue(os.environ.get(env), env + ' is required')
            image = PeImage(os.environ[env])
            values = re.search(r'PlacementQueryProfile ' + name + r'\{([^}]+)\}', source)[1]
            entries = [int(value, 16) for value in values.split(',')]
            bodies = []
            for index, (va, size, expected, calls) in enumerate(zip(
                    entries[:3], (0x45, 0x9F, 0xBC), entries[3:],
                    ((0x38, 0x3F), (0x6F, 0x93), (0x5A, 0x61)))):
                body = bytearray(image.read(va - image.base, size))
                value = 2166136261
                for byte in body:
                    value = ((value ^ byte) * 16777619) & 0xffffffff
                self.assertEqual(value, expected, env + hex(va))
                for offset in calls:
                    self.assertEqual(body[offset], 0xE8)
                    body[offset + 1:offset + 5] = bytes(4)
                if index == 1:
                    # Default footprint predicate address, not a gameplay flag.
                    self.assertEqual(body[0x31], 0xBB)
                    body[0x32:0x36] = bytes(4)
                bodies.append(bytes(body))
            normalized.append(bodies)
        self.assertEqual(normalized[0], normalized[1])
        self.assertEqual(normalized[0], normalized[2])

    def test_three_build_state_type_identity(self):
        source = (Path(__file__).parents[1] / 'runtime/CheckedPlacementProfiles.h').read_text()
        for env, name in (('MAJESTY_BETA2_EXE', 'betaBuild'),
                          ('MAJESTY_PUBLIC_EXE', 'publicBuild'),
                          ('MAJESTY_GOG_EXE', 'gogBuild')):
            self.assertTrue(os.environ.get(env), env + ' is required')
            image = PeImage(os.environ[env])
            def read(va, count):
                return image.read(va - image.base, count)
            def word(va):
                return struct.unpack('<I', read(va, 4))[0]
            values = re.search(r'PlacementStateProfile ' + name + r'\{([^}]+)\}', source)[1]
            entries = [int(value, 16) for value in values.split(',')]
            for table, type_name in zip(entries[:4],
                    ('GSUnit', 'VehicleRec', 'BuildingRec', 'MovementDesc_Linear_Engine')):
                locator = word(table - 4)
                self.assertEqual(read(locator, 12), bytes(12))
                type_descriptor = word(locator + 12)
                expected = ('.?AV' + type_name + '@@').encode() + b'\0'
                self.assertEqual(read(type_descriptor + 8, len(expected)), expected)
            for table in entries[:3]:
                self.assertEqual([word(table + slot) for slot in (0x30, 0xC0, 0x124)], entries[4:])

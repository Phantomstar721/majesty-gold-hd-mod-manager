"""Complete helper-body/ABI parity; not permission to activate the provider."""
import os
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage
from test_fade_persistence_profiles import fingerprint


class PlacementBindingProfilesTests(unittest.TestCase):
    def test_bodies_and_concrete_links(self):
        text = (Path(__file__).parents[1] / 'runtime/CheckedPlacementBindingProfiles.h').read_text()
        normalized = []
        for env, name, tables in (
            ('MAJESTY_PUBLIC_EXE', 'publicBuild', (0x73A924, 0x73B08C, 0x73A004)),
            ('MAJESTY_BETA2_EXE', 'betaBuild', (0x7539E4, 0x75414C, 0x7530C4)),
            ('MAJESTY_GOG_EXE', 'gogBuild', (0x752A2C, 0x753194, 0x75210C)),
        ):
            self.assertTrue(os.environ.get(env), env + ' is required')
            im = PeImage(os.environ[env])
            def read(va, size): return im.read(va-im.base, size)
            def word(va): return struct.unpack('<I', read(va, 4))[0]
            block = re.search(r'PlacementBindingProfile ' + name + r'\{(.*?)\}\};', text, re.S)[1]
            values = [int(v, 16) for v in re.findall(r'0x[0-9A-F]+', block)]
            self.assertEqual(len(values), 16)
            addresses, hashes = values[:8], values[8:]
            bodies = []
            for address, size, expected, references in zip(
                addresses, (9, 0x45, 0x21, 0x66, 10, 0x24, 0x21, 0x24), hashes,
                ((1,), (0x29, 0x36), (0x1B,), (0x17, 0x26), (), (0x13,), (0xE,), (8, 0xF)),
            ):
                body = bytearray(read(address, size))
                self.assertEqual(fingerprint(body), expected, (env, hex(address)))
                for offset in references: body[offset:offset+4] = bytes(4)
                bodies.append(bytes(body))
            normalized.append(bodies)
            # The proxy really calls the selected root accessor; dead predicates
            # come from the concrete supported types, not similar byte patterns.
            self.assertEqual(im.target(addresses[7]+7-im.base)+im.base, addresses[0])
            for table, predicate in zip(tables, (addresses[4], addresses[4], addresses[5])):
                self.assertEqual(word(table+0x78), predicate)
            self.assertEqual(read(addresses[0]+5, 4), bytes.fromhex('8b4020c3'))
            self.assertEqual(read(addresses[1]+0x42, 3), bytes.fromhex('c20400'))
            self.assertEqual(read(addresses[3]+0x63, 3), bytes.fromhex('c20400'))
            self.assertEqual(read(addresses[6]+0x1E, 3), bytes.fromhex('c20800'))
        self.assertEqual(normalized[0], normalized[1])
        self.assertEqual(normalized[0], normalized[2])

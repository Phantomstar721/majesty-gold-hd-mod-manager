"""Read-only actor draw evidence. Does not install or exercise a renderer."""
import hashlib
import os
import struct
import unittest
from test_occupant_runtime_profiles import PeImage


class DawnfallDrawProfilesTests(unittest.TestCase):
    def test_unit_draw_and_part_override(self):
        draw_bodies, overrides = [], []
        for env, unit, thunk, draw, part, iso, override, draw_sha, override_sha in (
            ('MAJESTY_PUBLIC_EXE', 0x73A924, 0x4463D0, 0x5D3F60, 0x74885C, 0x74A564, 0x60C360,
             '2a79be9f1dad081e0092210c4983c363a09dc13d1255eff8dfae794d4ebda047',
             '5c156e39a433fab20acd770186e99e7c64c76845926cbf5f51dc6251584d8fd3'),
            ('MAJESTY_BETA2_EXE', 0x7539E4, 0x4472E0, 0x5E9140, 0x76292C, 0x764634, 0x6216A0,
             '0dc58e61e577dc7d9b1ecaebe2382a2b6b167cb75a51da5f3353844e3100660c',
             '8add0c62645aad6c090259ec92f7a9fd5716ab3b22bcf533ffafe1694f51f277'),
            ('MAJESTY_GOG_EXE', 0x752A2C, 0x447200, 0x5E8490, 0x7617EC, 0x7634F4, 0x6209F0,
             'e10854205044fc295be0766b2e068100b35a538b8c1eb16b198de77c66c8978a',
             '5e829d4c76d4800d11811c2f65816ea6a380c8aa419e75b85fd0b2bb2fea5294'),
        ):
            self.assertTrue(os.environ.get(env), env + ' is required')
            im = PeImage(os.environ[env])
            def read(va, size): return im.read(va-im.base, size)
            def word(va): return struct.unpack('<I', read(va, 4))[0]
            self.assertEqual(word(unit+0xA8), thunk)
            self.assertEqual(read(thunk, 1), b'\xe9')
            self.assertEqual(thunk+5+struct.unpack('<i', read(thunk+1, 4))[0], draw)
            for table, name in ((part, 'UnitIMGPartEntry'), (iso, 'IsoUnitIMGPartEntry')):
                descriptor = word(word(table-4)+12)
                expected = ('.?AV'+name+'@@\0').encode()
                self.assertEqual(read(descriptor+8, len(expected)), expected)
            self.assertEqual(read(word(part+0x28), 5), bytes.fromhex('32c0c20400'))
            self.assertEqual(word(iso+0x28), override)
            body = bytearray(read(draw, 0x7A2))
            self.assertEqual(hashlib.sha256(body).hexdigest(), draw_sha)
            # Every ordinary part starts with unit+24, then passes the LOCAL copy
            # to that part's virtual28. It is not a main-image-only fade field.
            self.assertEqual(body[0x4F3:0x50C], bytes.fromhex(
                '8b47248b138b5228894424388d442438508bcbffd28b442438'))
            self.assertEqual(body[-3:], bytes.fromhex('c20800'))
            # Explicit executable references only; preserve all branches/slots.
            for offset in (87,212,254,333,546,621,645,678,688,709,731,758,766,836,860,909,
                           1149,1212,1231,1251,1263,1322,1346,1371,1451,1470,1478,1493,
                           1505,1529,1535,1569,1603,1634,1655,1681,1687,1696,1738,1758,1797):
                body[offset:offset+4] = bytes(4)
            draw_bodies.append(bytes(body))
            body = bytearray(read(override, 0xAE))
            self.assertEqual(hashlib.sha256(body).hexdigest(), override_sha)
            # Its override is conditional on part+10 and flags&F000==1000;
            # arbitrary effect parts cannot be assumed to bypass the unit fade.
            self.assertEqual(body[:8], bytes.fromhex('8b411083ec0885c0'))
            self.assertEqual(body[0xE:0x1D], bytes.fromhex('8b510c81e200f0000081fa00100000'))
            for offset in (0x25, 0x6A): body[offset:offset+4] = bytes(4)
            overrides.append(bytes(body))
        self.assertEqual(draw_bodies[0], draw_bodies[1])
        self.assertEqual(draw_bodies[0], draw_bodies[2])
        self.assertEqual(overrides[0], overrides[1])
        self.assertEqual(overrides[0], overrides[2])

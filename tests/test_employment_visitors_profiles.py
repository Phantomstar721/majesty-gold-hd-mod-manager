"""Read-only stock Visitors routing/lifecycle evidence for all three builds."""
import os
import struct
import unittest
from test_occupant_runtime_profiles import PeImage


class VisitorsProfiles(unittest.TestCase):
    def test_stock_routes(self):
        profiles = (
            ('MAJESTY_PUBLIC_EXE', 0x5897B72F, 0x95790, 0x968B0, 0x992B0,
             0x96E80, 0xB03F0, 0x67540, 0x10BE54, 0x9D580, 0x33D2DC),
            ('MAJESTY_BETA2_EXE', 0x5A8A11D5, 0x95FA0, 0x970C0, 0x99B90,
             0x97690, 0xB0CE0, 0x68780, 0x11C3A4, 0x9DE60, 0x355FB4),
            ('MAJESTY_GOG_EXE', None, 0x96550, 0x97670, 0x9A140,
             0x97C40, 0xB1290, 0x686A0, 0x10E2B4, 0x9E410, 0x3550EC),
        )
        for env, stamp, basic, guild, smith, service, opener, context, factory, ctor, table in profiles:
            with self.subTest(profile=env):
                path = os.environ.get(env)
                if not path:
                    self.fail(env + ' is required for Visitors parity validation')
                pe = PeImage(path)
                u32 = lambda rva: struct.unpack('<I', pe.read(rva, 4))[0]
                if stamp is not None:
                    self.assertEqual(pe.timestamp, stamp)
                # Blacksmith and Guild both delegate the Visitors command to Basic.
                self.assertEqual(pe.target(smith + 0xF), service)
                self.assertEqual(pe.target(service + 0x12), basic)
                self.assertEqual(pe.target(guild + 0x1F), basic)
                indices = u32(basic + 0x21) - pe.base
                jumps = u32(basic + 0x28) - pe.base
                index = pe.read(indices + 0x1F55 - 0x1F42, 1)[0]
                branch = u32(jumps + index * 4) - pe.base
                self.assertEqual(pe.read(branch, 8), bytes.fromhex('57 68 41 50 39 31 8b ce'))
                self.assertEqual(pe.target(branch + 8), opener)
                self.assertEqual(pe.read(branch + 13, 7), bytes.fromhex('8b f8 5f 5e c2 04 00'))
                # Stock factory owns allocation and AP91 constructor. No private child.
                self.assertEqual(pe.read(factory, 2), b'\x6a\x4c')
                self.assertEqual(pe.target(factory + 42), ctor)
                self.assertEqual(pe.read(ctor + 0x48, 2), b'\xc7\x06')
                self.assertEqual(u32(ctor + 0x4A) - pe.base, table)
                self.assertEqual(pe.target(ctor + 0x4E), context)
                self.assertEqual(pe.read(ctor + 0x53, 8), bytes.fromhex('6a 02 8d 88 a4 00 00 00'))
                # Constructor seeds handles from native relation 2; stock event,
                # setup, Back, destructor remain installed and unmodified.
                vt = struct.unpack('<15I', pe.read(table, 60))
                control, setup, event, destroy = (vt[i] - pe.base for i in (3, 1, 8, 0))
                self.assertEqual(pe.target(control + 7), context)
                public = env == 'MAJESTY_PUBLIC_EXE'
                self.assertEqual(pe.read(control + 0x12, 5),
                                 bytes.fromhex('3d 4d 1f 00 00' if public else '3d 40 1f 00 00'))
                # beta/GOG explicitly handle Close before Back; preserve each
                # stock implementation, not a copied Public command handler.
                self.assertEqual(pe.read(control + (0x1A8 if public else 0x204), 2), b'\x6a\x00')
                self.assertEqual(pe.target(control + 0x104), opener)
                self.assertEqual(pe.read(setup + 8, 7), bytes.fromhex('c7 46 30 01 00 00 00'))
                self.assertEqual(pe.read(event + 0x15, 6), bytes.fromhex('81 ff 58 53 43 06'))
                self.assertEqual(pe.read(destroy + 0x28, 2), b'\xc7\x06')


if __name__ == '__main__':
    unittest.main()

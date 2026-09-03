"""Verify the stock single/stacked lifecycle on both local executable profiles."""
import os
import unittest

from test_occupant_runtime_profiles import PeImage


class PanelLifecycleProfileTests(unittest.TestCase):
    def verify(self, variable, timestamp, opener, create, context, manager,
               remove, dispatch, layout, back):
        path = os.environ.get(variable)
        if not path:
            self.skipTest(f"{variable} is not set")
        pe = PeImage(path)
        self.assertEqual(pe.timestamp, timestamp)
        # Each controller resolves its own native handle, not its old parent.
        self.assertEqual(pe.read(context, 13), bytes.fromhex("8b 51 2c 33 c0 85 d2 74 09 8b 49 28 52"))
        self.assertEqual(pe.target(opener + 0xD), context)
        self.assertEqual(pe.target(opener + 0x3B), create)
        # Child classification 1 with parent 0 returns zero (keep parent).
        # Other cases preserve the default nonzero removal result.
        self.assertEqual(pe.read(opener + 0x8C, 13), bytes.fromhex("83 f8 01 75 31 83 7f 30 00 75 02 33 db"))
        # Missing secondary layout container falls back to the primary slot.
        self.assertEqual(pe.read(layout + 0x46, 5), bytes.fromhex("68 a0 0f 00 00"))
        self.assertEqual(pe.read(layout + 0x72, 3), bytes.fromhex("89 7e 30"))
        # The command result is consumed only after the command returns.
        self.assertEqual(pe.read(dispatch + 0x47, 6), bytes.fromhex("ff d0 85 c0 74 08"))
        self.assertEqual(pe.target(dispatch + 0x50), remove)
        self.assertEqual(pe.read(remove + 0x3F, 8), bytes.fromhex("8b 01 8b 10 6a 01 ff d2"))
        # AP69 Back: context on self, stream hide, parent create(ctx,0,0),
        # then the nonzero result that removes the initiating child.
        self.assertEqual(pe.target(back + 0xD), manager)
        self.assertEqual(pe.target(back + 0x16), context)
        self.assertEqual(pe.read(back + 0x4B, 14), bytes.fromhex("8b 44 24 10 8b 48 24 8b 11 8b 42 14 ff d0"))
        self.assertEqual(pe.read(back + 0xFB, 5), bytes.fromhex("6a 00 6a 00 56"))
        self.assertEqual(pe.target(back + 0x107), create)
        self.assertEqual(pe.read(back + 0x10E, 5), bytes.fromhex("bb 01 00 00 00"))

    def test_public(self):
        self.verify("MAJESTY_PUBLIC_EXE", 0x5897B72F, 0xB03F0, 0x25910,
                    0x67540, 0x25D00, 0x25880, 0x25B20, 0xAF150, 0xAE6F0)

    def test_beta2(self):
        self.verify("MAJESTY_BETA2_EXE", 0x5A8A11D5, 0xB0CE0, 0x268E0,
                    0x68780, 0x26CD0, 0x26850, 0x26AF0, 0xAFA40, 0xAEFE0)

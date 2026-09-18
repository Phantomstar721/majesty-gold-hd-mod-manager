"""Pin the production timing guards to both supported stock executables."""
import os
from pathlib import Path
import re
import struct
import unittest

from test_occupant_runtime_profiles import PeImage


class NativeTimingProfiles(unittest.TestCase):
    def verify(self, variable, suffix):
        path = os.environ.get(variable)
        if not path:
            self.skipTest(variable + " is not set")
        image = PeImage(path)
        source = (Path(__file__).resolve().parents[1] / "runtime/MapQueryRuntime.cpp").read_text()

        def profile(kind, name):
            body = re.search(r"constexpr " + kind + " " + name + r" = \{(.*?)\};", source, re.S)[1]
            return [int(value, 16) for value in re.findall(r"0x[0-9a-fA-F]+", body)]

        (_, _, engine, _, _, _, at, *_) = profile("Profile", "k" + suffix)
        (cast, available, check, clock, actions, units, find, resolve,
         effect, order, refresh, expire, vehicle, action_base, action_effective,
         action_constructor, action_vtable) = profile("TimingProfile", "kTiming" + suffix)
        for site, target in ((cast+0x2f, at), (cast+0x55, resolve), (cast+0xa8, find),
                             (check+0x5a, find+0xa0), (resolve+7, engine),
                             (action_effective+9, action_base)):
            with self.subTest(call=hex(site)):
                self.assertEqual(image.target(site), target)
        for site, target in ((cast+0xa3, actions), (check+0x53, units), (cast+0x19c, clock),
                             (available+0x1af, clock), (refresh+0x14, clock), (expire+1, clock),
                             (vehicle+0x140, effect), (vehicle+0x180, order),
                             (action_constructor+0x39, action_vtable)):
            with self.subTest(pointer=hex(site)):
                self.assertEqual(struct.unpack("<I", image.read(site, 4))[0], image.base+target)
        guards = source.split("bool ValidateNativeTiming()", 1)[1].split("bool ValidateMovementQuery()", 1)[0]
        for name, site in (("spellList", cast+0x102), ("spellDuration", cast+0x190),
                           ("spellCommit", cast+0x1a4), ("available", available+0x1b3),
                           ("effectorGet", effect), ("orderGet", order),
                           ("effectorRefresh", refresh), ("effectorWrite", refresh+0x18),
                           ("expire", expire+5), ("resolve", resolve), ("deleted", resolve+0x13),
                           ("actionPeriod", action_base), ("actionModifier", action_effective+0x0e)):
            body = re.search(r"unsigned char " + name + r"\[\] = \{(.*?)\};", guards, re.S)[1]
            expected = bytes(int(word.strip(), 0) for word in body.split(","))
            with self.subTest(guard=name):
                self.assertEqual(image.read(site, len(expected)), expected)

    def test_public(self):
        self.verify("MAJESTY_PUBLIC_EXE", "Public")

    def test_beta(self):
        self.verify("MAJESTY_BETA2_EXE", "Beta")

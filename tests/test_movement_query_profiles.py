"""Read-only checks against both audited native executable profiles."""
import os
from pathlib import Path
import re
import struct
import unittest

from test_occupant_runtime_profiles import PeImage


class MovementQueryProfiles(unittest.TestCase):
    def verify(self, variable, suffix):
        path = os.environ.get(variable)
        if not path:
            self.skipTest(variable + " is not set")
        image = PeImage(path)
        source = (Path(__file__).resolve().parents[1] / "runtime/MapQueryRuntime.cpp").read_text()

        def profile(kind, name):
            body = re.search(r"constexpr " + kind + " " + name + r" = \{(.*?)\};", source, re.S)[1]
            return [int(x, 16) for x in re.findall(r"0x[0-9a-fA-F]+", body)]

        (_, _, engine, _, _, _, at, *_) = profile("Profile", "k" + suffix)
        (change, resolve, find, descriptions, base, effective, attribute, clock,
         step, ctor, vtable, derived) = profile("MovementProfile", "kMovement" + suffix)
        for site, target in ((change+0x0e, at), (change+0x34, resolve),
                             (change+0x69, find), (resolve+7, engine),
                             (effective+4, base), (effective+0x14, attribute)):
            self.assertEqual(image.target(site), target)
        for site, target in ((change+0x64, descriptions), (effective+0x1c, clock),
                             (ctor+0x35, vtable), (vtable+0xc, derived)):
            self.assertEqual(struct.unpack("<I", image.read(site, 4))[0], image.base+target)
        # Check the actual installation byte guards, not an independent copy
        # that could pass while production rejects a supported executable.
        guards = source.split("bool ValidateMovementQuery()", 1)[1].split("void Register(", 1)[0]
        for name, site in (("interval", base), ("modifier", effective+9),
                           ("rounding", effective+0x20), ("step", step),
                           ("attachments", base-0xe0), ("resolveIdentity", resolve),
                           ("resolveDeleted", resolve+0x13),
                           ("agentArgument", change+0x13), ("stringArgument", change+0x27)):
            body = re.search(r"unsigned char " + name + r"\[\] = \{(.*?)\};", guards, re.S)[1]
            expected = bytes(int(word.strip(), 0) for word in body.split(","))
            with self.subTest(guard=name):
                self.assertEqual(image.read(site, len(expected)), expected)

    def test_public(self):
        self.verify("MAJESTY_PUBLIC_EXE", "Public")

    def test_beta(self):
        self.verify("MAJESTY_BETA2_EXE", "Beta")

    def test_gog(self):
        self.verify("MAJESTY_GOG_EXE", "Gog")

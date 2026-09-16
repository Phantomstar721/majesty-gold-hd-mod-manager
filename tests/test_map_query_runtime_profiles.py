"""Read-only native ABI evidence; never launches a game or builds a profile."""
import os
from pathlib import Path
import re
import struct
import unittest
from test_occupant_runtime_profiles import PeImage

class MapQueryProfiles(unittest.TestCase):
    def verify(self, variable, name, list_vtable, find_control, list_refresh):
        path = os.environ.get(variable)
        if not path:
            self.skipTest(variable + " is not set")
        image = PeImage(path)
        source = (Path(__file__).resolve().parents[1]/"runtime/MapQueryRuntime.cpp").read_text()
        body = re.search(r"constexpr Profile " + name + r" = \{(.*?)\};", source, re.S)[1]
        (call, registration, engine, register, ctor, dtor, at, world, extents, nearest, path_cost) = [
            int(x,16) for x in re.findall(r"0x[0-9a-fA-F]+",body)]
        self.assertEqual(image.target(call), registration)
        self.assertEqual(image.read(extents+0x1a,23), bytes.fromhex(
            "8b 48 10 8b 81 88 00 00 00 db 40 38 8d 4c 24 10 d9 5c 24 04 db 40 3c"))
        self.assertEqual(struct.unpack("<I",image.read(extents+6,4))[0],world+image.base)
        self.assertEqual(image.read(nearest+0x6f,12), bytes.fromhex("8b 8e 94 00 00 00 8b 91 88 00 00 00"))
        # Native argument boxing and the exact string/registration ABI are
        # references from the stock GetNearestHiddenCoord registration.
        self.assertEqual(image.target(nearest+0x2f),at)
        self.assertEqual(image.target(registration+0x7f1),ctor)
        self.assertEqual(image.target(registration+0x800),engine)
        self.assertEqual(image.target(registration+0x814),register)
        self.assertEqual(image.target(registration+0x821),dtor)
        # Both stock PathCost wrappers document an optional unit but fetch its
        # slot unconditionally. The guard changes only that one argument call.
        self.assertEqual(image.target(registration+0x7c2),engine)
        self.assertEqual(image.read(registration+0x7d0,1),b"\x68")
        self.assertEqual(struct.unpack("<I", image.read(registration+0x7d1,4))[0],
                         image.base+path_cost)
        self.assertEqual(image.target(registration+0x7d6),register)
        self.assertEqual(image.read(path_cost+0x7b,6),bytes.fromhex("6a 05 8b ce 8b e8"))
        self.assertEqual(image.target(path_cost+0x81),at)
        self.assertEqual(image.read(path_cost+0x86,6),bytes.fromhex("8b 00 8b 4c 24 1c"))
        self.assertEqual(image.read(path_cost+0x95,8),bytes.fromhex("c7 44 24 24 00 00 00 00"))
        self.assertEqual(image.read(path_cost+0x128,8),bytes.fromhex("8b 4c 24 24 85 c9 74 5f"))
        # The bounded traversal clones the first orientation of the stock
        # expanding rectangle scan, not a row-major approximation.
        search = 0x1c2f20 if name == "kPublic" else 0x1d8100
        self.assertEqual(image.target(nearest+0x111),search)
        self.assertEqual(image.read(search+0x163,36),bytes.fromhex(
            "8b 44 24 1c 8b 4c 24 20 8b 7c 24 24 8b 54 24 28 "
            "48 49 47 42 89 44 24 1c 89 4c 24 20 89 7c 24 24 89 54 24 28"))
        self.assertEqual(image.target(list_refresh+0x3b),find_control)
        table = [value-image.base for value in struct.unpack("<42I", image.read(list_vtable,168))]
        self.assertEqual(image.read(table[0xa0//4],4),bytes.fromhex("8b 44 24 04"))

    def test_public(self):
        self.verify("MAJESTY_PUBLIC_EXE","kPublic",0x34f76c,0x2524c0,0x97e20)
    def test_beta(self):
        self.verify("MAJESTY_BETA2_EXE","kBeta",0x369844,0x267920,0x98640)

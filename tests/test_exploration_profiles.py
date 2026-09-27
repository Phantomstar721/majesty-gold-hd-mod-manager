"""Opt-in verification against real executables, without running or patching them."""
import os
import re
import struct
import unittest
from pathlib import Path


class ExplorationProfileImageTests(unittest.TestCase):
    def test_audited_executables(self):
        header = (Path(__file__).parents[1] / "runtime/ExplorationProfiles.h").read_text()
        checked = 0
        for name, env, evaluator in (
            ("Public", "PUBLIC", (0xBBDB0,0x227A80,0x163680,0x227C30,0x162C40,0x1637C0,0x163520,0x163760,0x2DDF0)),
            ("Beta2", "BETA2", (0xBC7F0,0x23A220,0x1797B0,0x23A3D0,0x178D70,0x1798F0,0x179650,0x179890,0x2ED50)),
            ("Gog", "GOG", (0xBCDF0,0x23C370,0x178AB0,0x23C520,0x178070,0x178BF0,0x178950,0x178B90,0x2EC20)),
        ):
            path = os.environ.get("MAJESTY_EXPLORATION_" + env + "_EXE")
            if not path:
                continue
            checked += 1
            with self.subTest(build=name):
                file = Path(path).read_bytes()
                pe = struct.unpack_from("<I", file, 60)[0]
                section_count = struct.unpack_from("<H", file, pe+6)[0]
                optional_size = struct.unpack_from("<H", file, pe+20)[0]
                base = struct.unpack_from("<I", file, pe+52)[0]
                image = bytearray(struct.unpack_from("<I", file, pe+80)[0])
                for i in range(section_count):
                    offset = pe+24+optional_size+40*i
                    rva, size, raw = struct.unpack_from("<III", file, offset+12)
                    image[rva:rva+size] = file[raw:raw+size]
                values = [int(x,16) for x in re.findall(r"0x[0-9A-F]+", re.search(
                    r"constexpr Profile k"+name+r" = \{(.*?)\n\};", header, re.S).group(1))]
                self.assertEqual(len(values), 40)
                for rva, size, expected in zip(values[:21:3], values[1:21:3], values[2:21:3]):
                    value = 2166136261
                    for byte in image[rva:rva+size]:
                        value = ((value ^ byte)*16777619) & 0xFFFFFFFF
                    self.assertEqual(value, expected, hex(rva))
                source, reveal, reader, writer, owner, _, getter = values[:21:3]
                root, state, root_load, ready_call, ready = values[21:26]
                readers, owners, writers = values[26:29], values[29:38], values[38:40]
                def word(rva):
                    return struct.unpack_from("<I", image, rva)[0]
                def call(rva, target):
                    self.assertEqual(image[rva], 0xE8, hex(rva))
                    self.assertEqual(rva+5+struct.unpack_from("<i", image,rva+1)[0], target, hex(rva))
                self.assertEqual(image[reveal+0x12D:reveal+0x13B], bytes.fromhex("8B0F8BC10B4424443BC1744C8907"))
                call(source+0xC0,reveal)
                call(ready_call,ready)
                for site in readers:
                    call(site,reader)
                for site in owners:
                    self.assertEqual(word(site),base+owner)
                for site in writers:
                    self.assertEqual(word(site),base+writer)
                self.assertEqual(image[root_load],0xA1)
                self.assertEqual(word(root_load+1),base+root)
                self.assertEqual(word(getter+0x22),base+state)
                helper, string, ctor, string_dtor, agent, execute, scalar, dtor, at = evaluator
                for offset, target in ((0x2D,string),(0x43,ctor),(0x51,string_dtor),(0x5F,agent),
                                       (0x68,execute),(0x71,scalar),(0x84,dtor)):
                    call(helper+offset,target)
                call(scalar+5,at)
        if not checked:
            self.skipTest("Set MAJESTY_EXPLORATION_<PUBLIC|BETA2|GOG>_EXE for native image audit")

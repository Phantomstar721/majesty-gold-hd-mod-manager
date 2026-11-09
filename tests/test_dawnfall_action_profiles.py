"""Port the researched stock arrival-owner boundaries; no feature activation.

Reuses research/docs/dawnfall-arrival-owner-20261004.md. Comparisons retain
branch logic/virtual slots and normalize only enumerated executable references.
This does not establish private artwork, cancellation recovery or live playback.
"""
import os
import struct
import unittest
from test_occupant_runtime_profiles import PeImage
from test_fade_persistence_profiles import fingerprint


LENGTHS = (0x50,0xE2,0x17A,0x6F,0x1D8,0x27,9,0x1D,0x2F,0x63,0x21)
REFERENCES = ((28,), (6,16,84,92,124), (51,177,182,348,367), (15,101),
              (9,20,152,190,314,435), (), (), (), (20,39), (38,44,56,87), (19,))
# actor F4, processor14, kind10 step, self-target handoff, processor10,
# channel availability, stack emptiness, callback1001, actor F8, base F8,
# completion-image selector.
PROFILES = (
    ('MAJESTY_PUBLIC_EXE', 0x73A924, 0x749534, 0x749C0C,
     (0x5C91E0,0x5CA860,0x5CA5D0,0x5CA560,0x5F6E70,0x5C9FE0,0x5FD150,0x5F6B40,0x447F40,0x5BA250,0x5B0280),
     (0xCA2A90B5,0x7000D1BB,0x8FFDF64B,0xC1B616AE,0xBFBCFA93,0xBDB3CD0E,0x1BB0FCC2,0xCDBF9990,0x88F80FC1,0xE1487D1B,0x831C52F2)),
    ('MAJESTY_BETA2_EXE', 0x7539E4, 0x763604, 0x763CDC,
     (0x5DE3C0,0x5DFA40,0x5DF7B0,0x5DF740,0x60C1B0,0x5DF1C0,0x612490,0x60BE80,0x448E50,0x5CF1F0,0x5C5220),
     (0xDE95B03E,0x6B6A49E5,0x1F8405BC,0x5A50626A,0xE4BE3F7B,0xBDB3CD0E,0x1BB0FCC2,0xCDBF9990,0x9653B7F1,0x3857E7C8,0x2ED980C1)),
    ('MAJESTY_GOG_EXE', 0x752A2C, 0x7624C4, 0x762B9C,
     (0x5DD710,0x5DED90,0x5DEB00,0x5DEA90,0x60B500,0x5DE510,0x6117E0,0x60B1D0,0x448D70,0x5CE540,0x5C4570),
     (0xDE95B03E,0xDA1BCC73,0x4F805E5B,0x5A50626A,0x22E2DB9F,0xBDB3CD0E,0x1BB0FCC2,0xCDBF9990,0x8E8135BD,0x8CC5802E,0x6F1B179A)),
)


class DawnfallActionProfilesTests(unittest.TestCase):
    def test_stock_owner_bodies_and_links(self):
        normalized = []
        for env, unit, processor, stack, addresses, hashes in PROFILES:
            self.assertTrue(os.environ.get(env), env+' is required')
            image = PeImage(os.environ[env])
            def read(va,n): return image.read(va-image.base,n)
            def word(va): return struct.unpack('<I',read(va,4))[0]
            def target(va): return image.target(va-image.base)+image.base
            for table, name in ((unit,'GSUnit'), (stack,'OrderStack')):
                descriptor = word(word(table-4)+12)
                expected = ('.?AV'+name+'@@\0').encode()
                self.assertEqual(read(descriptor+8,len(expected)),expected)
            for table, slot, index in ((unit,0xF4,0),(processor,0x14,1),
                                       (processor,0x10,4),(unit,0x168,5),
                                       (stack,0x54,6),(unit,0xF8,8)):
                self.assertEqual(word(table+slot),addresses[index])
            self.assertEqual(target(addresses[2]+0xB0),addresses[3])
            self.assertEqual(target(addresses[8]+0x26),addresses[9])
            self.assertEqual(target(addresses[9]+0x37),addresses[10])
            for slot in (0x104,0x108):
                self.assertEqual(read(word(unit+slot),8),bytes.fromhex('b802000000c20800'))
            rows = []
            for address, length, digest, refs in zip(addresses,LENGTHS,hashes,REFERENCES):
                body = bytearray(read(address,length))
                self.assertEqual(fingerprint(body),digest,(env,hex(address)))
                for offset in refs: body[offset:offset+4] = bytes(4)
                rows.append(bytes(body))
            normalized.append(rows)
        self.assertEqual(normalized[0],normalized[1])
        self.assertEqual(normalized[0],normalized[2])

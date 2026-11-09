"""Bounded stock serialization evidence; not a live save/load acceptance test."""
import os
import struct
import unittest
from test_occupant_runtime_profiles import PeImage


# Independently matched bodies, verified against the concrete fade vtable.
# load/save fade, load/save envelope, load/save order-state subobject.
PROFILES = (
    ('MAJESTY_BETA2_EXE', 0x76371C, 0x60D050,
     (0x60CEF0, 0x60CF30, 0x611A60, 0x611A90, 0x611820, 0x6118B0),
     (0xB3955734, 0x052ED595, 0x3325C1F3, 0x638E57B6, 0x21396F0C, 0x31DD9CE2)),
    ('MAJESTY_PUBLIC_EXE', 0x74964C, 0x5F7D10,
     (0x5F7BB0, 0x5F7BF0, 0x5FC720, 0x5FC750, 0x5FC4E0, 0x5FC570),
     (0x8DAAE7E0, 0x93F2D78F, 0xA7CB86FF, 0x4A98DA88, 0x751AFF33, 0x69725DFA)),
    ('MAJESTY_GOG_EXE', 0x7625DC, 0x60C3A0,
     (0x60C240, 0x60C280, 0x610DB0, 0x610DE0, 0x610B70, 0x610C00),
     (0xD6B1C0EA, 0x014F49E1, 0x959E4AD7, 0x31636B78, 0x0C018C2A, 0x81900F80)),
)
LENGTHS = (0x3E, 0x3B, 0x2C, 0x29, 0x8A, 0x73)
CALLS = (
    (0xF, 0x17, 0x22, 0x2D, 0x34),
    (0xC, 0x14, 0x1F, 0x2A, 0x31),
    (0xF, 0x22), (0xC, 0x1F),
    (0xF, 0x1A, 0x25, 0x44, 0x4F, 0x5A, 0x65, 0x70, 0x79, 0x80),
    (0xC, 0x17, 0x22, 0x2D, 0x38, 0x43, 0x4E, 0x59, 0x62, 0x69),
)


def fingerprint(blob):
    value = 2166136261
    for byte in blob:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return value


class FadePersistenceProfilesTests(unittest.TestCase):
    def test_three_build_stock_routes(self):
        normalized = []
        for env, vtable, process, entries, hashes in PROFILES:
            # Unlike optional developer tests, this acceptance requires all three.
            self.assertTrue(os.environ.get(env), env + ' is required')
            image = PeImage(os.environ[env])
            def read(va, count):
                return image.read(va - image.base, count)
            def target(va):
                return image.target(va - image.base) + image.base
            self.assertEqual(struct.unpack('<II', read(vtable + 4, 8)), entries[:2])
            self.assertEqual(struct.unpack('<I', read(vtable + 0x18, 4))[0], process)
            bodies = []
            for entry, length, expected, calls in zip(entries, LENGTHS, hashes, CALLS):
                body = bytearray(read(entry, length))
                self.assertEqual(fingerprint(body), expected, env + hex(entry))
                for offset in calls:
                    self.assertEqual(body[offset], 0xE8)
                    body[offset + 1:offset + 5] = bytes(4)
                bodies.append(bytes(body))
            normalized.append(bodies)
            # Concrete fade serialization must delegate to its own base envelope.
            self.assertEqual(target(entries[0] + 0x17), entries[2])
            self.assertEqual(target(entries[1] + 0x14), entries[3])
            # Target and auxiliary fade fields are symmetric at +34/+38.
            self.assertEqual(read(entries[0] + 0x1C, 4), bytes.fromhex('8d4f3451'))
            self.assertEqual(read(entries[0] + 0x27, 4), bytes.fromhex('83c73857'))
            self.assertEqual(read(entries[1] + 0x19, 4), bytes.fromhex('8b473450'))
            self.assertEqual(read(entries[1] + 0x24, 4), bytes.fromhex('8b4f3851'))
        # Only relative call operands differ; structure, fields and branches match.
        self.assertEqual(normalized[0], normalized[1])
        self.assertEqual(normalized[0], normalized[2])

"""Read-only checks of the traced MX05 sites in both supported executables.

Set MAJESTY_PUBLIC_EXE and MAJESTY_BETA2_EXE to local reference files. Tests do
not launch, patch, or require pristine hashes for unrelated QOL code regions.
"""
import os
from pathlib import Path
import re
import struct
import unittest


class PeImage:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        header = struct.unpack_from("<I", self.data, 0x3C)[0]
        if self.data[header:header + 4] != b"PE\0\0":
            raise ValueError("not a PE image")
        count, self.timestamp = struct.unpack_from("<HI", self.data, header + 6)
        optional = struct.unpack_from("<H", self.data, header + 20)[0]
        self.base = struct.unpack_from("<I", self.data, header + 24 + 28)[0]
        self.sections = [struct.unpack_from("<4I", self.data, header + 24 + optional + 40 * i + 8)
                         for i in range(count)]

    def read(self, rva, size):
        for virtual_size, address, raw_size, offset in self.sections:
            if address <= rva and rva + size <= address + min(raw_size, virtual_size):
                start = offset + rva - address
                return self.data[start:start + size]
        raise ValueError(f"RVA {rva:#x} is not file-backed")

    def target(self, rva):
        code = self.read(rva, 5)
        if code[0] not in (0xE8, 0xE9):
            raise ValueError(f"not a relative call/jump at {rva:#x}")
        return rva + 5 + struct.unpack_from("<i", code, 1)[0]


class OccupantRuntimeProfileTests(unittest.TestCase):
    def verify(self, variable, name, timestamp, submit, ui_manager, slots, list_setup, list_refresh, list_callback, painter):
        path = os.environ.get(variable)
        if not path:
            self.skipTest(f"{variable} is not set")
        image = PeImage(path)
        source = (Path(__file__).resolve().parents[1] / "runtime/MajestyModManagerRuntime.cpp").read_text()
        body = re.search(r"constexpr OccupantBuildProfile " + name + r" = \{(.*?)\};", source, re.S)[1]
        (
            cost, submit_call, action, dispatch, string_ctor,
            post_submit_call, general_control_call, post_submit_handler,
            selection_focus_jump_entry, selection_focus_branch,
            action_focus_jump_entry, action_focus_branch, vtable,
        ) = [int(x, 16) for x in re.findall(r"0x[0-9A-Fa-f]+", body)]
        self.assertEqual(image.timestamp, timestamp)
        self.assertEqual(image.target(cost), string_ctor)
        self.assertEqual(image.target(action), string_ctor)
        self.assertEqual(image.target(submit_call), submit)
        self.assertEqual(
            image.read(post_submit_call - 3, 4),
            bytes.fromhex("55 8b ce e8"),
        )
        self.assertEqual(image.target(post_submit_call), post_submit_handler)
        self.assertEqual(
            image.read(general_control_call - 3, 4),
            bytes.fromhex("55 8b ce e8"),
        )
        self.assertEqual(image.target(general_control_call), post_submit_handler)
        self.assertEqual(
            struct.unpack("<I", image.read(selection_focus_jump_entry, 4))[0] - image.base,
            selection_focus_branch,
        )
        self.assertEqual(
            image.read(selection_focus_branch, 12),
            bytes.fromhex("8b 4e 24 8b 01 8b 50 68 6a 00 6a 00"),
        )
        self.assertEqual(
            struct.unpack("<I", image.read(action_focus_jump_entry, 4))[0] - image.base,
            action_focus_branch,
        )
        self.assertEqual(
            image.read(action_focus_branch, 12),
            bytes.fromhex("8b 17 8b 82 b8 00 00 00 8b cf ff d0"),
        )
        self.assertEqual(image.target(post_submit_handler + 0xEB), ui_manager)
        self.assertEqual(
            image.read(post_submit_handler + 0xF0, 6),
            bytes.fromhex("89 78 48 57 57 e8"),
        )
        self.assertEqual(
            image.target(post_submit_handler + 0xF5),
            image.target(post_submit_handler + 0xEB),
        )
        self.assertEqual(image.read(dispatch, 6), bytes.fromhex("55 8b ec 83 e4 f8"))
        table = struct.unpack("<15I", image.read(vtable, 60))
        for slot, rva in zip((0, 1, 3, 8, 11, 14), slots):
            self.assertEqual(table[slot] - image.base, rva)
        # The native child populates the generic Occupants relation (index 2).
        self.assertEqual(image.read(slots[4] + 0x4B, 8), bytes.fromhex("6a 02 8d 88 a4 00 00 00"))
        self.assertEqual(image.target(slots[5] + 3), list_refresh)
        # Shared setup installs the same row callback that draws generic visitors.
        setup = image.read(list_setup, 16)
        self.assertIn(b"\x68" + struct.pack("<I", image.base + list_callback), setup)
        callback = image.read(list_callback, 0x1B0)
        calls = [list_callback + offset for offset in range(len(callback) - 4)
                 if callback[offset] == 0xE8]
        self.assertIn(painter, [image.target(address) for address in calls])

    def test_public(self):
        self.verify("MAJESTY_PUBLIC_EXE", "kPublicOccupants", 0x5897B72F, 0xC4CF0, 0x25D00,
                    (0xBC2E0, 0xBC180, 0xBC0C0, 0xBBD90, 0xBC340, 0xBC1D0),
                    0x98EA0, 0x97E20, 0x98C60, 0x98360)

    def test_beta2(self):
        self.verify("MAJESTY_BETA2_EXE", "kBeta2Occupants", 0x5A8A11D5, 0xC5730, 0x26CD0,
                    (0xBCD20, 0xBCBC0, 0xBCB00, 0xBC7D0, 0xBCD80, 0xBCC10),
                    0x99510, 0x98640, 0x992D0, 0x98990)

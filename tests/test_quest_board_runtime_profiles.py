"""Read-only proof of the AP08/MX05 quest-board runtime on both builds."""

import os
from pathlib import Path
import re
import struct
import unittest

from test_occupant_runtime_profiles import PeImage


class QuestBoardRuntimeProfileTests(unittest.TestCase):
    def assert_gpl_result_type(
        self, image: PeImage, decorated_name: bytes, expected_tag: int
    ) -> None:
        def raw_to_rva(raw_offset: int) -> int:
            for virtual_size, address, raw_size, offset in image.sections:
                if offset <= raw_offset < offset + min(raw_size, virtual_size):
                    return address + raw_offset - offset
            raise ValueError(f"raw offset {raw_offset:#x} is not section-backed")

        name_offset = image.data.find(decorated_name + b"\0")
        self.assertGreaterEqual(name_offset, 8, decorated_name)
        type_descriptor = image.base + raw_to_rva(name_offset) - 8
        type_reference = struct.pack("<I", type_descriptor)
        complete_locators = []
        position = 0
        while True:
            position = image.data.find(type_reference, position)
            if position < 0:
                break
            if position >= 12:
                signature, offset, cd_offset, candidate, hierarchy = (
                    struct.unpack_from("<5I", image.data, position - 12)
                )
                if signature == 0 and candidate == type_descriptor:
                    complete_locators.append(
                        image.base + raw_to_rva(position - 12)
                    )
            position += 1
        self.assertTrue(complete_locators, decorated_name)

        vtables = []
        for locator in complete_locators:
            locator_reference = struct.pack("<I", locator)
            position = 0
            while True:
                position = image.data.find(locator_reference, position)
                if position < 0:
                    break
                vtables.append(image.base + raw_to_rva(position) + 4)
                position += 1
        self.assertTrue(vtables, decorated_name)
        tag_value = struct.pack("<I", expected_tag)

        def constructor_sets_tag(vtable: int) -> bool:
            reference = struct.pack("<I", vtable)
            position = 0
            while True:
                position = image.data.find(reference, position)
                if position < 0:
                    return False
                # Constructors use different destination registers. Require a
                # direct vtable reference followed in the same short basic
                # block by `mov dword ptr [reg+4], expected_tag`.
                window = image.data[position + 4:position + 68]
                if any(
                    b"\xC7" + bytes((modrm,)) + b"\x04" + tag_value in window
                    for modrm in range(0x40, 0x48)
                ):
                    return True
                position += 1

        self.assertTrue(
            any(constructor_sets_tag(vtable) for vtable in vtables),
            f"{decorated_name!r} no longer constructs stock type {expected_tag}",
        )

    def verify(
        self,
        variable: str,
        profile_name: str,
        timestamp: int,
        string_constructor: int,
        packed_attribute_reader: int,
        parent_slots: tuple[int, int, int, int],
        child_slots: tuple[int, int, int, int, int, int],
        shared_list_setup: int,
    ) -> None:
        path = os.environ.get(variable)
        if not path:
            self.skipTest(f"{variable} is not set")
        image = PeImage(path)
        source = (
            Path(__file__).resolve().parents[1]
            / "runtime/MajestyModManagerRuntime.cpp"
        ).read_text()
        body = re.search(
            rf"constexpr QuestBoardBuildProfile {profile_name} = \{{(.*?)\}};",
            source,
            re.S,
        )[1]
        (
            helper,
            evaluator_constructor,
            add_agent,
            add_integer,
            execute,
            scalar_result,
            result_at,
            evaluator_destructor,
            string_destructor,
            parent_vtable,
            row_name_call,
            row_name_target,
            row_attribute_call,
        ) = [int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]+", body)]

        self.assertEqual(image.timestamp, timestamp)
        self.assert_gpl_result_type(image, b".?AVGplInteger@@", 1)
        self.assertEqual(image.read(helper, 3), bytes.fromhex("6a ff 68"))
        for offset, target in (
            (0x2D, string_constructor),
            (0x43, evaluator_constructor),
            (0x51, string_destructor),
            (0x5F, add_agent),
            (0x68, execute),
            (0x71, scalar_result),
            (0x84, evaluator_destructor),
        ):
            self.assertEqual(image.target(helper + offset), target)
        self.assertEqual(image.read(add_integer, 4), bytes.fromhex("83 c1 08 e9"))
        self.assertEqual(image.target(scalar_result + 5), result_at)
        self.assertEqual(image.target(row_name_call), row_name_target)
        self.assertEqual(image.target(row_attribute_call), packed_attribute_reader)

        table = struct.unpack("<13I", image.read(parent_vtable, 13 * 4))
        for slot, expected in zip((0, 1, 3, 8), parent_slots):
            self.assertEqual(table[slot] - image.base, expected)
        self.assertEqual(
            image.read(parent_vtable + 13 * 4, 4),
            b"#gam",
            "AP08 vtable length changed; do not copy into adjacent string data",
        )
        parent_event = image.read(parent_slots[3], 0x60)
        for event_id in (0x06425041, 0x01425041, 0x05425041, 0x1E425041):
            self.assertIn(
                struct.pack("<I", event_id),
                parent_event,
                "AP08's stock primary-presentation event gate changed",
            )

        occupant_profiles = re.findall(
            r"constexpr OccupantBuildProfile (k(?:Public|Beta2)Occupants) = \{(.*?)\};",
            source,
            re.S,
        )
        occupant_name = (
            "kPublicOccupants" if profile_name == "kPublicQuestBoard"
            else "kBeta2Occupants"
        )
        occupant_values = next(
            [int(value, 16) for value in re.findall(r"0x[0-9A-Fa-f]+", body)]
            for name, body in occupant_profiles if name == occupant_name
        )
        child_vtable = occupant_values[-1]
        child_table = struct.unpack("<15I", image.read(child_vtable, 15 * 4))
        for slot, expected in zip((0, 1, 3, 8, 11, 14), child_slots):
            self.assertEqual(child_table[slot] - image.base, expected)

        setup = image.read(child_slots[1], 0x45)
        self.assertEqual(image.target(child_slots[1] + 0x33), shared_list_setup)
        self.assertIn(
            bytes.fromhex("8b 16 8b 42 28"), setup,
            "MX05 slot 1 no longer completes its final stock presentation",
        )
        shared_setup = image.read(shared_list_setup, 0x90)
        slot_12 = shared_setup.find(
            bytes.fromhex("8b 06 8b 50 30 8b ce ff d2")
        )
        slot_14 = shared_setup.find(
            bytes.fromhex("8b 16 8b 42 38 8b ce ff d0")
        )
        self.assertGreaterEqual(slot_12, 0)
        self.assertGreater(slot_14, slot_12)
        self.assertLess(
            slot_14,
            len(shared_setup) - 10,
            "MX05 slot 14 is no longer followed by final setup presentation",
        )

        population = child_slots[4]
        self.assertEqual(image.read(population + 0x3F, 1), b"\xE8")
        self.assertEqual(image.read(population + 0xDF, 1), b"\xE8")
        erase = image.target(population + 0x3F)
        insert = image.target(population + 0xDF)
        self.assertNotEqual(erase, insert)
        self.assertTrue(image.read(erase, 1))
        self.assertTrue(image.read(insert, 1))

        event = image.read(child_slots[3], 0x80)
        self.assertIn(struct.pack("<I", 0x09435358), event)
        self.assertIn(
            bytes.fromhex("8b 50 38 ff d2"), event,
            "MX05 event no longer invokes vtable slot 14 for XSCX",
        )

    def test_public(self) -> None:
        self.verify(
            "MAJESTY_PUBLIC_EXE",
            "kPublicQuestBoard",
            0x5897B72F,
            0x227A80,
            0x1B9FD0,
            (0x9E2A0, 0x9E5D0, 0x9E660, 0x9E600),
            (0xBC2E0, 0xBC180, 0xBC0C0, 0xBBD90, 0xBC340, 0xBC1D0),
            0x98EA0,
        )

    def test_beta2(self) -> None:
        self.verify(
            "MAJESTY_BETA2_EXE",
            "kBeta2QuestBoard",
            0x5A8A11D5,
            0x23A220,
            0x1CEF70,
            (0x9EB80, 0x9EEB0, 0x9EF40, 0x9EEE0),
            (0xBCD20, 0xBCBC0, 0xBCB00, 0xBC7D0, 0xBCD80, 0xBCC10),
            0x99510,
        )


if __name__ == "__main__":
    unittest.main()

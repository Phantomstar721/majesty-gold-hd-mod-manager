from pathlib import Path
from dataclasses import replace
import os
import struct
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.cam import CamEntry, pad_name
from majesty_cam.compose import (
    CamResource, ComposeError, _validate_mx22_toggle_controls,
    _validate_private_ap10_button_art, _validate_authored_building_toggle_controls,
)
from majesty_cam.stock_controller_registry import ResolvedBuildingOpenToggleRecord, ResolvedControllerRegistry


def _record(command: int, image: int, label: int, tooltip: int, rectangle) -> list[int]:
    return [
        0xFFFFFFFF, 0, 2,
        *rectangle,
        7,
        label,
        0x21,
        tooltip,
        0x0A, 2, 0x0C, 0x62424E49, 0x0D, 0x3ED,
        0x14, 4, 3, 2, 3, 0x400, 5, image, 6,
        command,
        0x12, 0x37746E66, 0x24, 3, 0x8000003F,
        0x40000000, 0x40000000, 0xFFFFFFFF,
    ]


def _ap39_record(command: int, label: int, tooltip: int, rectangle) -> list[int]:
    return [
        0, 2,
        *rectangle,
        7,
        label,
        0x21,
        tooltip,
        0x0A, 2, 0x0C, 0x62424E49, 0x0D, 0x3F8,
        3, 2, 3, 0x400, 5, 0x52, 6,
        command,
        0x12, 0x34746E66, 0x24, 3, 0x8000003F,
        0x40000000, 0x40000000, 0x102, 0x45, 0x10A, 0x4E,
        0xFFFFFFFF,
    ]


def _ap10_record(
    command: int,
    label: int,
    tooltip: int,
    rectangle,
    image_set: int = 1004,
) -> list[int]:
    return [
        0, 2,
        *rectangle,
        0x2A, 0x16, 0x04, 0x44, 0x12, 0x07,
        label,
        0x21,
        tooltip,
        0x0A, 2, 0x0C, 0x62424E49, 0x0D, image_set,
        0x14, 1, 0x14, 8, 0x14, 4,
        3, 2, 3, 0x400, 5, 0x53, 6,
        command,
        0x2C, 2, 0x12, 0x34746E66, 0x24, 3,
        0x8000003F, 0x40000000, 0x40000000,
        0x102, 0x5A, 0x10A, 0x43,
        0xFFFFFFFF,
    ]


class BuildingOpenToggleEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.toggle = ResolvedBuildingOpenToggleRecord(
            "owner-qualified-rentals", int.from_bytes(b"Z001", "little"),
            10801, 10802, "MX09",
        )

    def payload(self) -> bytes:
        values = [0, 2, 7]
        values += _record(10802, 67, 28, 29, (7, 219, 139, 21))
        values += [0, 2]
        values += _record(10801, 79, 30, 31, (103, 217, 93, 26))
        values += [0xFFFFFFFF]
        return struct.pack(f"<{len(values)}I", *values)

    def test_package_owned_text_and_layout_are_allowed(self) -> None:
        _validate_mx22_toggle_controls(
            self.payload(), self.toggle, owner="fixture", panel_label="MX09"
        )

    def test_opcode_or_stock_image_change_fails_closed(self) -> None:
        payload = bytearray(self.payload())
        image = struct.pack("<I", 79)
        offset = payload.rfind(image)
        struct.pack_into("<I", payload, offset, 80)
        with self.assertRaisesRegex(ComposeError, "literal MX22 open"):
            _validate_mx22_toggle_controls(
                bytes(payload), self.toggle, owner="fixture", panel_label="MX09"
            )

    def test_ap39_half_width_pair_is_accepted_in_combined_parent(self) -> None:
        values = [0, 2, 7, 0xFFFFFFFF]
        # The parent may already expose an ordinary reward action and an
        # occupant-panel opener.  Those unrelated controls must not make the
        # manager confuse their commands with the paired toggle presentation.
        values += _ap39_record(0x1389, 22, 23, (7, 190, 89, 22))
        values += [0, 2, 7, 217, 93, 26, 6, 0x2A30, 0xFFFFFFFF]
        values += _ap39_record(10802, 28, 29, (106, 190, 89, 22))
        values += _ap39_record(10801, 30, 31, (106, 190, 89, 22))
        values += [0xFFFFFFFF]
        payload = struct.pack(f"<{len(values)}I", *values)

        _validate_mx22_toggle_controls(
            payload, self.toggle, owner="fixture", panel_label="MX09"
        )

    def test_ap39_art_or_font_change_fails_closed(self) -> None:
        values = [0, 2, 7, 0xFFFFFFFF]
        values += _ap39_record(10802, 28, 29, (106, 190, 89, 22))
        values += _ap39_record(10801, 30, 31, (106, 190, 89, 22))
        values += [0xFFFFFFFF]
        first_control = 4
        values[first_control + 15] = 0x3F9
        payload = struct.pack(f"<{len(values)}I", *values)

        with self.assertRaisesRegex(ComposeError, "audited AP39"):
            _validate_mx22_toggle_controls(
                payload, self.toggle, owner="fixture", panel_label="MX09"
            )

    def test_ap10_action_pair_is_accepted_with_package_owned_image_set(self) -> None:
        values = [0, 2, 7, 0xFFFFFFFF]
        values += _ap10_record(10802, 28, 29, (103, 190, 93, 26), 1004)
        values += _ap10_record(10801, 30, 31, (103, 190, 93, 26), 4097)
        values += [0xFFFFFFFF]
        payload = struct.pack(f"<{len(values)}I", *values)

        _validate_mx22_toggle_controls(
            payload, self.toggle, owner="fixture", panel_label="MX09"
        )

    def test_ap10_art_token_or_opcode_change_fails_closed(self) -> None:
        values = [0, 2, 7, 0xFFFFFFFF]
        first_control = len(values)
        values += _ap10_record(10802, 28, 29, (103, 190, 93, 26))
        values += _ap10_record(10801, 30, 31, (103, 190, 93, 26))
        values += [0xFFFFFFFF]
        # A private token without its package-owned art evidence still fails.
        values[first_control + 18] = 0x4242435A
        payload = struct.pack(f"<{len(values)}I", *values)

        with self.assertRaisesRegex(ComposeError, "audited AP10"):
            _validate_mx22_toggle_controls(
                payload, self.toggle, owner="fixture", panel_label="MX09"
            )

    def private_art_inventory(self):
        # Literal stock INBb/1009 structure, with compact private TILE indices.
        words = [7, 0, 0, 256] + [0] * 12 + [92 + 32 * i for i in range(7)]
        for tile in (0, 1, 2, 2, 2, 2, 3):
            words += [0, 65537, 0, 0, 65536, 0, 0, tile]
        payload = struct.pack('<79I', *words)
        image = struct.pack('<8I', 4, 0, 0, 0, 0, 1, 4097, 32) + payload
        tile = struct.pack('<10HHI', 3, 26, 93, 0, 0, 0, 0, 0, 0, 0, 1, 26) + bytes(1032)
        resources = [CamResource('fixture', Path('source.cam'), 0, 0, 0, b'IMAG', CamEntry(pad_name(b'PBTN'), image))]
        resources += [CamResource('fixture', Path('source.cam'), 0, 1, i, b'TILE', CamEntry(pad_name(str(i)), tile)) for i in range(4)]
        return SimpleNamespace(selected=SimpleNamespace(alias='fixture'), resources=tuple(resources))

    def private_pair(self):
        values = [0, 2, 7, 0xFFFFFFFF]
        for command in (10801, 10802):
            row = _ap10_record(command, 28, 29, (103, 190, 93, 26), 4097)
            row[18] = int.from_bytes(b'PBTN', 'little')
            values += row
        return struct.pack(f'<{len(values)+1}I', *values, 0xFFFFFFFF)

    def test_private_button_art_is_proved_in_authored_preflight_without_file_reads(self):
        inventory = self.private_art_inventory()
        inventory.resources += (CamResource('fixture', Path('panel.cam'), 0, 0, 0, b'SMNU',
                                           CamEntry(pad_name(b'Z001'), self.private_pair())),)
        registry = ResolvedControllerRegistry((), (), (), (), (), (), (), building_open_toggles=(self.toggle,))
        mapping = SimpleNamespace(owner='fixture', raw_parent_building='Example', raw_toggle_key='rentals',
                                  qualified_toggle_key=self.toggle.toggle_key)
        before = inventory.resources
        with patch('majesty_cam.compose._description_dialog_sources', return_value={'Z001'}), \
             patch('majesty_cam.compose.read_cam', side_effect=AssertionError('must reuse inventory')):
            _validate_authored_building_toggle_controls((inventory,), registry, (mapping,))
        self.assertEqual(inventory.resources, before)

    def test_private_button_art_malformed_or_unowned_data_is_rejected(self):
        inventory = self.private_art_inventory()
        image = inventory.resources[0]
        variants = []
        # Missing/duplicate/cross-owner IMAG, split or missing TILE storage.
        variants += [inventory.resources[1:], inventory.resources + (image,),
                     (replace(image, owner='other'),) + inventory.resources[1:],
                     inventory.resources[:-1],
                     (image,) + tuple(replace(r, source=Path('other.cam')) for r in inventory.resources[1:])]
        for offset, value in ((0, 5), (24, 9999), (32, 6), (44, 257), (32+216, 1), (32+120, 99)):
            payload = bytearray(image.entry.data)
            struct.pack_into('<I', payload, offset, value)
            variants.append((replace(image, entry=replace(image.entry, data=bytes(payload))),) + inventory.resources[1:])
        for data in (b'', inventory.resources[1].entry.data[:26],
                     struct.pack('<H', 1) + inventory.resources[1].entry.data[2:],
                     inventory.resources[1].entry.data[:4] + struct.pack('<H', 94) + inventory.resources[1].entry.data[6:]):
            variants.append((image, replace(inventory.resources[1], entry=CamEntry(pad_name('bad'), data))) + inventory.resources[2:])
        for resources in variants:
            candidate = SimpleNamespace(selected=inventory.selected, resources=resources)
            with self.subTest(resources=resources[0].section if resources else None), self.assertRaises(ComposeError):
                _validate_mx22_toggle_controls(self.private_pair(), self.toggle, owner='fixture', panel_label='Z001',
                    private_art_validator=lambda key, set_id: _validate_private_ap10_button_art(candidate, key, set_id))

    def test_private_art_does_not_relax_stock_widget_geometry_or_commands(self):
        inventory = self.private_art_inventory()
        for offset, value in ((4, 94), (5, 27), (7, 23), (32, 0x54), (34, 10803), (36, 3)):
            payload = bytearray(self.private_pair())
            struct.pack_into('<I', payload, (4 + offset) * 4, value)
            with self.subTest(offset=offset), self.assertRaises(ComposeError):
                _validate_mx22_toggle_controls(bytes(payload), self.toggle, owner='fixture', panel_label='Z001',
                    private_art_validator=lambda key, set_id: _validate_private_ap10_button_art(inventory, key, set_id))

    def test_button_art_fingerprint_matches_installed_stock_reference(self):
        executable = os.environ.get('MAJESTY_BETA2_EXE') or os.environ.get('MAJESTY_PUBLIC_EXE')
        if not executable:
            self.skipTest('stock CAM fixtures are not configured')
        from majesty_cam.compose import _require_cam_entry, _split_imag_sets, _join_imag_sets
        from majesty_cam.cam import read_cam
        source = Path(executable).parent / 'Data' / 'interfacedata.cam'
        stock = _require_cam_entry(source, b'IMAG', b'INBb')
        header, sets = _split_imag_sets(stock)
        private = _join_imag_sets(CamEntry(pad_name(b'PBTN'), b''), header, ((4097, dict(sets)[1009]),))
        tiles = next(s for s in read_cam(source).sections if s.extension == b'TILE')
        resources = (CamResource('fixture', source, 0, 0, 0, b'IMAG', private),) + tuple(
            CamResource('fixture', source, 0, 1, i, b'TILE', entry) for i, entry in enumerate(tiles.entries))
        _validate_private_ap10_button_art(SimpleNamespace(selected=SimpleNamespace(alias='fixture'), resources=resources), b'PBTN', 4097)

    def test_mixed_mx22_and_ap39_pair_is_rejected(self) -> None:
        values = [0, 2, 7]
        values += _record(10802, 67, 28, 29, (7, 219, 139, 21))
        values += _ap39_record(10801, 30, 31, (106, 190, 89, 22))
        values += [0xFFFFFFFF]
        payload = struct.pack(f"<{len(values)}I", *values)

        with self.assertRaisesRegex(ComposeError, "coherent pair"):
            _validate_mx22_toggle_controls(
                payload, self.toggle, owner="fixture", panel_label="MX09"
            )

    def test_mixed_ap39_and_ap10_pair_is_rejected(self) -> None:
        values = [0, 2, 7]
        values += _ap39_record(10802, 28, 29, (106, 190, 89, 22))
        values += _ap10_record(10801, 30, 31, (103, 190, 93, 26))
        values += [0xFFFFFFFF]
        payload = struct.pack(f"<{len(values)}I", *values)

        with self.assertRaisesRegex(ComposeError, "coherent pair"):
            _validate_mx22_toggle_controls(
                payload, self.toggle, owner="fixture", panel_label="MX09"
            )


if __name__ == "__main__":
    unittest.main()

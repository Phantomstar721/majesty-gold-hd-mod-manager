from pathlib import Path
import struct
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.compose import ComposeError, _validate_mx22_toggle_controls
from majesty_cam.stock_controller_registry import ResolvedBuildingOpenToggleRecord


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


if __name__ == "__main__":
    unittest.main()

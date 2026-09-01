from dataclasses import replace
from pathlib import Path
import struct
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.stock_controller_features import (
    StockAp41Fl00HostileMonsterFlag,
    StockMx09Ap41RewardPanel,
    StockAp10Ap69SecondaryPanel,
    legacy_alchemist_controller_features,
)
from majesty_cam.stock_controller_registry import (
    CONTROLLER_REGISTRY_ENVIRONMENT,
    CONTROLLER_REGISTRY_MAGIC,
    CONTROLLER_REGISTRY_RELATIVE_PATH,
    ControllerRegistryError,
    decode_stock_controller_registry,
    encode_stock_controller_registry,
    resolve_stock_controller_registry,
    write_stock_controller_registry,
)


class StockControllerRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.features = legacy_alchemist_controller_features(
            "AlchemistsLaboratory"
        )
        self.registry = resolve_stock_controller_registry(
            self.features,
            {"brewing": (
                int.from_bytes(b"CGAL", "little"),
                int.from_bytes(b"CGBR", "little"),
            )},
        )
        self.payload = encode_stock_controller_registry(self.registry)

    def test_exact_legacy_records_round_trip_in_nine_bounded_sections(self) -> None:
        self.assertEqual(decode_stock_controller_registry(self.payload), self.registry)
        magic, version, *counts = struct.unpack_from("<4s10I", self.payload)
        self.assertEqual(magic, CONTROLLER_REGISTRY_MAGIC)
        self.assertEqual(version, 2)
        self.assertEqual(counts, [1, 1, 2, 1, 1, 1, 1, 0, 0])
        self.assertNotIn(b".dll", self.payload.lower())
        self.assertNotIn(b"42ba4603", self.payload.lower())

    def test_encoding_is_canonical_for_order_and_duplicates(self) -> None:
        self.assertEqual(
            encode_stock_controller_registry(
                decode_stock_controller_registry(self.payload)
            ),
            self.payload,
        )

    def test_registry_identity_is_distinct_from_other_runtime_data(self) -> None:
        self.assertEqual(CONTROLLER_REGISTRY_ENVIRONMENT,
                         "MAJESTY_MOD_MANAGER_CONTROLLERS")
        self.assertEqual(
            CONTROLLER_REGISTRY_RELATIVE_PATH.as_posix(),
            "DataMX/majesty_mod_manager_controllers.bin",
        )

    def test_multiple_panel_recipes_are_canonical_and_composable(self) -> None:
        alpha = StockAp10Ap69SecondaryPanel(
            panel_key="alpha", parent_building="alpha-building",
            source_dialog_id="PX01", building_family_id="AXA",
            open_command_id=0x4001,
        )
        beta = StockAp10Ap69SecondaryPanel(
            panel_key="beta", parent_building="beta-building",
            source_dialog_id="PX02", building_family_id="BXB",
            open_command_id=0x4002,
        )
        registry = resolve_stock_controller_registry(
            (beta, alpha),
            {
                "alpha": (int.from_bytes(b"PA01", "little"), int.from_bytes(b"PX01", "little")),
                "beta": (int.from_bytes(b"PB01", "little"), int.from_bytes(b"PX02", "little")),
            },
        )
        payload = encode_stock_controller_registry(registry)
        self.assertEqual(decode_stock_controller_registry(payload), registry)

    def test_every_truncation_and_trailing_data_fail_closed(self) -> None:
        for size in range(len(self.payload)):
            with self.subTest(size=size):
                with self.assertRaises(ControllerRegistryError):
                    decode_stock_controller_registry(self.payload[:size])
        with self.assertRaisesRegex(ControllerRegistryError, "trailing|canonical"):
            decode_stock_controller_registry(self.payload + b"\x00")

    def test_header_bounds_and_invalid_text_fail_closed(self) -> None:
        wrong_magic = b"FAIL" + self.payload[4:]
        with self.assertRaisesRegex(ControllerRegistryError, "magic"):
            decode_stock_controller_registry(wrong_magic)

        wrong_version = bytearray(self.payload)
        struct.pack_into("<I", wrong_version, 4, 1)
        with self.assertRaisesRegex(ControllerRegistryError, "version"):
            decode_stock_controller_registry(bytes(wrong_version))

        too_many = bytearray(self.payload)
        struct.pack_into("<I", too_many, 8, 257)
        with self.assertRaisesRegex(ControllerRegistryError, "count"):
            decode_stock_controller_registry(bytes(too_many))

        invalid_cp1252 = bytearray(self.payload)
        text_offset = self.payload.index(b"Weapon Oil")
        invalid_cp1252[text_offset] = 0x81
        with self.assertRaisesRegex(ControllerRegistryError, "invalid cp1252"):
            decode_stock_controller_registry(bytes(invalid_cp1252))

        embedded_nul = bytearray(self.payload)
        embedded_nul[text_offset] = 0
        with self.assertRaisesRegex(ControllerRegistryError, "contains NUL"):
            decode_stock_controller_registry(bytes(embedded_nul))

    def test_noncanonical_record_order_is_rejected(self) -> None:
        alpha = StockAp10Ap69SecondaryPanel(
            panel_key="alpha", parent_building="first-building",
            source_dialog_id="PX01", building_family_id="AXA",
            open_command_id=0x4001,
        )
        beta = replace(
            alpha, panel_key="bravo", parent_building="other-building",
            source_dialog_id="PX02", building_family_id="BXB",
            open_command_id=0x4002,
        )
        registry = resolve_stock_controller_registry(
            (alpha, beta),
            {
                "alpha": (int.from_bytes(b"PA01", "little"), int.from_bytes(b"PX01", "little")),
                "bravo": (int.from_bytes(b"PB01", "little"), int.from_bytes(b"PX02", "little")),
            },
        )
        canonical = encode_stock_controller_registry(registry)

        # Decode the two variable-size panel records only to exchange their
        # exact byte ranges.  The malformed payload remains structurally valid.
        cursor = struct.calcsize("<4s10I")
        records = []
        for _ in range(2):
            start = cursor
            length = struct.unpack_from("<I", canonical, cursor)[0]
            cursor += 4 + length
            cursor += 16
            records.append(canonical[start:cursor])
        reversed_payload = canonical[:struct.calcsize("<4s10I")] + records[1] + records[0]
        with self.assertRaisesRegex(ControllerRegistryError, "canonical"):
            decode_stock_controller_registry(reversed_payload)

    def test_atomic_writer_writes_only_the_canonical_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "nested" / "controllers.bin"
            normalized = write_stock_controller_registry(
                destination, self.registry
            )
            self.assertEqual(normalized, self.registry)
            self.assertEqual(destination.read_bytes(), self.payload)
            self.assertEqual(list(destination.parent.glob("*.tmp")), [])

    def test_resolver_requires_explicit_dialogs_and_unique_game_namespaces(self) -> None:
        with self.assertRaisesRegex(ControllerRegistryError, "exactly every"):
            resolve_stock_controller_registry(self.features, {})

        first = StockAp10Ap69SecondaryPanel(
            panel_key="alpha", parent_building="one",
            source_dialog_id="PX01", building_family_id="DUP",
            open_command_id=0x4001,
        )
        second = replace(
            first, panel_key="beta", parent_building="two",
            source_dialog_id="PX02", open_command_id=0x4002,
        )
        with self.assertRaisesRegex(ControllerRegistryError, "family"):
            resolve_stock_controller_registry(
                (first, second),
                {
                    "alpha": (int.from_bytes(b"PA01", "little"), int.from_bytes(b"PX01", "little")),
                    "beta": (int.from_bytes(b"PB01", "little"), int.from_bytes(b"PX02", "little")),
                },
            )

    def test_generated_registry_rejects_a_stock_ap99_command_key(self) -> None:
        corrupted = replace(
            self.registry,
            research_rows=(
                replace(self.registry.research_rows[0], action_control_id=0x139C),
                *self.registry.research_rows[1:],
            ),
        )
        with self.assertRaisesRegex(
            ControllerRegistryError, "reserved stock AP99 control range"
        ):
            encode_stock_controller_registry(corrupted)

    def test_reward_panel_and_hostile_flag_round_trip_without_package_identity(self) -> None:
        features = (
            StockMx09Ap41RewardPanel(
                "rewards", "private-building", "PX41", 5001,
            ),
            StockAp41Fl00HostileMonsterFlag(
                "rewards", "capture", "RF01", "RF01", 38,
                "AZ0", "No room remains",
            ),
        )
        registry = resolve_stock_controller_registry(
            features,
            {"rewards": (
                int.from_bytes(b"PB01", "little"),
                int.from_bytes(b"PC01", "little"),
            )},
            flag_prototypes={"capture": "Private_Reward_Flag"},
        )
        payload = encode_stock_controller_registry(registry)
        self.assertEqual(decode_stock_controller_registry(payload), registry)
        self.assertEqual(registry.reward_panels[0].child_dialog_id,
                         int.from_bytes(b"PC01", "little"))
        self.assertEqual(registry.hostile_monster_flags[0].flag_prototype_name,
                         "Private_Reward_Flag")


if __name__ == "__main__":
    unittest.main()

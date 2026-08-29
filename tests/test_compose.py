from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.art import (
    compute_stock_relative_delta,
    find_positional_collisions,
)
from majesty_cam.cam import CamEntry, CamSection, pad_name
from majesty_cam.compose import (
    CamResource,
    ComposeError,
    ScopedSemanticResolution,
    SelectedMod,
    _blank_positional_section,
    _build_manifest,
    _derive_runtime_capabilities,
    _first_free_after_reserved,
    _generated_definition,
    _generated_mod_id,
    _materialize_effective_stock_prefix,
    _select_later_conflict_runs,
    merge_named_resources,
    merge_gpl_resources,
)
from majesty_cam.gpl import GplProjectSourceSet, parse_gpl
from majesty_cam.package import CustomBuildingDefinition, ModDefinition
from majesty_cam.runtime_capabilities import (
    PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY,
    decode_runtime_capability_manifest,
)


def resource(owner, key, payload, order=0):
    return CamResource(
        owner=owner,
        source=Path(f"{owner}.cam"),
        cam_order=0,
        section_order=0,
        entry_order=order,
        section=b"SMNU",
        entry=CamEntry(name=pad_name(key), data=payload),
    )


def positional(extension, payloads):
    return CamSection(
        extension=extension,
        entries=tuple(
            CamEntry(name=index.to_bytes(4, "little").ljust(20, b"\x00"), data=data)
            for index, data in enumerate(payloads)
        ),
    )


class NamedComposeTests(unittest.TestCase):
    def test_named_union_preserves_order_accepts_identical_and_renames(self):
        resources = (
            resource("haunt", b"AP07", b"panel"),
            resource("alchemist", b"CGAL", b"lab", 1),
            resource("other", b"CGAL", b"lab", 2),
        )

        entries, selections = merge_named_resources(
            resources,
            b"SMNU",
            renames={("haunt", b"AP07"): b"CGPH"},
        )

        self.assertEqual([entry.name[:4] for entry in entries], [b"CGPH", b"CGAL"])
        self.assertEqual(selections[1].owners, ("alchemist", "other"))

    def test_named_union_rejects_divergence_and_duplicate_owner(self):
        with self.assertRaisesRegex(ComposeError, "conflicting SMNU"):
            merge_named_resources(
                (resource("a", b"SAME", b"one"), resource("b", b"SAME", b"two")),
                b"SMNU",
            )
        with self.assertRaisesRegex(ComposeError, "duplicate SMNU"):
            merge_named_resources(
                (resource("a", b"SAME", b"one"), resource("a", b"SAME", b"one", 1)),
                b"SMNU",
            )


class PositionalComposeTests(unittest.TestCase):
    def test_later_owner_moves_complete_contiguous_conflict_run(self):
        stock = positional(b"TILE", [b"s0", b"s1", b"s2", b"s3", b"s4"])
        alchemist = positional(
            b"TILE", [b"", b"", b"", b"", b"", b"a5", b"a6", b"a7"]
        )
        haunt = positional(
            b"TILE", [b"", b"", b"", b"", b"h4", b"h5", b"h6", b"h7", b"h8"]
        )
        deltas = {
            "alchemist": compute_stock_relative_delta(stock, alchemist),
            "haunt": compute_stock_relative_delta(stock, haunt),
        }
        collisions = find_positional_collisions(deltas)

        selected = _select_later_conflict_runs(
            deltas, collisions, {"alchemist": 0, "haunt": 1}
        )

        self.assertEqual(selected["alchemist"], set())
        self.assertEqual(selected["haunt"], {4, 5, 6, 7, 8})
        self.assertEqual(_first_free_after_reserved(deltas, selected), 8)

    def test_blank_stock_slots_do_not_redistribute_payloads(self):
        stock = positional(b"TILE", [b"proprietary-0", b"proprietary-1"])
        output = _blank_positional_section(stock, 3)
        self.assertEqual([entry.data for entry in output], [b"", b"", b""])
        self.assertEqual(output[0].name, stock.entries[0].name)
        self.assertEqual(output[2].name[:4], (2).to_bytes(4, "little"))

    def test_effective_stock_prefix_fills_only_unresolved_slots(self):
        stock = positional(b"SPLT", [b"stock-0", b"stock-1"])
        output = _blank_positional_section(stock, 3)
        output[1] = CamEntry(name=output[1].name, data=b"mod-1")

        _materialize_effective_stock_prefix(output, stock)

        self.assertEqual(
            [entry.data for entry in output],
            [b"stock-0", b"mod-1", b""],
        )


class ScopedGplResolutionTests(unittest.TestCase):
    def test_pair_resolution_allows_unrelated_third_mod_but_rejects_contributor(self):
        def parsed(owner, function_name, value):
            return parse_gpl(
                f"function {function_name}() is integer\n"
                f"begin\nreturn {value};\nend\n",
                f"{owner}.gpl",
            )

        inventories = tuple(
            SimpleNamespace(selected=SimpleNamespace(alias=owner))
            for owner in ("first", "second", "third")
        )
        sources = {
            "first": parsed("first", "Shared_Result", 1),
            "second": parsed("second", "Shared_Result", 2),
            "third": parsed("third", "Unrelated_Result", 9),
        }
        resolution_item = parsed("resolution", "Shared_Result", 3).items[0]
        scoped = ScopedSemanticResolution(
            item=resolution_item,
            participant_owners=frozenset(("first", "second")),
        )
        key = resolution_item.key

        with patch(
            "majesty_cam.compose._parse_inventory_gpl_sources",
            side_effect=lambda inventory: [sources[inventory.selected.alias]],
        ):
            result = merge_gpl_resources(
                inventories,
                semantic_resolutions={key: scoped},
            )

        self.assertIn("return 3", result.source_set.gpl_text)
        self.assertIn("Unrelated_Result", result.source_set.gpl_text)

        sources["third"] = parsed("third", "Shared_Result", 4)
        with patch(
            "majesty_cam.compose._parse_inventory_gpl_sources",
            side_effect=lambda inventory: [sources[inventory.selected.alias]],
        ), self.assertRaisesRegex(
            ComposeError,
            "additional mod owners.*third",
        ):
            merge_gpl_resources(
                inventories,
                semantic_resolutions={key: scoped},
            )

        sources["third"] = parsed("third", "Shared_Result", 1)
        with patch(
            "majesty_cam.compose._parse_inventory_gpl_sources",
            side_effect=lambda inventory: [sources[inventory.selected.alias]],
        ):
            duplicate_variant = merge_gpl_resources(
                inventories,
                semantic_resolutions={key: scoped},
            )

        self.assertIn("return 3", duplicate_variant.source_set.gpl_text)

        sources["third"] = parsed("third", "Shared_Result", 3)
        with patch(
            "majesty_cam.compose._parse_inventory_gpl_sources",
            side_effect=lambda inventory: [sources[inventory.selected.alias]],
        ):
            resolved_variant = merge_gpl_resources(
                inventories,
                semantic_resolutions={key: scoped},
            )

        self.assertIn("return 3", resolved_variant.source_set.gpl_text)


class ProfileIdentityTests(unittest.TestCase):
    def test_private_text_runtime_capability_is_derived_not_caller_asserted(self):
        other = "freestyle-cam-rebind.v1"
        without_records, without_payload = _derive_runtime_capabilities(
            (other, PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY),
            has_private_activity_text=False,
        )
        with_records, with_payload = _derive_runtime_capabilities(
            (other,),
            has_private_activity_text=True,
        )

        self.assertEqual(without_records, (other,))
        self.assertEqual(
            decode_runtime_capability_manifest(without_payload),
            without_records,
        )
        self.assertEqual(
            with_records,
            (other, PRIVATE_ACTIVITY_TEXT_RUNTIME_CAPABILITY),
        )
        self.assertEqual(
            decode_runtime_capability_manifest(with_payload),
            with_records,
        )

    def test_generated_definition_round_trips_exact_runtime_capabilities(self):
        source_definition = ModDefinition(
            schema_version=2,
            mod_id="{00000000-0000-0000-0000-000000000001}",
            internal_name="Fixture",
            display_name="Fixture",
            custom_buildings=(
                CustomBuildingDefinition(
                    local_name="FixtureGuild",
                    dialog_id="CGFX",
                    controller_base="CGGuild",
                    panel_resource_template="CGFX",
                ),
            ),
            runtime_capabilities=(),
        )
        selected = (
            SelectedMod(
                "fixture",
                SimpleNamespace(definition=source_definition),
            ),
        )
        for capabilities in (
            (),
            (
                "expanded-building-slots.cg-prefix",
                "freestyle-cam-rebind.v1",
            ),
        ):
            with self.subTest(capabilities=capabilities):
                payload = _generated_definition(
                    source_definition.mod_id,
                    "GeneratedFixture",
                    "Generated Fixture",
                    selected,
                    capabilities,
                )

                self.assertEqual(payload["schema_version"], 2)
                self.assertEqual(
                    tuple(payload["runtime_capabilities"]), capabilities
                )

    def test_generated_ids_are_distinct_stable_and_ordered(self):
        first = SelectedMod("first", SimpleNamespace(mod_id="{00000000-0000-0000-0000-000000000001}"))
        second = SelectedMod("second", SimpleNamespace(mod_id="{00000000-0000-0000-0000-000000000002}"))
        single = _generated_mod_id((first,), "first-only")
        self.assertNotEqual(
            single, "{00000000-0000-0000-0000-000000000001}"
        )
        self.assertEqual(single, _generated_mod_id((first,), "first-only"))
        self.assertNotEqual(single, _generated_mod_id((first,), "alternate"))
        combined = _generated_mod_id((first, second), "combined")
        self.assertEqual(combined, _generated_mod_id((first, second), "combined"))
        self.assertNotEqual(
            combined, _generated_mod_id((second, first), "combined")
        )

    def test_manifest_preserves_native_load_order(self):
        source_set = GplProjectSourceSet(
            project_text='data="Merged.dat"\nsource="Merged.gpl"\n',
            gpl_filename="Merged.gpl",
            gpl_text="Function X()\nBegin\nEnd\n",
            dat_filename="Merged.dat",
            dat_text="[X]\n[end]\n",
        )
        payload = _build_manifest(
            mod_id="{00000000-0000-0000-0000-000000000001}",
            internal_name="Fixture",
            display_name="Fixture",
            cam_filenames=("one.cam", "two.cam"),
            description_filename="merged.xml",
            source_set=source_set,
        )
        load = ET.fromstring(payload).find("./Mod/DataConfiguration/Dataset/Load")
        self.assertIsNotNone(load)
        self.assertEqual(
            [child.tag for child in load],
            ["CAM", "CAM", "Descriptions", "GPL"],
        )
        self.assertEqual(
            [child.tag for child in load.find("GPL")],
            ["Target", "Source", "Source"],
        )


if __name__ == "__main__":
    unittest.main()

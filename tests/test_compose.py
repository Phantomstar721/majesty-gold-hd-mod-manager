from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
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
    SelectedMod,
    _blank_positional_section,
    _build_manifest,
    _first_free_after_reserved,
    _generated_mod_id,
    _materialize_effective_stock_prefix,
    _select_later_conflict_runs,
    merge_named_resources,
)
from majesty_cam.gpl import GplProjectSourceSet


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


class ProfileIdentityTests(unittest.TestCase):
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

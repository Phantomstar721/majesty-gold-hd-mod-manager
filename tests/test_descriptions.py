from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.descriptions import (
    DescriptionFormatError,
    DescriptionMergeConflict,
    DescriptionResolutionError,
    merge_descriptions,
    parse_descriptions,
)


def document(*records, attributes=""):
    return (
        f"<Majesty{attributes}>\n"
        + "\n".join(records)
        + "\n</Majesty>"
    )


def record(record_type, description_id, value, *, extra=""):
    return (
        f'<Description type="{record_type}" ID="{description_id}"{extra}>'
        f'<Game><Value value="{value}" /></Game></Description>'
    )


class DescriptionParsingTests(unittest.TestCase):
    def test_indexes_case_sensitive_keys_in_source_order(self):
        parsed = parse_descriptions(
            document(
                record("Unit", "Same", "first"),
                record("unit", "Same", "second"),
                record("Unit", "same", "third"),
            )
        )
        self.assertEqual(
            [item.key for item in parsed.records],
            [("Unit", "Same"), ("unit", "Same"), ("Unit", "same")],
        )
        self.assertEqual(parsed.index[("unit", "Same")].description_id, "Same")

    def test_rejects_duplicate_missing_and_malformed_records(self):
        duplicate = document(
            record("Unit", "U001", "a"), record("Unit", "U001", "b")
        )
        with self.assertRaisesRegex(DescriptionFormatError, "duplicate"):
            parse_descriptions(duplicate, source="duplicate.xml")
        with self.assertRaisesRegex(DescriptionFormatError, "non-empty type"):
            parse_descriptions(
                '<Majesty><Description ID="U001" /></Majesty>'
            )
        with self.assertRaisesRegex(DescriptionFormatError, "not valid XML"):
            parse_descriptions("<Majesty><Description></Majesty>")

    def test_rejects_dtd_and_unknown_top_level_elements(self):
        with self.assertRaisesRegex(DescriptionFormatError, "forbidden"):
            parse_descriptions(
                '<!DOCTYPE Majesty [<!ENTITY x "boom">]>'
                '<Majesty><Description type="Unit" ID="U001" /></Majesty>'
            )
        with self.assertRaisesRegex(DescriptionFormatError, "unsupported top-level"):
            parse_descriptions("<Majesty><Include /></Majesty>")
        with self.assertRaisesRegex(DescriptionFormatError, "unexpected text"):
            parse_descriptions(
                '<Majesty><Description type="Unit" ID="U001" />oops</Majesty>'
            )
        with self.assertRaisesRegex(DescriptionFormatError, "NUL bytes"):
            parse_descriptions("<Majesty />".encode("utf-16"))


class DescriptionMergeTests(unittest.TestCase):
    def test_stock_delta_merge_retains_order_and_appends_in_mod_order(self):
        stock_u1 = record("Unit", "U001", "stock")
        stock_u2 = record("Unit", "U002", "stock")
        stock = document(stock_u1, stock_u2)
        left = document(
            # Identical stock content is not a delta.
            stock_u1,
            record("Unit", "U002", "left-change"),
            record("Action", "A001", "left-add"),
        )
        right = document(record("Unit", "U003", "right-add"))

        result = merge_descriptions(stock, (("left", left), ("right", right)))

        self.assertEqual(
            [item.key for item in result.document.records],
            [
                ("Unit", "U001"),
                ("Unit", "U002"),
                ("Action", "A001"),
                ("Unit", "U003"),
            ],
        )
        self.assertEqual(
            [item.key for item in result.deltas[0].records],
            [("Unit", "U002"), ("Action", "A001")],
        )
        reparsed = parse_descriptions(result.payload)
        self.assertEqual(len(reparsed.records), 4)
        changed = reparsed.index[("Unit", "U002")].to_element()
        self.assertEqual(changed.find("./Game/Value").get("value"), "left-change")

    def test_accepts_identical_co_owned_change_despite_formatting(self):
        stock = document(record("Unit", "U001", "stock"))
        first = document(
            '<Description type="Unit" ID="U001" Name="same">'
            '<Game><Value value="changed"/></Game></Description>'
        )
        second = document(
            '<Description Name="same" ID="U001" type="Unit">\n'
            '  <Game>\n<Value value="changed" />\n</Game>\n</Description>'
        )

        result = merge_descriptions(
            stock, (("first", first), ("second", second))
        )

        selection = result.selections[0]
        self.assertEqual(selection.key, ("Unit", "U001"))
        self.assertEqual(selection.owners, ("first", "second"))

    def test_divergent_change_has_structured_conflict_and_resolution(self):
        stock = document(record("Unit", "U001", "stock"))
        variants = (
            ("left", document(record("Unit", "U001", "left"))),
            ("right", document(record("Unit", "U001", "right"))),
        )

        with self.assertRaises(DescriptionMergeConflict) as raised:
            merge_descriptions(stock, variants)
        conflict = raised.exception.conflicts[0]
        self.assertEqual(conflict.key, ("Unit", "U001"))
        self.assertEqual(conflict.owners, ("left", "right"))
        self.assertIsNotNone(conflict.stock)

        result = merge_descriptions(
            stock, variants, resolve=lambda conflict: "right"
        )
        chosen = result.document.index[("Unit", "U001")].to_element()
        self.assertEqual(chosen.find("./Game/Value").get("value"), "right")

        with self.assertRaisesRegex(
            DescriptionResolutionError, "unknown owner"
        ):
            merge_descriptions(
                stock, variants, resolve=lambda conflict: "missing"
            )

    def test_transform_is_precise_to_owner_and_selected_keys(self):
        stock = "<Majesty />"
        haunt = document(
            '<Description type="Unit" subType="Building" ID="PHG1">'
            '<Game><DialogID value="AP07" /></Game></Description>',
            '<Description type="Unit" subType="Character" ID="PHM1">'
            '<Game><DialogID value="AP07" /></Game></Description>',
        )
        alchemist = document(
            '<Description type="Unit" subType="Building" ID="ALB1">'
            '<Game><DialogID value="AP07" /></Game></Description>'
        )
        haunt_buildings = {("Unit", "PHG1")}

        def change_haunt_dialog(owner, key, element):
            if owner == "haunt" and key in haunt_buildings:
                dialog = element.find("./Game/DialogID")
                self.assertIsNotNone(dialog)
                self.assertEqual(dialog.get("value"), "AP07")
                dialog.set("value", "CGPH")
            return element

        result = merge_descriptions(
            stock,
            (("haunt", haunt), ("alchemist", alchemist)),
            transform=change_haunt_dialog,
        )
        values = {}
        for key, item in result.document.index.items():
            values[key] = item.to_element().find("./Game/DialogID").get("value")
        self.assertEqual(values[("Unit", "PHG1")], "CGPH")
        self.assertEqual(values[("Unit", "PHM1")], "AP07")
        self.assertEqual(values[("Unit", "ALB1")], "AP07")

    def test_compatible_root_attributes_are_preserved_and_conflicts_fail(self):
        stock = '<Majesty version="1" />'
        result = merge_descriptions(
            stock, (("mod", '<Majesty locale="en" version="1" />'),)
        )
        self.assertEqual(
            result.document.root_attributes,
            (("version", "1"), ("locale", "en")),
        )
        root = ET.fromstring(result.payload)
        self.assertEqual(root.attrib, {"version": "1", "locale": "en"})

        with self.assertRaisesRegex(DescriptionFormatError, "conflicts"):
            merge_descriptions(
                stock, (("mod", '<Majesty version="2" />'),)
            )


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import sys
import unittest
from unittest.mock import patch
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


class DescriptionFieldMergeTests(unittest.TestCase):
    base = ('<Description type="Action" subType="Standard" ID="TEST" Name="example">'
            '<Engine><ImageSet value="Cast"/><Script GPLFunction="effect"/></Engine>'
            '<Game><Flags value="IsSpell"/><Flags value="Visible"/>'
            '<Rate min="10" max="100"/><ValidationScript value="stock_check"/></Game>'
            '</Description>')

    def merged(self, *variants, **kwargs):
        return merge_descriptions(document(self.base),
            tuple((f"owner{i}", document(value)) for i, value in enumerate(variants)), **kwargs)

    def test_independent_sound_and_validation_edits_survive_in_both_orders(self):
        sound = self.base.replace('<Script ', '<Sound value="Example"/><SoundPhase begin="Begin"/><Script ')
        gate = self.base.replace('value="stock_check"', 'value="private_check"')
        for variants in ((sound, gate), (gate, sound)):
            result = self.merged(*variants)
            element = result.document.records[0].to_element()
            self.assertEqual([item.tag for item in element.find("Engine")],
                             ["ImageSet", "Sound", "SoundPhase", "Script"])
            self.assertEqual(element.find("./Engine/Sound").get("value"), "Example")
            self.assertEqual(element.find("./Game/ValidationScript").get("value"), "private_check")
            self.assertEqual(result.selections[0].owners, ("owner0", "owner1"))
            self.assertEqual([item.get("value") for item in element.findall("./Game/Flags")],
                             ["IsSpell", "Visible"])

    def test_many_owners_same_and_independent_attributes(self):
        first = self.base.replace('min="10"', 'min="20"')
        second = self.base.replace('max="100"', 'max="200"')
        third = self.base.replace('value="stock_check"', 'value="private_check"')
        result = self.merged(first, second, third, first, self.base)
        element = result.document.records[0].to_element()
        self.assertEqual(element.find("./Game/Rate").attrib, {"min": "20", "max": "200"})
        self.assertEqual(element.find("./Game/ValidationScript").get("value"), "private_check")
        self.assertEqual(result.selections[0].owners, ("owner0", "owner1", "owner2", "owner3"))

    def test_competing_attribute_reports_exact_field(self):
        with self.assertRaises(DescriptionMergeConflict) as raised:
            self.merged(self.base.replace('min="10"', 'min="20"'),
                        self.base.replace('min="10"', 'min="30"'))
        self.assertEqual(raised.exception.conflicts[0].fields, ("Description/Game/Rate/@min",))
        self.assertIn("Description/Game/Rate/@min", str(raised.exception))

    def test_repeated_groups_are_atomic_but_other_fields_can_merge(self):
        flags = self.base.replace('value="Visible"', 'value="Hidden"')
        gate = self.base.replace('value="stock_check"', 'value="private_check"')
        self.merged(flags, gate)
        with self.assertRaises(DescriptionMergeConflict):
            self.merged(flags, self.base.replace('value="IsSpell"', 'value="Other"'))
        # Even independently named Script entries cannot be paired by position.
        scripts = self.base.replace('<Script GPLFunction="effect"/>',
                                    '<Script type="0" GPLFunction="a"/><Script type="1" GPLFunction="b"/>')
        with patch.object(self, "base", scripts), self.assertRaises(DescriptionMergeConflict):
            self.merged(scripts.replace('GPLFunction="a"', 'GPLFunction="c"'),
                        scripts.replace('GPLFunction="b"', 'GPLFunction="d"'))

    def test_deletion_is_preserved_but_delete_versus_edit_conflicts(self):
        removed = self.base.replace('<Rate min="10" max="100"/>', '')
        gate = self.base.replace('value="stock_check"', 'value="private_check"')
        self.assertIsNone(self.merged(removed, gate).document.records[0].to_element().find("./Game/Rate"))
        with self.assertRaises(DescriptionMergeConflict):
            self.merged(removed, self.base.replace('min="10"', 'min="20"'))
        removed_attribute = self.base.replace(' min="10"', '')
        changed_attribute = self.base.replace('max="100"', 'max="200"')
        self.assertEqual(self.merged(removed_attribute, changed_attribute).document.records[0]
                         .to_element().find("./Game/Rate").attrib, {"max": "200"})

    def test_new_subtrees_need_identical_content_and_unambiguous_position(self):
        first = self.base.replace('</Game>', '<New a="1"/></Game>')
        second = self.base.replace('</Game>', '<New b="2"/></Game>')
        with self.assertRaises(DescriptionMergeConflict):
            self.merged(first, second)
        # Neither package defines an order between New and Other.
        ambiguous = self.base.replace('</Game>', '<Other value="2"/></Game>')
        with self.assertRaisesRegex(DescriptionMergeConflict, r"child-order\(\)"):
            self.merged(first, ambiguous)
        anchored = self.base.replace('<Rate ', '<Earlier value="2"/><Rate ')
        result = self.merged(first, anchored).document.records[0].to_element()
        self.assertEqual([node.tag for node in result.find("Game")],
                         ["Flags", "Flags", "Earlier", "Rate", "ValidationScript", "New"])

    def test_reordered_or_interleaved_children_are_not_guessed(self):
        reordered = self.base.replace('<Rate min="10" max="100"/><ValidationScript value="stock_check"/>',
                                     '<ValidationScript value="stock_check"/><Rate min="10" max="100"/>')
        with self.assertRaisesRegex(DescriptionMergeConflict, r"child-order\(\)"):
            self.merged(reordered, self.base.replace('min="10"', 'min="20"'))
        interleaved = self.base.replace('<Flags value="Visible"/>', '').replace(
            '<ValidationScript', '<Flags value="Visible"/><ValidationScript')
        with patch.object(self, "base", interleaved), self.assertRaisesRegex(DescriptionMergeConflict, r"children\(\)"):
            self.merged(interleaved.replace('min="10"', 'min="20"'),
                        interleaved.replace('value="Visible"', 'value="Hidden"'))

    def test_text_changes_preserve_content_and_conflict_on_same_text(self):
        base = self.base.replace('<Rate min="10" max="100"/>', '<Rate>stock text</Rate>')
        with patch.object(self, "base", base):
            result = self.merged(base.replace('stock text', 'new text'),
                                 base.replace('value="stock_check"', 'value="private_check"'))
            self.assertEqual(result.document.records[0].to_element().find("./Game/Rate").text, "new text")
            with self.assertRaises(DescriptionMergeConflict):
                self.merged(base.replace('stock text', 'first'), base.replace('stock text', 'second'))

    def test_external_baseline_does_not_emit_unselected_stock_records(self):
        stock = parse_descriptions(document(self.base, record("Unit", "OTHER", "stock")))
        first = self.base.replace('min="10"', 'min="20"')
        second = self.base.replace('max="100"', 'max="200"')
        result = merge_descriptions("<Majesty/>", (("a", document(first)), ("b", document(second))),
                                    field_merge_stock=stock.index)
        self.assertEqual([item.key for item in result.document.records], [("Action", "TEST")])
        with self.assertRaises(DescriptionMergeConflict):
            merge_descriptions("<Majesty/>", (("a", document(first)), ("b", document(second))))

    def test_explicit_resolution_still_takes_precedence(self):
        first = self.base.replace('min="10"', 'min="20"')
        second = self.base.replace('max="100"', 'max="200"')
        result = self.merged(first, second, resolve=lambda conflict: "owner0")
        self.assertEqual(result.document.records[0].to_element().find("./Game/Rate").get("max"), "100")

    def test_single_or_identical_records_do_not_enter_field_reconciliation(self):
        changed = self.base.replace('min="10"', 'min="20"')
        with patch("majesty_cam.descriptions._merge_stock_fields", side_effect=AssertionError("unexpected field merge")):
            self.merged(changed)
            self.merged(changed, changed)


if __name__ == "__main__":
    unittest.main()

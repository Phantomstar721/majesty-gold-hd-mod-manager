from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.strings import (
    StringsFormatError,
    load_effective_stock_strings,
    merge_strings,
    parse_strings,
)


class StringsTests(unittest.TestCase):
    def test_stock_strings_follow_installed_dataset_manifest_order(self):
        with TemporaryDirectory() as tmp:
            game = Path(tmp)
            data = game / "Data"
            datamx = game / "DataMX"
            data.mkdir()
            datamx.mkdir()
            (data / "base.xml").write_text(
                '<Majesty><Language id="en_US">'
                '<Text id="SAME">Base</Text><Text id="BASE">Only base</Text>'
                '</Language></Majesty>',
                encoding="utf-8",
            )
            (datamx / "expansion.xml").write_text(
                '<Majesty><Language id="en_US">'
                '<Text id="SAME">Expansion</Text><Text id="MX">Only MX</Text>'
                '</Language></Majesty>',
                encoding="utf-8",
            )
            (data / "MajestyDatasetDefinitions.xml").write_text(
                "<Majesty><DataConfiguration><Dataset><Load>"
                "<Strings>base.xml</Strings>"
                "</Load></Dataset></DataConfiguration></Majesty>",
                encoding="utf-8",
            )
            (datamx / "MajestyExpansionDatasetDefinitions.xml").write_text(
                "<Majesty><DataConfiguration><Dataset><Load>"
                "<Strings>expansion.xml</Strings>"
                "</Load></Dataset></DataConfiguration></Majesty>",
                encoding="utf-8",
            )

            document, inputs = load_effective_stock_strings(game)

            self.assertIn(b"Expansion", document.index[("en_US", "SAME")].payload)
            self.assertEqual(
                tuple(record.key for record in document.records),
                (("en_US", "SAME"), ("en_US", "BASE"), ("en_US", "MX")),
            )
            self.assertEqual(len(inputs), 4)

    def test_qdd_is_not_misclassified_as_a_strings_dictionary(self):
        qdd = (
            b"Name =\r\n[QUEST]\r\n\r\nShort Description =\r\n[Short]\r\n\r\n"
            b"Long Description =\r\n[Long]\r\n"
        )

        with self.assertRaises(StringsFormatError):
            parse_strings(qdd, source="quests.qdd")

    def test_duplicate_text_id_uses_the_final_stock_loader_value(self):
        document = parse_strings(
            b'<Majesty><Language id="en_US">'
            b'<Text id="HELLO">First</Text><Text id="HELLO">Second</Text>'
            b"</Language></Majesty>"
        )

        self.assertEqual(len(document.records), 1)
        self.assertIn(b"Second", document.records[0].payload)

    def test_different_text_ids_are_unioned_into_one_overlay(self):
        first = parse_strings(
            b'<Majesty><Language id="en_US"><Text id="FIRST">One</Text>'
            b"</Language></Majesty>"
        )
        second = parse_strings(
            b'<Majesty><Language id="en_US"><Text id="SECOND">Two</Text>'
            b"</Language></Majesty>"
        )

        merged = merge_strings((("first", first), ("second", second)))

        self.assertIn(b' id="FIRST"', merged.payload)
        self.assertIn(b' id="SECOND"', merged.payload)

    def test_same_text_id_requires_an_explicit_choice(self):
        first = parse_strings(
            b'<Majesty><Language id="en_US"><Text id="HELLO">First</Text>'
            b"</Language></Majesty>"
        )
        second = parse_strings(
            b'<Majesty><Language id="en_US"><Text id="HELLO">Second</Text>'
            b"</Language></Majesty>"
        )

        unresolved = merge_strings((("first", first), ("second", second)))
        self.assertEqual(len(unresolved.conflicts), 1)
        key = unresolved.conflicts[0].key
        resolved = merge_strings(
            (("first", first), ("second", second)),
            resolutions={key: second.records[0]},
        )
        self.assertIn(b"Second", resolved.payload)


if __name__ == "__main__":
    unittest.main()

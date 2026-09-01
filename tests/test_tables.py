from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.tables import (
    TableAncestryError,
    TableFormatError,
    TableMergeConflict,
    merge_bdep,
    merge_bdep_stock_relative,
    parse_bdep,
)


class BdepTests(unittest.TestCase):
    def test_parse_ignores_comments_and_preserves_expressions(self):
        rows = parse_bdep(b"# stock\r\nABC1\r\nABJ2 : AAA BBB ||\r\n\r\n")
        self.assertEqual(rows[0].building_id, "ABC1")
        self.assertIsNone(rows[0].expression)
        self.assertEqual(rows[1].building_id, "ABJ2")
        self.assertEqual(rows[1].expression, b"AAA BBB ||")

    def test_merge_appends_disjoint_rows_once(self):
        stock = b"# stock\r\nABJ2 : ROOT\r\n"
        haunt = stock + b"\r\n# haunt\r\nPHG1 : PALACE2\r\n"
        alchemist = stock + b"\r\n# alchemist\r\nALB1 : PALACE2\r\n"

        result = merge_bdep(stock, (("haunt", haunt), ("alchemist", alchemist)))

        self.assertEqual(result.payload.count(b"ABJ2 : ROOT"), 1)
        self.assertEqual(result.payload.count(b"PHG1 : PALACE2"), 1)
        self.assertEqual(result.payload.count(b"ALB1 : PALACE2"), 1)
        self.assertEqual([d.owner for d in result.deltas], ["haunt", "alchemist"])

    def test_merge_accepts_identical_premerged_row(self):
        stock = b"ABJ2 : ROOT\r\n"
        first = stock + b"PHG1 : PALACE2\r\n"
        second = stock + b"PHG1 : PALACE2\r\nALB1 : PALACE2\r\n"
        result = merge_bdep(stock, (("haunt", first), ("alchemist", second)))
        self.assertEqual(result.payload.count(b"PHG1 : PALACE2"), 1)

    def test_merge_rejects_different_rule_for_one_building(self):
        stock = b"ABJ2 : ROOT\r\n"
        with self.assertRaisesRegex(TableMergeConflict, "left, right"):
            merge_bdep(
                stock,
                (
                    ("left", stock + b"PHG1 : PALACE2\r\n"),
                    ("right", stock + b"PHG1 : PALACE3\r\n"),
                ),
            )

    def test_parse_rejects_lf_line_endings(self):
        with self.assertRaisesRegex(TableFormatError, "CRLF"):
            parse_bdep(b"ABJ2 : ROOT\n")

    def test_stock_relative_merge_recovers_original_based_additions_only(self):
        original = b"PAL1\r\nMARKET : PAL1\r\n"
        expansion = b"PAL1\r\nMARKET : PAL1 OUTPOST ||\r\nOUTPOST : PAL1\r\n"
        zoo = original + b"ZOO1\r\nZOO2\r\nZOO3\r\n"

        result = merge_bdep_stock_relative(
            expansion,
            (("Original", original), ("Expansion", expansion)),
            (("zoo", zoo),),
        )

        self.assertIn(b"MARKET : PAL1 OUTPOST ||\r\n", result.payload)
        self.assertIn(b"OUTPOST : PAL1\r\n", result.payload)
        self.assertEqual(
            tuple(row.building_id for row in result.deltas[0].rows),
            ("ZOO1", "ZOO2", "ZOO3"),
        )

    def test_stock_relative_merge_preserves_unambiguous_replacement(self):
        original = b"PAL1\r\nMARKET : PAL1\r\n"
        expansion = b"PAL1\r\nMARKET : PAL1 OUTPOST ||\r\nOUTPOST : PAL1\r\n"
        package = b"PAL1\r\nMARKET : CUSTOM\r\nOUTPOST : PAL1\r\n"

        result = merge_bdep_stock_relative(
            expansion,
            (("Original", original), ("Expansion", expansion)),
            (("custom", package),),
        )

        self.assertIn(b"MARKET : CUSTOM\r\n", result.payload)
        self.assertEqual(
            tuple(row.building_id for row in result.deltas[0].rows),
            ("MARKET",),
        )

    def test_stock_relative_merge_preserves_reversion_on_complete_newer_topology(self):
        original = b"PAL1\r\nMARKET : PAL1\r\n"
        expansion = b"PAL1\r\nMARKET : PAL1 OUTPOST ||\r\nOUTPOST : PAL1\r\n"
        package = b"PAL1\r\nMARKET : PAL1\r\nOUTPOST : PAL1\r\n"

        result = merge_bdep_stock_relative(
            expansion,
            (("Original", original), ("Expansion", expansion)),
            (("reversion", package),),
        )

        self.assertIn(b"MARKET : PAL1\r\n", result.payload)
        self.assertEqual(
            tuple(row.building_id for row in result.deltas[0].rows),
            ("MARKET",),
        )

    def test_stock_relative_merge_rejects_same_topology_ancestry_ambiguity(self):
        original = b"PAL1\r\nMARKET : PAL1\r\n"
        expansion = b"PAL1\r\nMARKET : PAL1 OUTPOST ||\r\n"

        with self.assertRaisesRegex(
            TableAncestryError,
            r"ambiguous between Original, Expansion.*MARKET",
        ):
            merge_bdep_stock_relative(
                expansion,
                (("Original", original), ("Expansion", expansion)),
                (("ambiguous", original),),
            )

    def test_stock_relative_merge_rejects_truncated_table(self):
        original = b"PAL1\r\nMARKET : PAL1\r\n"
        expansion = original + b"OUTPOST : PAL1\r\n"

        with self.assertRaisesRegex(TableAncestryError, "not a complete table"):
            merge_bdep_stock_relative(
                expansion,
                (("Original", original), ("Expansion", expansion)),
                (("fragment", b"ZOO1\r\n"),),
            )

    def test_stock_relative_merge_rejects_complete_newer_rows_out_of_order(self):
        original = b"PAL1\r\nMARKET : PAL1\r\n"
        expansion = original + b"OUTPOST : PAL1\r\n"
        misordered = b"PAL1\r\nOUTPOST : PAL1\r\nMARKET : PAL1\r\n"

        with self.assertRaisesRegex(TableAncestryError, "stock ordering"):
            merge_bdep_stock_relative(
                expansion,
                (("Original", original), ("Expansion", expansion)),
                (("misordered", misordered),),
            )


if __name__ == "__main__":
    unittest.main()

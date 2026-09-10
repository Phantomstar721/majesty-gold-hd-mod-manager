from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.strt import (
    StrtAncestryError,
    StrtFormatError,
    StrtMergeConflict,
    StrtRecord,
    StrtRowResolution,
    StrtTable,
    merge_strt,
    merge_strt_stock_relative,
    parse_strt,
    strt_delta,
)


class StrtTests(unittest.TestCase):
    def test_round_trip_preserves_version_ids_and_bytes(self):
        table = StrtTable(
            version=b"\x03\x00",
            records=(
                StrtRecord(7, b"alpha"),
                StrtRecord(0x41424344, "caf\xe9".encode("cp1252")),
            ),
        )

        self.assertEqual(parse_strt(table.to_bytes()), table)

    def test_id_merge_unions_disjoint_stock_deltas(self):
        base = _table((1, b"stock one"), (2, b"stock two"))
        left = _table((1, b"left one"), (2, b"stock two"), (3, b"left three"))
        right = _table((1, b"stock one"), (2, b"right two"), (4, b"right four"))

        merged, deltas = merge_strt(
            base, (("left", left), ("right", right)), key_mode="id"
        )

        self.assertEqual(
            merged.records,
            (
                StrtRecord(1, b"left one"),
                StrtRecord(2, b"right two"),
                StrtRecord(3, b"left three"),
                StrtRecord(4, b"right four"),
            ),
        )
        self.assertEqual([delta.owner for delta in deltas], ["left", "right"])

    def test_index_merge_accepts_identical_premerged_compatibility_rows(self):
        base = _table((0, b"stock"))
        left = _table((0, b"stock"), (1, b"shared"), (2, b"left"))
        right = _table((0, b"stock"), (1, b"shared"), (2, b""), (3, b"right"))

        merged, _ = merge_strt(
            base, (("left", left), ("right", right)), key_mode="index"
        )

        self.assertEqual(
            merged.records,
            (
                StrtRecord(0, b"stock"),
                StrtRecord(1, b"shared"),
                StrtRecord(2, b"left"),
                StrtRecord(3, b"right"),
            ),
        )

    def test_id_delta_rejects_provider_that_omits_stock_semantic_row(self):
        base = _table((1, b"stock one"), (2, b"stock two"))
        incomplete = _table((1, b"changed one"), (3, b"added three"))

        with self.assertRaisesRegex(
            StrtFormatError,
            r"provider STRT table omits stock semantic ID\(s\): 0x00000002",
        ):
            strt_delta(base, incomplete, owner="provider", key_mode="id")

    def test_index_merge_rejects_provider_that_truncates_stock_tail(self):
        base = _table((0, b"stock zero"), (1, b"stock one"), (2, b"stock two"))
        incomplete = _table((0, b"changed zero"), (1, b"stock one"))

        with self.assertRaisesRegex(
            StrtFormatError,
            r"provider STRT table is truncated \(2 rows; stock has 3\)",
        ):
            merge_strt(base, (("provider", incomplete),), key_mode="index")

    def test_merge_rejects_different_changes_to_one_key(self):
        base = _table((1, b"stock"))
        with self.assertRaisesRegex(StrtMergeConflict, "left, right"):
            merge_strt(
                base,
                (("left", _table((1, b"L"))), ("right", _table((1, b"R")))),
                key_mode="id",
            )

    def test_index_stock_relative_merge_preserves_effective_tail(self):
        original = _table((0, b"stock zero"), (1, b"original one"))
        effective = _table(
            (0, b"stock zero"),
            (1, b"mx one"),
            (2, b"mx-only two"),
        )
        original_shaped = _table((0, b"custom zero"), (1, b"original one"))

        merged, deltas = merge_strt_stock_relative(
            effective,
            (("Original", original), ("Northern Expansion", effective)),
            (("legacy", original_shaped),),
            key_mode="index",
        )

        self.assertEqual(
            merged.records,
            (
                StrtRecord(0, b"custom zero"),
                StrtRecord(1, b"mx one"),
                StrtRecord(2, b"mx-only two"),
            ),
        )
        self.assertEqual(deltas[0].changes, ((0, StrtRecord(0, b"custom zero")),))

    def test_id_stock_relative_merge_preserves_effective_rows(self):
        original = _table((10, b"stock ten"), (20, b"original twenty"))
        effective = _table(
            (10, b"stock ten"),
            (20, b"mx twenty"),
            (30, b"mx-only thirty"),
        )
        original_shaped = _table(
            (10, b"custom ten"),
            (20, b"original twenty"),
        )

        merged, deltas = merge_strt_stock_relative(
            effective,
            (("Original", original), ("Northern Expansion", effective)),
            (("legacy", original_shaped),),
            key_mode="id",
        )

        self.assertEqual(
            merged.records,
            (
                StrtRecord(10, b"custom ten"),
                StrtRecord(20, b"mx twenty"),
                StrtRecord(30, b"mx-only thirty"),
            ),
        )
        self.assertEqual(deltas[0].changes, ((10, StrtRecord(10, b"custom ten")),))

    def test_index_complete_mx_topology_preserves_intentional_reversion(self):
        original = _table((0, b"stock zero"), (1, b"original one"))
        effective = _table(
            (0, b"stock zero"),
            (1, b"mx one"),
            (2, b"mx-only two"),
        )
        reversion = _table(
            (0, b"stock zero"),
            (1, b"original one"),
            (2, b"mx-only two"),
        )

        merged, deltas = merge_strt_stock_relative(
            effective,
            (("Original", original), ("Northern Expansion", effective)),
            (("reversion", reversion),),
            key_mode="index",
        )

        self.assertEqual(merged.records[1].text, b"original one")
        self.assertEqual(
            deltas[0].changes,
            ((1, StrtRecord(1, b"original one")),),
        )

    def test_id_complete_mx_topology_preserves_intentional_reversion(self):
        original = _table((10, b"stock ten"), (20, b"original twenty"))
        effective = _table(
            (10, b"stock ten"),
            (20, b"mx twenty"),
            (30, b"mx-only thirty"),
        )
        reversion = _table(
            (10, b"stock ten"),
            (20, b"original twenty"),
            (30, b"mx-only thirty"),
        )

        merged, deltas = merge_strt_stock_relative(
            effective,
            (("Original", original), ("Northern Expansion", effective)),
            (("reversion", reversion),),
            key_mode="id",
        )

        self.assertEqual(merged.records[1].text, b"original twenty")
        self.assertEqual(
            deltas[0].changes,
            ((20, StrtRecord(20, b"original twenty")),),
        )

    def test_stock_relative_merge_honors_row_conflict_resolution(self):
        original = _table((0, b"stock"))
        effective = _table((0, b"mx"), (1, b"mx-only"))
        resolution = StrtRowResolution(
            StrtRecord(0, b"chosen"),
            frozenset(("left", "right")),
        )

        merged, deltas = merge_strt_stock_relative(
            effective,
            (("Original", original), ("Northern Expansion", effective)),
            (
                ("left", _table((0, b"left"))),
                ("right", _table((0, b"right"))),
            ),
            key_mode="index",
            resolutions={0: resolution},
        )

        self.assertEqual(
            merged.records,
            (StrtRecord(0, b"chosen"), StrtRecord(1, b"mx-only")),
        )
        self.assertEqual(tuple(delta.owner for delta in deltas), ("left", "right"))

    def test_stock_relative_merge_rejects_incomparable_ancestry(self):
        branch_a = _table((1, b"one-a"), (2, b"two-a"))
        branch_b = _table((1, b"one-b"), (3, b"three-b"))
        effective = _table(
            (1, b"one-effective"),
            (2, b"two-effective"),
            (3, b"three-effective"),
        )
        ambiguous = _table(
            (1, b"one-custom"),
            (2, b"two-a"),
            (3, b"three-b"),
        )

        with self.assertRaisesRegex(
            StrtAncestryError,
            r"ambiguous between Branch A, Branch B.*0x00000002",
        ):
            merge_strt_stock_relative(
                effective,
                (("Branch A", branch_a), ("Branch B", branch_b)),
                (("ambiguous", ambiguous),),
                key_mode="id",
            )

    def test_parser_rejects_offset_into_header(self):
        payload = b"\x01\x00\x03\x00\x04\x00\x00\x00"
        with self.assertRaisesRegex(StrtFormatError, "out-of-bounds offset"):
            parse_strt(payload)


def _table(*items: tuple[int, bytes]) -> StrtTable:
    return StrtTable(
        version=b"\x03\x00",
        records=tuple(StrtRecord(string_id, text) for string_id, text in items),
    )


if __name__ == "__main__":
    unittest.main()

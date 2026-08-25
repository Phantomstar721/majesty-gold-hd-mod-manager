from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.strt import (
    StrtFormatError,
    StrtMergeConflict,
    StrtRecord,
    StrtTable,
    merge_strt,
    parse_strt,
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

    def test_merge_rejects_different_changes_to_one_key(self):
        base = _table((1, b"stock"))
        with self.assertRaisesRegex(StrtMergeConflict, "left, right"):
            merge_strt(
                base,
                (("left", _table((1, b"L"))), ("right", _table((1, b"R")))),
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

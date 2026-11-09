from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET

from test_stock_art import _archive, _image, _tile, _section, _entry_for
from majesty_cam.art import parse_stock_imag_tile_references, parse_tile_palette_reference
from majesty_cam.compose import (
    _complete_description_art, _description_imag_ids, _required_stock_art_domain,
    merge_art_resource_domains,
)
from majesty_cam.stock_art import StockArtLineage, _art_overlay


class DescriptionArtDependenciesTests(unittest.TestCase):
    def fixture(self):
        base = _archive((_image(b"BASE", 1001, 0),), (_tile(0, marker=7),), palette=b"SPLT")
        expansion = _archive((_image(b"EXPN", 1002, 0),), (_tile(1, marker=99),), palette=b"SPLT")
        lineage = StockArtLineage("main", (Path("game/Data/base.cam"), Path("game/DataMX/mx.cam")),
                                  (base, expansion), _art_overlay(base, (expansion,)))
        return lineage

    def test_hidden_overlay_reference_is_included_once(self):
        node = ET.fromstring('<Description><Engine><Info>NotVisibleInISOView</Info>'
                             '<ImageIDBase>EXPN</ImageIDBase></Engine></Description>')
        record = SimpleNamespace(to_element=lambda: node)
        descriptions = SimpleNamespace(document=SimpleNamespace(records=(record, record)))
        self.assertEqual(_description_imag_ids(descriptions), (b"EXPN",))

    def test_missing_expansion_reference_copies_tiles_and_palette(self):
        lineage = self.fixture()
        results = _complete_description_art(Path("game"), (), (lineage,), (b"BASE", b"EXPN", b"EXPN"))
        self.assertEqual(len(results), 1)
        archive = results[0].archive
        self.assertEqual([e.name[:4] for e in _section(archive, b"IMAG").entries], [b"EXPN"])
        tiles = _section(archive, b"TILE").entries
        image = _entry_for(archive, b"IMAG", b"EXPN")
        ref = parse_stock_imag_tile_references(image.data, tile_count=len(tiles)).references[0]
        tile = tiles[ref.tile_index].data
        self.assertEqual(tile[26], 99)
        palette = parse_tile_palette_reference(tile, tile_index=ref.tile_index)
        self.assertEqual(_section(archive, b"SPLT").entries[palette.palette_index].data, b"\x02")

    def test_custom_image_is_not_replaced_and_completion_is_idempotent(self):
        lineage = self.fixture()
        result = _required_stock_art_domain("main", lineage.effective, (b"EXPN",))
        # A selected provider owns this image, regardless of matching stock ID.
        image = _entry_for(result.archive, b"IMAG", b"EXPN")
        custom = replace(image, data=b"authored custom image")
        result = replace(result, archive=replace(result.archive, sections=tuple(
            replace(s, entries=(custom,)) if s.extension == b"IMAG" else s
            for s in result.archive.sections)))
        self.assertEqual(_complete_description_art(Path("game"), (result,), (lineage,), (b"EXPN",)), (result,))
        first = _complete_description_art(Path("game"), (), (lineage,), (b"EXPN",))
        self.assertEqual(_complete_description_art(Path("game"), first, (lineage,), (b"EXPN",)), first)

    def test_existing_domain_keeps_other_art(self):
        lineage = self.fixture()
        result = _required_stock_art_domain("main", lineage.effective, (b"BASE",))
        before = _entry_for(result.archive, b"IMAG", b"BASE")
        output = _complete_description_art(Path("game"), (result,), (lineage,), (b"EXPN",))
        self.assertEqual(len(output), 1)
        self.assertEqual(_entry_for(output[0].archive, b"IMAG", b"BASE"), before)
        self.assertEqual(len(_section(output[0].archive, b"IMAG").entries), 2)

    def test_expansion_only_lineage_is_not_mistaken_for_base(self):
        lineage = self.fixture()
        lineage = replace(lineage, source_paths=lineage.source_paths[1:], ancestors=lineage.ancestors[1:],
                          effective=lineage.ancestors[1])
        self.assertEqual(len(_complete_description_art(Path("game"), (), (lineage,), (b"EXPN",))), 1)

    def test_installed_expansion_overlay_dependency(self):
        game = Path("C:/Program Files (x86)/Steam/steamapps/common/Majesty HD")
        if not (game / "DataMX/mx_maindata.cam").is_file():
            self.skipTest("installed art unavailable")
        # Read-only helper verification, never Prepare or write a player profile.
        results = merge_art_resource_domains(game, (), description_imag_ids=(b"XR01",))
        image = _entry_for(results[0].archive, b"IMAG", b"XR01")
        tiles = _section(results[0].archive, b"TILE").entries
        refs = parse_stock_imag_tile_references(image.data, tile_count=len(tiles)).references
        self.assertTrue(refs)
        self.assertTrue(all(tiles[ref.tile_index].data for ref in refs))


if __name__ == "__main__":
    unittest.main()

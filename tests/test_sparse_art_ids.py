"""Numeric TOC identity at the real art import/composition boundary."""
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from majesty_cam.cam import CamArchive, CamEntry, CamSection, read_cam, write_cam
from majesty_cam.art import parse_stock_imag_tile_references, parse_tile_palette_reference
from majesty_cam.stock_art import (
    StockArtError, normalize_art_slots, collapse_art_archives, StockArtLineage,
)
from majesty_cam.compose import _compose_art_domain
from test_stock_art import _archive, _image, _tile, _section


def keyed(tag, rows, flags=0):
    return CamSection(tag, tuple(
        CamEntry(struct.pack('<I', key) + b'fixture'.ljust(16, b'\0'), data)
        for key, data in rows
    ), padding=struct.pack('<I', flags))


def sparse(key=20000, marker=23, image=b'NEW1'):
    return CamArchive((
        CamSection(b'IMAG', (_image(image, 300, key),)),
        keyed(b'TILE', ((key, _tile(key, marker=marker)),)),
        keyed(b'SPLT', ((key, bytes((marker,))),)),
    ))


class SparseArtIdTests(unittest.TestCase):
    def test_sparse_and_out_of_order_ids_not_positions(self):
        archive = CamArchive((keyed(b'TILE', ((20001, b'b'), (20000, b'a'))),))
        output = normalize_art_slots(archive).sections[0]
        self.assertEqual(len(output.entries), 20002)
        self.assertEqual(output.entries[20000].data, b'a')
        self.assertEqual(output.entries[20001].data, b'b')
        self.assertFalse(any(e.data for e in output.entries[:20000]))
        self.assertEqual(output.entries[10].name, b'\0' * 20)
        self.assertEqual(output.padding, struct.pack('<I', 1))
        self.assertEqual(normalize_art_slots(normalize_art_slots(archive)), normalize_art_slots(archive))
        self.assertEqual(read_cam(archive.to_bytes()), read_cam(read_cam(archive.to_bytes()).to_bytes()))

    def test_ordinal_flag_keeps_positions_even_if_ids_differ(self):
        section = keyed(b'TILE', ((20000, b'a'), (3, b'b')), flags=5)
        self.assertIs(normalize_art_slots(CamArchive((section,))).sections[0], section)

    def test_duplicate_id_uses_last_entry_including_empty(self):
        for final in (b'last', b''):
            section = keyed(b'SPLT', ((7, b'first'), (7, final)), flags=4)
            output = normalize_art_slots(CamArchive((section,))).sections[0]
            self.assertEqual(output.entries[7].data, final)
            self.assertEqual(output.padding, struct.pack('<I', 5))

    def test_named_palettes_and_images_are_not_numeric_tables(self):
        for tag in (b'PALT', b'IMAG'):
            section = CamSection(tag, (CamEntry(b'PLYR'.ljust(20, b'\0'), b'payload'),))
            self.assertIs(normalize_art_slots(CamArchive((section,))).sections[0], section)

    def test_invalid_ids_do_not_allocate_unbounded_tables(self):
        for tag, key in ((b'TILE', 65535), (b'TILE', 0xffffffff)):
            with self.subTest(tag=tag, key=key), self.assertRaisesRegex(StockArtError, 'TOC ID'):
                normalize_art_slots(CamArchive((keyed(tag, ((key, b'data'),)),)))

    def test_full_dword_palette_key_is_compacted_and_reference_rewritten(self):
        # Printable FourCCs are DWORD resource identities, not enormous arrays.
        key = int.from_bytes(b'PALX', 'little')
        archive = CamArchive((
            keyed(b'TILE', ((0, _tile(key, marker=23)),), flags=1),
            keyed(b'SPLT', ((0, b'stock'), (key, b'private'))),
        ))
        result = normalize_art_slots(archive, palette_floor=854)
        palettes = _section(result, b'SPLT').entries
        self.assertEqual(len(palettes), 855)
        self.assertEqual(palettes[854].data, b'private')
        self.assertEqual(parse_tile_palette_reference(_section(result,b'TILE').entries[0].data,
                                                     tile_index=0).palette_index, 854)

    def test_unreferenced_named_palette_does_not_become_ordinal_alias(self):
        key = int.from_bytes(b'PALX', 'little')
        archive = CamArchive((keyed(b'SPLT', ((0, b'stock'), (key, b'unused'))),))
        result = normalize_art_slots(archive, palette_floor=3)
        self.assertFalse(_section(result,b'SPLT').entries[1].data)
        self.assertEqual(_section(result,b'SPLT').entries[3].data,b'unused')

    def test_full_palette_keys_across_component_cams_remain_distinct(self):
        stock = _archive((_image(b'BASE', 300, 0),), (_tile(0, marker=7),), palette=b'SPLT')
        lineage = StockArtLineage('main', (Path('stock.cam'),), (stock,), stock)
        with TemporaryDirectory() as tmp:
            paths = []
            for index, key in enumerate((int.from_bytes(b'PALX','little'), int.from_bytes(b'PALY','little'))):
                path = Path(tmp) / f'art{index}.cam'
                archive = CamArchive((
                    CamSection(b'IMAG', (_image(b'NEW' + bytes((49+index,)), 300, 20000+index),)),
                    keyed(b'TILE', ((20000+index, _tile(key, marker=23+index)),)),
                    keyed(b'SPLT', ((key, bytes((23+index,))),)),
                ))
                write_cam(archive,path)
                paths.append(path)
            item, = collapse_art_archives(Path(tmp), paths, owner='multi', lineages=(lineage,))
            self.assertEqual(item.analysis.palette_delta.changed_indices, (2,3))
            inv=SimpleNamespace(selected=SimpleNamespace(alias='multi'))
            output=_compose_art_domain('main','main',stock,((inv,paths[-1],item.archive),),
                                       (item.analysis,),fallthrough_ancestors=(stock,))
            for index in range(2):
                tile=_section(output.archive,b'TILE').entries[20000+index]
                ref=parse_tile_palette_reference(tile.data,tile_index=20000+index)
                self.assertEqual(_section(output.archive,b'SPLT').entries[ref.palette_index].data,
                                 bytes((23+index,)))

    def test_dense_id_keyed_table_preserves_slots(self):
        section = keyed(b'TILE', ((0, b'a'), (1, b'b')))
        self.assertEqual(normalize_art_slots(CamArchive((section,))).sections[0].entries, section.entries)

    def test_compact_eighteen_record_table_preserves_high_ids(self):
        section = keyed(b'TILE', ((20000 + i, bytes((i,))) for i in range(18)))
        result = normalize_art_slots(CamArchive((section,))).sections[0]
        self.assertEqual(len(result.entries), 20018)
        self.assertEqual([e.data for e in result.entries[20000:]], [bytes((i,)) for i in range(18)])

    def test_missing_sparse_tile_or_palette_is_still_an_error(self):
        stock = _archive((_image(b'BASE', 300, 0),), (_tile(0, marker=7),), palette=b'SPLT')
        lineage = StockArtLineage('main', (Path('stock.cam'),), (stock,), stock)
        for missing in (b'TILE', b'SPLT'):
            archive = sparse()
            archive = CamArchive(tuple(
                keyed(s.extension, ((20001, s.entries[0].data),)) if s.extension == missing else s
                for s in archive.sections
            ))
            with self.subTest(missing=missing), TemporaryDirectory() as tmp:
                path = Path(tmp) / 'missing.cam'
                write_cam(archive, path)
                with self.assertRaises((StockArtError, ValueError)):
                    item, = collapse_art_archives(Path(tmp), (path,), owner='missing', lineages=(lineage,))
                    inventory = SimpleNamespace(selected=SimpleNamespace(alias='missing'))
                    _compose_art_domain('main', 'main', stock,
                        ((inventory, path, item.archive),), (item.analysis,),
                        fallthrough_ancestors=(stock,))

    def test_import_compose_and_relocate_tiles_and_palettes_together(self):
        stock = _archive((_image(b'BASE', 300, 0),), (_tile(0, marker=7),), palette=b'SPLT')
        lineage = StockArtLineage('main', (Path('stock.cam'),), (stock,), stock)
        with TemporaryDirectory() as tmp:
            providers, analyses = [], []
            for owner, marker, image in (('first', 23, b'NEW1'), ('second', 47, b'NEW2')):
                path = Path(tmp) / (owner + '.cam')
                write_cam(sparse(marker=marker, image=image), path)
                item, = collapse_art_archives(Path(tmp), (path,), owner=owner, lineages=(lineage,))
                self.assertEqual(item.analysis.tile_delta.changed_indices, (20000,))
                self.assertEqual(item.analysis.palette_delta.changed_indices, (20000,))
                self.assertEqual(item.analysis.tile_delta.changes[0].kind, 'append')
                providers.append((SimpleNamespace(selected=SimpleNamespace(alias=owner)), path, item.archive))
                analyses.append(item.analysis)
            result = _compose_art_domain('main', 'main', stock, providers, analyses, fallthrough_ancestors=(stock,))
            tiles = _section(result.archive, b'TILE').entries
            palettes = _section(result.archive, b'SPLT').entries
            indices = []
            for image in _section(result.archive, b'IMAG').entries:
                if image.name[:4] not in (b'NEW1', b'NEW2'):
                    continue
                marker = 23 if image.name[:4] == b'NEW1' else 47
                ref, = parse_stock_imag_tile_references(image.data, tile_count=len(tiles)).references
                indices.append(ref.tile_index)
                tile = tiles[ref.tile_index]
                self.assertEqual(tile.data[26], marker)
                palette = parse_tile_palette_reference(tile.data, tile_index=ref.tile_index)
                self.assertEqual(palettes[palette.palette_index].data, bytes((marker,)))
                self.assertEqual(int.from_bytes(tile.name[:4], 'little'), ref.tile_index)
            self.assertEqual(len(set(indices)), 2)
            self.assertIn(20000, indices)
            self.assertFalse(tiles[0].data)  # private IDs never replace stock tile 0


if __name__ == '__main__':
    unittest.main()

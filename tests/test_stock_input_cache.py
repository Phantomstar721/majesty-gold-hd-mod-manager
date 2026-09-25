from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from majesty_cam.stock_input_cache import StockInputCache
from majesty_cam.dataset_dependencies import load_dataset_symbols, _DATASET_CACHE
from test_stock_gpl import _stock_game


class StockInputCacheTests(unittest.TestCase):
    def test_warm_hit_skips_enumeration_and_loader_but_file_edit_invalidates(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / 'source'
            source.write_bytes(b'first')
            paths = Mock(return_value=(source,))
            loader = Mock(side_effect=source.read_bytes)
            cache = StockInputCache()
            self.assertEqual(cache.get(root, 'key', paths, loader), b'first')
            paths.reset_mock()
            self.assertEqual(cache.get(root, 'key', paths, loader), b'first')
            paths.assert_not_called()
            self.assertEqual(loader.call_count, 1)
            source.write_bytes(b'changed')
            self.assertEqual(cache.get(root, 'key', paths, loader), b'changed')
            self.assertEqual(loader.call_count, 2)

    def test_directory_addition_and_optional_file_presence_invalidate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            directory = root / 'xml'
            directory.mkdir()
            optional = root / 'optional'
            paths = lambda: (directory, optional, *sorted(directory.iterdir()))
            loader = Mock(side_effect=lambda: (len(list(directory.iterdir())), optional.exists()))
            cache = StockInputCache()
            self.assertEqual(cache.get(root, 1, paths, loader), (0, False))
            (directory / 'new.xml').write_bytes(b'<xml/>')
            self.assertEqual(cache.get(root, 1, paths, loader), (1, False))
            optional.write_bytes(b'new')
            self.assertEqual(cache.get(root, 1, paths, loader), (1, True))
            optional.unlink()
            self.assertEqual(cache.get(root, 1, paths, loader), (1, False))

    def test_mutation_during_load_is_not_cached(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = root / 'source'
            source.write_bytes(b'a')
            cache = StockInputCache()
            def mutate():
                source.write_bytes(b'longer')
                return 'stale'
            with self.assertRaisesRegex(ValueError, 'changed while being read'):
                cache.get(root, 1, lambda: (source,), mutate)
            self.assertFalse(cache.entries)

    def test_bound_and_reparse_boundaries(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            cache = StockInputCache(capacity=2)
            for key in range(4):
                cache.get(root, key, lambda: (), lambda: key)
            self.assertEqual(len(cache.entries), 2)
            loader = Mock(return_value='uncached')
            with patch('majesty_cam.stock_input_cache._stamp', return_value=None):
                cache.get(root, 'link', lambda: (), loader)
                cache.get(root, 'link', lambda: (), loader)
            self.assertEqual(loader.call_count, 2)

    def test_dataset_cache_does_not_reread_and_project_changes_refresh_membership(self):
        with TemporaryDirectory() as tmp:
            game, _, sources = _stock_game(Path(tmp))
            _DATASET_CACHE.clear()
            first = load_dataset_symbols(game)
            with patch.object(Path, 'read_bytes', side_effect=AssertionError('warm read')):
                self.assertIs(load_dataset_symbols(game), first)
            from majesty_cam.stock_gpl import STOCK_GPL_RUNTIME_PAIRS
            project = game / 'SDK/OriginalQuests' / STOCK_GPL_RUNTIME_PAIRS[-1].project_relative
            new = project.parent / 'added.gpl'
            new.write_text('expression #NewStock 71\n')
            project.write_text(project.read_text() + 'source="added.gpl"\n')
            updated = load_dataset_symbols(game)
            self.assertIn('#newstock', updated.expansion_expressions)


if __name__ == '__main__':
    unittest.main()

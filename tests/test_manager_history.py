import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from majesty_cam.manager.catalog import Catalog
from majesty_cam.manager.catalog_changes import detect_changes, MANAGER_CHANGE_KEY
from majesty_cam.manager.history import PATCH_HISTORY
from majesty_cam.version import __version__, MANAGER_VERSION


class HistoryTests(unittest.TestCase):
    def test_updates_share_scan_baseline_and_expire_on_next_scan(self):
        with TemporaryDirectory() as temp:
            paths = SimpleNamespace(profile_path=Path(temp) / "profile.json")
            catalog = Catalog(())
            # First-ever inventory establishes a baseline, as it does for mods.
            self.assertEqual(detect_changes(paths, catalog), {})
            seen = paths.profile_path.parent / "catalog-seen.json"
            self.assertEqual(json.loads(seen.read_text())[MANAGER_CHANGE_KEY], MANAGER_VERSION)
            with patch("majesty_cam.manager.catalog_changes.MANAGER_VERSION", "new-version"):
                self.assertEqual(detect_changes(paths, catalog), {MANAGER_CHANGE_KEY: "UPDATED"})
                self.assertEqual(detect_changes(paths, catalog), {})

    def test_existing_catalog_without_manager_version_shows_update_once(self):
        with TemporaryDirectory() as temp:
            paths = SimpleNamespace(profile_path=Path(temp) / "profile.json")
            (Path(temp) / "catalog-seen.json").write_text("{}")
            self.assertEqual(detect_changes(paths, Catalog(())), {MANAGER_CHANGE_KEY: "UPDATED"})
            self.assertEqual(detect_changes(paths, Catalog(())), {})

    def test_current_version_has_brief_history_in_descending_order(self):
        self.assertEqual(PATCH_HISTORY[0][0], __version__)
        versions = [tuple(map(int, version.split("."))) for version, _ in PATCH_HISTORY]
        self.assertEqual(versions, sorted(set(versions), reverse=True))
        for _, additions in PATCH_HISTORY:
            self.assertTrue(additions)
            self.assertTrue(all(len(text) < 150 for text in additions))

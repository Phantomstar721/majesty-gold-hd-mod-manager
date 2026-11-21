"""Window-only Merge admission must coexist with independent native packages."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from majesty_cam.cam import CamArchive, CamEntry, CamSection
from majesty_cam.compose import (ComposeError, ScopedNamedResourceResolution,
    merge_text_resources)
from majesty_cam.engine_dependencies import PANEL_SERVICE
from majesty_cam.manager.catalog import CatalogKind, scan_catalog
from majesty_cam.manager.compatibility import CompatibilityRegistry
from majesty_cam.manager.engine_patches import discover
from majesty_cam.manager.preflight import prepare_merge_package
from majesty_cam.package import (PackageFormatError, load_mod_definition,
    mod_definition_mapping, parse_mod_definition, _validate_definition_object)
from majesty_cam.strt import StrtRecord, StrtTable


ONE = '11111111-1111-1111-1111-111111111111'
TWO = '22222222-2222-2222-2222-222222222222'


def package(root, name, identifier=ONE):
    from test_bcd import compiled
    from majesty_cam.gpl import DefinitionKind
    path = root / name
    (path / 'Data').mkdir(parents=True)
    (path / 'GPL').mkdir()
    (path / 'Mod.mmxml').write_text('''<Majesty><Mod id="{}">
      <DisplayName>{}</DisplayName><DataConfiguration><Dataset base="Any"><Load>
      <CAM>Data/Content.cam</CAM><GPL><Target>Data/Content.bcd</Target>
      <Source>GPL/Content.gpl</Source></GPL>
      </Load></Dataset></DataConfiguration></Mod></Majesty>'''.format(identifier, name))
    (path / 'GPL/Content.gpl').write_text('function Example()\nbegin\nend Example;\n')
    (path / 'Data/Content.bcd').write_bytes(compiled((DefinitionKind.FUNCTION, 'Example')))
    rows = StrtTable(b'\x00\x02', (StrtRecord(1, b'WE|1|BASE|AP10'),
        StrtRecord(2, ('WE|1|LABEL|200|'+name).encode('ascii'))))
    archive = CamArchive((CamSection(b'SMNU', (CamEntry(b'AP10'.ljust(20,b'\0'), name.encode()),)),
        CamSection(b'STRT', (CamEntry(b'AP10'.ljust(20,b'\0'), rows.to_bytes()),))))
    (path / 'Data/Content.cam').write_bytes(archive.to_bytes())
    definition = dict(schema_version=3, mod_id=identifier, internal_name=name,
        display_name=name, custom_buildings=[], runtime_features=[])
    write_definition(path, definition)
    return path, definition


def write_definition(path, definition):
    (path / 'mod-definition.json').write_text(json.dumps(definition))


def prepared(path, identifier=ONE):
    return prepare_merge_package(content_id=identifier, display_name=path.name,
        source_root=path, registry=CompatibilityRegistry({}))


class PanelMergeIntentTests(unittest.TestCase):
    def test_explicit_merge_uses_real_inventory_and_engine_dependency_without_fake_features(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, definition = package(root, 'Panels')
            definition['merge'] = True
            write_definition(path, definition)
            check = Mock(return_value=())
            entry = scan_catalog(local_mods_root=root, merge_preflight=check).entries[0]
            self.assertEqual(entry.kind, CatalogKind.MERGE)
            self.assertTrue(entry.merge_ready)
            self.assertTrue(entry.selectable)
            check.assert_called_once_with(ONE.upper(), 'Panels', path)
            result = prepared(path)
            self.assertTrue(result.ready, result.issues)
            self.assertEqual(result.package.definition.custom_buildings, ())
            self.assertEqual(result.package.definition.runtime_features, ())
            self.assertTrue(result.inventory.resources)
            self.assertEqual({row.requirement.service for row in discover(entry).evidence},
                {PANEL_SERVICE})

    def test_implicit_and_explicit_false_keep_independent_native_components_standard(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, definition = package(root, 'Panels')
            for flag in (None, False):
                with self.subTest(flag=flag):
                    if flag is not None:
                        definition['merge'] = flag
                    write_definition(path, definition)
                    check = Mock()
                    entry = scan_catalog(local_mods_root=root, merge_preflight=check).entries[0]
                    self.assertEqual(entry.kind, CatalogKind.STANDARD)
                    self.assertTrue(entry.selectable)
                    check.assert_not_called()
            (path / 'mod-definition.json').unlink()
            self.assertEqual(scan_catalog(local_mods_root=root).entries[0].kind, CatalogKind.STANDARD)

    def test_merge_flag_is_strict_and_roundtrips_without_changing_legacy_fingerprints(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, definition = package(root, 'Panels')
            self.assertEqual(mod_definition_mapping(parse_mod_definition(definition)), definition)
            for flag in (None, 0, 1, 'true', [], {}):
                with self.subTest(flag=flag):
                    definition['merge'] = flag
                    write_definition(path, definition)
                    with self.assertRaisesRegex(PackageFormatError, 'merge must be a boolean'):
                        load_mod_definition(path / 'mod-definition.json')
                    entry = scan_catalog(local_mods_root=root).entries[0]
                    self.assertEqual(entry.kind, CatalogKind.MERGE)
                    self.assertFalse(entry.selectable)
                    self.assertIn('invalid_merge_definition', {issue.code for issue in entry.issues})
            definition['merge'] = True
            parsed = parse_mod_definition(definition)
            self.assertTrue(parsed.merge)
            self.assertEqual(_validate_definition_object(parsed), parsed)
            self.assertEqual(mod_definition_mapping(parsed), definition)
            definition['schema_version'] = 2
            definition['runtime_capabilities'] = []
            with self.assertRaisesRegex(PackageFormatError, 'unknown merge'):
                parse_mod_definition(definition)

    def test_opt_in_does_not_bypass_identity_scope_or_source_requirements(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, definition = package(root, 'Panels')
            definition.update(merge=True, mod_id=TWO)
            write_definition(path, definition)
            entry = scan_catalog(local_mods_root=root).entries[0]
            self.assertEqual(entry.kind, CatalogKind.MERGE)
            self.assertFalse(entry.selectable)
            definition['mod_id'] = ONE
            write_definition(path, definition)
            manifest = path / 'Mod.mmxml'
            original = manifest.read_text()
            manifest.write_text(original.replace('base="Any"', 'base="MajestyExpansion"'))
            result = prepared(path)
            self.assertFalse(result.ready)
            self.assertTrue(any('scoped CAM/GPL' in issue.message for issue in result.issues))
            manifest.write_text(original)
            (path / 'GPL/Content.gpl').unlink()
            self.assertFalse(prepared(path).ready)

    def test_actual_preference_merge_keeps_the_winning_window_and_its_we_rows(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = [package(root, 'One', ONE), package(root, 'Two', TWO)]
            for path, definition in paths:
                definition['merge'] = True
                write_definition(path, definition)
            records = [prepared(paths[0][0], ONE), prepared(paths[1][0], TWO)]
            for result in records:
                self.assertTrue(result.ready, result.issues)
            inventories = tuple(result.inventory for result in records)
            with self.assertRaisesRegex(ComposeError, 'conflicting'):
                merge_text_resources(root, inventories, external_panel_behaviors=True)
            for winner in inventories:
                participants = frozenset(inv.selected.alias for inv in inventories)
                choices = {(r.section,r.key):ScopedNamedResourceResolution(r.entry,participants,winner.selected.alias)
                    for r in winner.resources}
                result = merge_text_resources(root, inventories, named_resolutions=choices,
                    external_panel_behaviors=True)
                merged = {(s.extension,e.name[:4]):e.data for s in result.text_archive.sections for e in s.entries}
                for resource in winner.resources:
                    self.assertEqual(merged[resource.section,resource.key], resource.entry.data)
                self.assertEqual(result.dialog_renames, ())

    def test_explicit_request_does_not_turn_unsupported_shapes_into_merge_ready_packages(self):
        import xml.etree.ElementTree as ET
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, definition = package(root, 'Panels')
            definition['merge'] = True
            write_definition(path, definition)
            manifest = path / 'Mod.mmxml'
            original = manifest.read_text()
            manifest.write_text(original.replace('<CAM>Data/Content.cam</CAM>', ''))
            self.assertEqual(scan_catalog(local_mods_root=root).entries[0].kind, CatalogKind.MERGE)
            self.assertFalse(prepared(path).ready)
            tree = ET.fromstring(original)
            tree.append(ET.fromstring(ET.tostring(tree[0])))
            manifest.write_bytes(ET.tostring(tree))
            entries = scan_catalog(local_mods_root=root).entries
            for entry in entries:
                self.assertEqual(entry.kind, CatalogKind.MERGE)
                self.assertFalse(entry.selectable)
                self.assertIn('multi_mod_merge_manifest', {issue.code for issue in entry.issues})

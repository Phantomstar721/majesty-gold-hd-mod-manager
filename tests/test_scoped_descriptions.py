from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET
from majesty_cam.descriptions import parse_descriptions
from majesty_cam.scoped_descriptions import build_views, inventory_view, document
from majesty_cam.compose import _build_manifest
from majesty_cam.gpl import SemanticMergeResult


def xml(spell, image='STCK', cost=100):
    return f'<Majesty><Description type="Unit" subType="Character" ID="UNIT" Name="Hero"><Engine version="1"><ImageIDBase value="{image}"/></Engine><Game version="1"><Cost value="{cost}"/><Spell value="{spell}"/></Game></Description></Majesty>'


@dataclass
class Inventory:
    selected: object
    descriptions: tuple = ()
    scoped_descriptions: tuple = ()


class ScopedDescriptionTests(unittest.TestCase):
    def test_native_scopes_preserve_their_stock_fields(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            base, expansion = root/'base.xml', root/'expansion.xml'
            base.write_text(xml('base_spell', 'PRIV'))
            expansion.write_text(xml('expansion_spell', 'PRIV'))
            inv = Inventory(SimpleNamespace(alias='owner'), (), (('Majesty', base), ('MajestyExpansion', expansion)))
            stock = {scope: parse_descriptions(xml(spell)).index for scope, spell in
                     (('Majesty', 'base_spell'), ('MajestyExpansion', 'expansion_spell'))}
            result = build_views((inv,), document(()), document(()), stock)
            for scope, expected in (('Majesty', 'base_spell'), ('MajestyExpansion', 'expansion_spell')):
                record = result[scope].records[0].to_element()
                self.assertEqual(record.find('Engine/ImageIDBase').get('value'), 'PRIV')
                self.assertEqual(record.find('Game/Spell').get('value'), expected)
            self.assertEqual(inventory_view(inv, 'Any').descriptions, ())

    def test_component_scope_replaces_its_own_any_then_keeps_generated_edits(self):
        with TemporaryDirectory() as folder:
            root = Path(folder); shared, scoped = root/'any.xml', root/'base.xml'
            shared.write_text(xml('any_spell', cost=200))
            scoped.write_text(xml('base_spell', 'PRIV', cost=100))
            inv = Inventory(SimpleNamespace(alias='owner'), (shared,), (('Majesty', scoped),))
            before = parse_descriptions(shared.read_bytes())
            after = parse_descriptions(shared.read_bytes().replace(b'</Game>', b'<Extra value="1"/></Game>'))
            result = build_views((inv,), before, after, {'Majesty': parse_descriptions(xml('base_spell')).index})
            record = result['Majesty'].records[0].to_element()
            self.assertEqual(record.find('Game/Spell').get('value'), 'base_spell')
            self.assertEqual(record.find('Game/Cost').get('value'), '100')
            self.assertEqual(record.find('Game/Extra').get('value'), '1')

    def test_manifest_uses_existing_native_scope_records(self):
        empty = SemanticMergeResult((), ()).emit_project_source_set()
        payload = _build_manifest(mod_id='{00000000-0000-0000-0000-000000000001}',
            internal_name='Fixture', display_name='Fixture', cam_filenames=(),
            description_filename='merged_descriptions.xml', source_set=empty,
            scoped_descriptions=(('Majesty', 'merged_descriptions-Majesty.xml'),
                                 ('MajestyExpansion', 'merged_descriptions-MajestyExpansion.xml')))
        mods = ET.fromstring(payload).findall('Mod')
        self.assertEqual(len(mods), 3)
        for mod, scope in zip(mods[1:], ('Majesty', 'MajestyExpansion')):
            dataset = mod.find('DataConfiguration/Dataset')
            self.assertEqual(dataset.get('base'), scope)
            self.assertEqual(dataset.find('Load/Descriptions').text, f'Data\\merged_descriptions-{scope}.xml')
            self.assertIsNone(dataset.find('Load/GPL'))

    def test_generated_reader_retains_description_only_patch(self):
        from test_scoped_output import package_fixture, result, function
        from majesty_cam.scoped_output import load_generated_bundle
        from majesty_cam.compose import validate_composed_package
        with TemporaryDirectory() as folder:
            root = Path(folder)
            package_fixture(root, result(function('Shared')))
            path = root/'Data/merged_descriptions-Majesty.xml'
            path.write_text(xml('base_spell', 'PRIV'))
            manifest = root/'CAMManager-fixture.mmxml'
            tree = ET.fromstring(manifest.read_bytes())
            from majesty_cam.scoped_output import scoped_mod_id
            patch = ET.SubElement(tree, 'Mod', {'id': scoped_mod_id(tree.find('Mod').get('id'), 'Majesty')})
            ET.SubElement(patch, 'Name').text = 'FixtureMajesty'
            ET.SubElement(patch, 'DisplayName', {'lang': 'en_US'}).text = 'Fixture Majesty'
            load = ET.SubElement(ET.SubElement(ET.SubElement(patch, 'DataConfiguration'), 'Dataset', {'base': 'Majesty'}), 'Load')
            ET.SubElement(load, 'Descriptions').text = 'Data/merged_descriptions-Majesty.xml'
            manifest.write_bytes(ET.tostring(tree))
            packages = load_generated_bundle(root)
            self.assertEqual(packages[1].datasets[0].loads[0].descriptions[0].absolute_path, path)
            validate_composed_package(root)

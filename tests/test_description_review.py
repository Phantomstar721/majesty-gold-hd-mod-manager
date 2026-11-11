import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch

from majesty_cam.descriptions import parse_descriptions
from majesty_cam.description_review import DescriptionReviewCandidate as Candidate, DescriptionReviewConflict as Conflict
from majesty_cam.description_composition import prepare_description_views, native_descriptions
from majesty_cam.script_review import ScriptReviewSession, ScriptReviewRequired, pair_key, group_conflicts


def record(cost, hp=100, identity='HALL'):
    return parse_descriptions(f'<Majesty><Description type="Unit" subType="Building" ID="{identity}" Name="Example_Hall"><Game><Cost value="{cost}"/><Health value="{hp}"/></Game></Description></Majesty>').records[0]


def conflict(*values, base=None):
    return Conflict('majesty', ('Unit', 'HALL'), 'Example Hall', '', base,
                    tuple(Candidate(owner, value, owner) for owner, value in values))


class DescriptionReviewTests(unittest.TestCase):
    def test_native_mixed_xml_indexes_only_direct_descriptions(self):
        from majesty_cam.descriptions import parse_native_descriptions, DescriptionFormatError
        payload=(b'<Majesty><Language id="en_US"><Text id="name">A name</Text></Language>'
                 +record(20).payload+b'<Quest><Description lang="en_US"><Short>Quest text</Short>'
                 b'</Description></Quest></Majesty>')
        with self.assertRaisesRegex(DescriptionFormatError,'unsupported top-level'):
            parse_descriptions(payload)
        projected=parse_native_descriptions(payload)
        self.assertEqual(tuple(projected.index),(('Unit','HALL'),))
        source=NS(package=NS(mod_id='Native'),name='Native',description_payloads=(('any',payload),))
        for scope in ('majesty','majestyexpansion'):
            variants,_=native_descriptions((source,),scope)
            self.assertEqual(variants[0][1].records[0]._fingerprint,record(20)._fingerprint)
        quest=b'<Majesty><Quest><Description lang="en_US">Text</Description></Quest></Majesty>'
        self.assertFalse(parse_native_descriptions(quest).records)
        for unsafe in (b'<!DOCTYPE Majesty [<!ENTITY x "y">]><Majesty/>',
                       b'<Majesty><Description type="Unit"/></Majesty>'):
            with self.assertRaises(DescriptionFormatError):
                parse_native_descriptions(unsafe)

    def test_script_only_composition_does_not_repackage_native_xml(self):
        class Native:
            @property
            def description_payloads(self):
                raise AssertionError('Script-only composition must leave native XML loading alone')
        common,patches,keys=prepare_description_views(Path('.'),(),(Native(),),
            ScriptReviewSession(),None,stock_views={'majesty':{},'majestyexpansion':{}})
        self.assertFalse(common.document.records)
        self.assertFalse(patches)
        self.assertFalse(keys)

    def test_development_scoped_records_keep_preferences_and_generated_fields(self):
        from dataclasses import dataclass, replace
        from majesty_cam.descriptions import serialize_descriptions
        from test_scoped_descriptions import xml
        @dataclass
        class Inventory:
            selected: object
            descriptions: tuple
            scoped_descriptions: tuple
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared, original, expansion = (root / name for name in ('any.xml', 'original.xml', 'expansion.xml'))
            shared.write_text(xml('any_spell', 'PRIV', 200))
            original.write_text(xml('original_spell', 'PRIV', 100))
            expansion.write_text(xml('expansion_spell', 'PRIV', 300))
            package = NS(mod_id='patch', metadata=NS(display_name='Patch'), datasets=(),
                         definition=NS(schema_version=3, custom_buildings=(), runtime_features=()))
            inventory = Inventory(NS(alias='patch', package=package), (shared,),
                                  (('Majesty', original), ('MajestyExpansion', expansion)))
            native = NS(name='Provider', package=NS(mod_id='provider'), description_payloads=(
                ('majesty', xml('original_spell', 'OTHR', 400).encode()),
                ('majestyexpansion', xml('expansion_spell', 'OTHR', 400).encode())))
            def finalize(views):
                results = {}
                for scope, result in views.items():
                    document = parse_descriptions(result.payload.replace(b'</Game>', b'<Extra value="1"/></Game>'))
                    results[scope] = replace(result, document=document, payload=serialize_descriptions(document))
                return results
            for winner, image in (('patch', 'PRIV'), ('provider', 'OTHR')):
                review = ScriptReviewSession()
                common, patches, _ = prepare_description_views(root, (inventory,), (native,), review,
                    lambda conflicts: {p.identity: winner for p in group_conflicts(conflicts)},
                    finalize_views=finalize, stock_views={'majesty':{}, 'majestyexpansion':{}}, dialog_resolutions=())
                self.assertFalse(common.document.records)
                for scope, spell in (('majesty', 'original_spell'), ('majestyexpansion', 'expansion_spell')):
                    hero = patches[scope].document.records[0].to_element()
                    self.assertEqual(hero.find('Engine/ImageIDBase').get('value'), image)
                    self.assertEqual(hero.find('Game/Spell').get('value'), spell)
                    self.assertEqual(hero.find('Game/Extra').get('value'), '1')

    def test_scoped_description_plans_reach_each_script_view(self):
        from majesty_cam.compose import prepare_gpl_bundle
        from test_scoped_output import result, function
        plans = {'majesty': {'spell_policy_plan': 'original'},
                 'majestyexpansion': {'spell_policy_plan': 'expansion'}}
        with patch('majesty_cam.dataset_dependencies.load_dataset_symbols', return_value={}), patch(
                'majesty_cam.compose.prepare_final_gpl_resources', return_value=result(function('Shared'))) as prepare:
            prepare_gpl_bundle(Path('.'), (), description_plans=plans)
        self.assertEqual([c.kwargs['spell_policy_plan'] for c in prepare.call_args_list], ['original', 'expansion'])

    def test_native_container_comments_do_not_change_records(self):
        from majesty_cam.descriptions import DescriptionFormatError
        plain = b'<Majesty>' + record(10).payload + b'</Majesty>'
        commented = b'<Majesty>\n // heading\n' + record(10).payload + b'\n // footer\n</Majesty>'
        self.assertEqual(parse_descriptions(plain).records[0]._fingerprint,
                         parse_descriptions(commented).records[0]._fingerprint)
        with self.assertRaises(DescriptionFormatError):
            parse_descriptions(b'<Majesty>unexpected text</Majesty>')

    def test_preference_selects_complete_authored_record(self):
        item = conflict(('a', record(10)), ('b', record(20)), base=record(0))
        review = ScriptReviewSession()
        self.assertIsNone(review.resolve(item))
        review.apply({pair_key('a', 'b'): 'b'})
        self.assertEqual(review.resolve(item)._fingerprint, record(20)._fingerprint)

    def test_independent_stock_fields_combine_without_choice(self):
        item = conflict(('a', record(10)), ('b', record(0, 200)), base=record(0))
        review = ScriptReviewSession()
        chosen = review.resolve(item)
        self.assertEqual(chosen._fingerprint, record(10, 200)._fingerprint)
        self.assertFalse(group_conflicts(review.observed))

    def test_same_pair_choice_applies_to_more_than_two_mods(self):
        item = conflict(('a', record(10)), ('b', record(20)), ('c', record(30)))
        review = ScriptReviewSession({pair_key('a','b'):'a', pair_key('a','c'):'a', pair_key('b','c'):'b'})
        self.assertEqual(review.resolve(item)._fingerprint, record(10)._fingerprint)
        with self.assertRaises(ValueError):
            ScriptReviewSession({pair_key('a','b'):'a', pair_key('a','c'):'c', pair_key('b','c'):'b'})

    def test_native_xml_obeys_component_scope_and_last_owner(self):
        def source(owner, scope, value):
            return NS(name=owner, package=NS(mod_id=owner), description_payloads=((scope,
                b'<Majesty>' + record(value).payload + b'</Majesty>'),))
        inputs = (source('a','any',10), source('b','majestyexpansion',20))
        self.assertEqual(native_descriptions(inputs,'majesty')[0][0][0], 'a')
        self.assertEqual(native_descriptions(inputs,'majestyexpansion')[0][0][0], 'b')

    def test_xml_only_standard_snapshot_tracks_xml_changes(self):
        from majesty_cam import standard_scripts
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root/'mod.mmxml'
            manifest.write_text('<Mod id="11111111-1111-1111-1111-111111111111"><DisplayName>Provider</DisplayName><DataConfiguration><Dataset base="Any"><Load><Descriptions>building.xml</Descriptions></Load></Dataset></DataConfiguration></Mod>')
            path = root/'building.xml'
            path.write_bytes(b'<Majesty>'+record(10).payload+b'</Majesty>')
            entry = NS(package_root=root, manifest_path=manifest,
                       content_id='11111111-1111-1111-1111-111111111111', display_name='Provider')
            first = standard_scripts.read(entry)
            signature = standard_scripts.fingerprint((entry,))
            path.write_bytes(b'<Majesty>'+record(200).payload+b'</Majesty>')
            second = standard_scripts.read(entry)
            self.assertNotEqual(signature, standard_scripts.fingerprint((entry,)))
            self.assertNotEqual(first.description_payloads, second.description_payloads)
            self.assertFalse(second.loads)

    def test_actual_merger_reviews_standard_overlap_and_keeps_dataset_scope(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'buildings.xml'
            path.write_bytes(b'<Majesty>'+record(10).payload+b'</Majesty>')
            definition = NS(schema_version=3, custom_buildings=(), runtime_features=())
            inventory = NS(descriptions=(path,), selected=NS(alias='patch', package=NS(
                mod_id='patch-id', definition=definition, metadata=NS(display_name='Patch'))))
            native = NS(name='Provider', package=NS(mod_id='provider-id'),
                description_payloads=(('majestyexpansion', b'<Majesty>'+record(20).payload+b'</Majesty>'),))
            review = ScriptReviewSession()
            def choose(conflicts):
                return {p.identity: 'patch-id' for p in group_conflicts(conflicts)}
            with patch('majesty_cam.compose._load_effective_stock_descriptions', return_value={}):
                common, patches, keys = prepare_description_views(Path(tmp), (inventory,), (native,), review,
                    choose, dialog_resolutions=())
            self.assertFalse(common.document.records)
            self.assertEqual(set(patches), {'majestyexpansion'})
            self.assertEqual(patches['majestyexpansion'].document.records[0]._fingerprint, record(10)._fingerprint)
            self.assertEqual(keys, {('Unit','HALL')})
            self.assertEqual(review.applicable_decisions, {pair_key('patch-id','provider-id'):'patch-id'})
            with patch('majesty_cam.compose._load_effective_stock_descriptions', return_value={}):
                from majesty_cam.script_review import ScriptReviewCancelled
                with self.assertRaises(ScriptReviewCancelled):
                    prepare_description_views(Path(tmp), (inventory,), (native,), ScriptReviewSession(),
                                              lambda _: None, dialog_resolutions=())

    def test_player_label_names_building_without_source_diff(self):
        from majesty_cam.manager.script_review_dialog import _gameplay_label, _gameplay_descriptions
        item = conflict(('a',record(10)), ('b',record(20)))
        self.assertEqual(_gameplay_label(item), 'Building: Example Hall')
        self.assertIn('preferred mod', _gameplay_descriptions((item,)))

    def test_xml_and_script_share_one_preference(self):
        from majesty_cam.script_review import ScriptCandidate, ScriptConflict
        from majesty_cam.gpl import parse_gpl
        a = parse_gpl('function sample() is integer\nbegin\nreturn 1;\nend').items[0]
        b = parse_gpl('function sample() is integer\nbegin\nreturn 2;\nend').items[0]
        review = ScriptReviewSession({pair_key('a','b'):'b'})
        xml = conflict(('a',record(10)), ('b',record(20)))
        script = ScriptConflict('majesty', a.key, 'sample', '', None,
                                (ScriptCandidate('a',a), ScriptCandidate('b',b)))
        self.assertEqual(review.resolve(xml)._fingerprint, record(20)._fingerprint)
        self.assertEqual(review.resolve(script).text, b.text)
        self.assertEqual(len(group_conflicts(review.observed)), 1)

    def test_external_building_evidence_deferred_only_until_selection(self):
        from test_compose import _write_stock_description_dirs, _v3_description_inventory, _panel_pair
        from majesty_cam.compose import validate_controller_stock_evidence, ComposeError
        from majesty_cam.stock_controller_registry import resolve_stock_controller_registry
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_description_dirs(root)
            xml = '<Majesty><Description type="Building" ID="PV01" subType="Building" Name="Private"><Game><DialogID value="B001"/></Game></Description></Majesty>'
            inventory = _v3_description_inventory(root, 'patch', xml, resources=_panel_pair('patch', b'B001'))
            inventory.selected.package.root = root
            registry = resolve_stock_controller_registry((), {})
            validate_controller_stock_evidence(root, (inventory,), registry, defer_external_buildings=True)
            with self.assertRaisesRegex(ComposeError, 'custom_building'):
                validate_controller_stock_evidence(root, (inventory,), registry)
            validate_controller_stock_evidence(root, (inventory,), registry,
                                              external_building_keys={('Building','PV01')})

    def test_xml_only_scope_uses_native_manifest_without_dummy_gpl(self):
        import xml.etree.ElementTree as ET
        from test_scoped_output import package_fixture, result, COMMON_ID
        from majesty_cam.compose import _build_manifest
        from majesty_cam.scoped_output import load_generated_bundle
        from majesty_cam.package import PackageFormatError
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            empty = result('')
            package_fixture(root, empty)
            name = 'merged_descriptions-majestyexpansion.xml'
            (root/'Data'/name).write_bytes(b'<Majesty>'+record(30).payload+b'</Majesty>')
            manifest = root/'CAMManager-fixture.mmxml'
            manifest.write_bytes(_build_manifest(mod_id=COMMON_ID, internal_name='Fixture', display_name='Fixture',
                cam_filenames=(), description_filename='Descriptions.xml', source_set=empty.source_set,
                scoped_sources=(('MajestyExpansion', empty.source_set),),
                scoped_descriptions={'MajestyExpansion':name}))
            packages = load_generated_bundle(root)
            self.assertEqual(len(packages), 2)
            self.assertFalse(packages[1].datasets[0].loads[0].gpl)
            self.assertEqual(len(packages[1].datasets[0].loads[0].descriptions), 1)
            tree = ET.fromstring(manifest.read_bytes())
            tree.findall('Mod')[1].find('./DataConfiguration/Dataset/Load/Descriptions').text = 'Data/Descriptions.xml'
            manifest.write_bytes(ET.tostring(tree))
            with self.assertRaisesRegex(PackageFormatError, 'owned by its scope'):
                load_generated_bundle(root)

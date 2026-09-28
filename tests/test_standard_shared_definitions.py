"""Shared metadata must never share native component identity or sources."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from majesty_cam.gpl import DefinitionKind, SemanticMergeResult, parse_gpl, add_hero_quest_lifecycle_callbacks
from majesty_cam.package import load_mod_definition, load_standard_definition, PackageFormatError
from majesty_cam.private_hero_gpl import validate_bindings
from majesty_cam.standard_scripts import read, participant_inventories, file_inputs, for_dataset
from majesty_cam.manager.catalog import scan_catalog
from test_bcd import compiled
from test_private_hero_gpl import tree, CALLBACKS


IDS = tuple(f'aaaaaaaa-bbbb-cccc-dddd-{i:012d}' for i in range(1, 7))
FEATURE = dict(type='stock.hero-quest-participant.v1', feature_key='shared-hero',
               hero_script='Private_Hero', stock_hero_script='mx_healer')


def definition():
    return dict(schema_version=3, mod_ids=list(IDS), internal_name='SharedHeroes',
                display_name='Shared heroes', custom_buildings=[], runtime_features=[FEATURE])


class SharedStandardDefinitionTests(TestCase):
    def test_selected_identity_and_legacy_definitions(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'mod-definition.json'
            value = definition()
            path.write_text(json.dumps(value))
            for identity in IDS:
                selected = '{' + identity.upper() + '}'
                parsed = load_standard_definition(path, selected)
                self.assertEqual(parsed.mod_id, selected)
                self.assertEqual(parsed.runtime_features[0].hero_script, 'Private_Hero')
            # Merge-package identity is still singular; no first-ID fallback.
            with self.assertRaises(PackageFormatError):
                load_mod_definition(path)
            value.pop('mod_ids')
            value['mod_id'] = IDS[0]
            path.write_text(json.dumps(value))
            self.assertEqual(load_standard_definition(path, IDS[0]), load_mod_definition(path))
            with self.assertRaisesRegex(PackageFormatError, 'different Mod ID'):
                load_standard_definition(path, IDS[1])
            for schema in (1, 2):
                legacy = {**value, 'schema_version': schema}
                legacy.pop('runtime_features')
                if schema == 2:
                    legacy['runtime_capabilities'] = []
                path.write_text(json.dumps(legacy))
                self.assertEqual(load_standard_definition(path, IDS[0]), load_mod_definition(path))

    def test_rejects_invalid_or_unscoped_shared_metadata(self):
        cases = [
            ({'mod_ids': []}, 'nonempty'),
            ({'mod_ids': IDS[0]}, 'nonempty'),
            ({'mod_ids': [None]}, 'string'),
            ({'mod_ids': ['not-a-uuid']}, 'valid Mod UUID'),
            ({'mod_ids': [IDS[0], '{' + IDS[0].upper() + '}']}, 'duplicate'),
            ({'mod_ids': [IDS[1]]}, 'does not include'),
            ({'mod_id': IDS[0]}, 'replaces mod_id'),
            ({'schema_version': 2}, 'schema_version 3'),
            ({'schema_version': 4}, 'schema_version 3'),
            ({'custom_buildings': [{}]}, 'empty custom_buildings'),
            ({'runtime_capabilities': []}, 'unknown'),
            ({'unexpected': True}, 'unknown'),
            ({'runtime_features': [{'type': 'stock.spell-evaluation-equivalent.v1',
                                    'feature_key': 'spell', 'private_spell': 'Private_Bolt',
                                    'stock_spell': 'energy_blast', 'hero_title': 'Private_Hero'}]},
             'unsupported Standard script declarations'),
        ]
        with TemporaryDirectory() as temp:
            path = Path(temp) / 'mod-definition.json'
            for changes, message in cases:
                with self.subTest(changes=changes):
                    path.write_text(json.dumps({**definition(), **changes}))
                    with self.assertRaises(PackageFormatError) as error:
                        load_standard_definition(path, IDS[0])
                    if message:
                        self.assertIn(message, str(error.exception))
            path.write_text(json.dumps(definition()).replace('"mod_ids":', '"mod_ids": [], "mod_ids":'))
            with self.assertRaisesRegex(PackageFormatError, 'duplicate JSON key'):
                load_standard_definition(path, IDS[0])

    def test_six_components_stay_standard_and_use_only_selected_sources(self):
        with TemporaryDirectory() as temp:
            mods = Path(temp)
            root = mods / 'Variants'
            root.mkdir()
            manifest = root / 'Variants.mmxml'
            nodes = []
            for index, identity in enumerate(IDS):
                # Same tree name, but distinct behavior in each component.
                source = tree('Private_Hero', healer=True).items[0].text.replace(
                    '$Go_Home(ThisAgent,90)', f'$Go_Home(ThisAgent,{80 + index})')
                (root / f'Variant{index}.gpl').write_text(source)
                (root / f'Variant{index}.bcd').write_bytes(compiled((DefinitionKind.FUNCTION, 'Private_Hero')))
                nodes.append(f'''<Mod id="{{{identity}}}"><DataConfiguration>
                    <Dataset base="MajestyExpansion"><Load><GPL>
                    <Target>Variant{index}.bcd</Target><Source>Variant{index}.gpl</Source>
                    </GPL></Load></Dataset></DataConfiguration>
                    <DisplayName lang="en_US">Variant {index}</DisplayName></Mod>''')
            manifest.write_text('<Majesty>' + ''.join(nodes) + '</Majesty>')
            path = root / 'mod-definition.json'
            path.write_text(json.dumps(definition()))
            catalog = scan_catalog(local_mods_root=mods)
            self.assertEqual(len(catalog.standard), 6)
            self.assertFalse(catalog.merge)
            for entry in catalog.standard:
                self.assertTrue(entry.selectable)
                native = read(entry)
                index = IDS.index(entry.content_id.casefold())
                self.assertEqual(native.package.mod_id.strip('{}').casefold(), IDS[index])
                self.assertEqual(len(native.loads), 1)
                self.assertEqual(native.loads[0].target.relative_path, f'Variant{index}.bcd')
                self.assertEqual(len(native.payloads), 1)
                self.assertEqual(for_dataset((native,), 'majesty'), ())
                self.assertEqual(for_dataset((native,), 'majestyexpansion'), (native,))
                inventory, = participant_inventories((native,))
                private, _ = validate_bindings([(entry.content_id, native.participants,
                                                inventory.semantic_sources, ())])
                source = inventory.semantic_sources[0]
                result = SemanticMergeResult((*source.items, *parse_gpl(CALLBACKS).items), ())
                hooked = add_hero_quest_lifecycle_callbacks(result,
                    [(('mx_healer',), 'Resume', 'Consider', 'Reset', 'Death')],
                    stock_hero_trees={'mx_healer': tree('Healer_tree', healer=True).items[0]},
                    private_hero_trees=private)
                hero = next(i.text for i in hooked.items if i.normalized_name == 'private_hero')
                self.assertEqual(hero.count('$Resume(ThisAgent)'), 1)
                self.assertEqual(hero.count('$Consider(ThisAgent)'), 1)
                self.assertIn(f'$Go_Home(ThisAgent,{80 + index})', hero)
                self.assertIs(read(entry), native)

            selected = catalog.standard[0]
            before = file_inputs((read(selected),))
            changed = definition()
            changed['runtime_features'] = [{**FEATURE, 'feature_key': 'updated-shared-hero'}]
            path.write_text(json.dumps(changed))
            updated = read(selected)
            self.assertNotEqual(before, file_inputs((updated,)))
            self.assertEqual(updated.participants[0].feature_key, 'updated-shared-hero')
            changed['mod_ids'] = [i for i in IDS if i != selected.content_id.casefold()]
            path.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'does not include'):
                read(selected)

    def test_shared_declaration_cannot_borrow_a_sibling_tree(self):
        from test_standard_scripts import provider, function
        from dataclasses import replace
        from majesty_cam.gpl_features import StockHeroQuestParticipant
        from majesty_cam.package import ModDefinition
        participant = StockHeroQuestParticipant('hero', 'Private_Hero', 'mx_healer')
        selected = replace(provider(function()), participants=(participant,),
            package=SimpleNamespace(mod_id=IDS[0], definition=ModDefinition(3, IDS[0], 'One', 'One', ())))
        sibling = provider(tree('Private_Hero', healer=True).items[0].text, 'Sibling')
        with self.assertRaisesRegex(ValueError, 'has no manifest-registered source'):
            participant_inventories((selected, sibling))

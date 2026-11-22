"""Window collisions between selected Merge packages: declarations and choices."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from majesty_cam.cam import CamArchive, CamEntry, CamSection
from majesty_cam.compose import ComposeError, merge_text_resources
from majesty_cam.description_composition import prepare_description_views
from majesty_cam.package import (PackageFormatError, ResourceReplacement,
    _validate_definition_object, mod_definition_mapping, parse_mod_definition)
from majesty_cam.script_review import (ScriptReviewRequired, ScriptReviewSession,
    group_conflicts, pair_key)
from majesty_cam.window_review import WindowConflict
from test_panel_engine_merge_intent import ONE, TWO, package, prepared, write_definition


THREE = '33333333-3333-3333-3333-333333333333'


def replaces(identifier, *panels):
    return {'mod_id': '{' + identifier + '}', 'panels': list(panels)}


def selected(test, root, *specs):
    """Prepare Merge window packages; each spec is (name, mod_id, replacements)."""
    inventories = []
    for name, identifier, replacements in specs:
        path, definition = package(root, name, identifier)
        definition['merge'] = True
        if replacements:
            definition['resource_replacements'] = replacements
        write_definition(path, definition)
        result = prepared(path, identifier)
        test.assertTrue(result.ready, result.issues)
        inventories.append(result.inventory)
    return tuple(inventories)


def merged(result):
    return {(section.extension, entry.name[:4]): entry.data
            for section in result.text_archive.sections for entry in section.entries}


class PanelResourceReplacementDefinitionTests(unittest.TestCase):
    BASE = dict(schema_version=3, mod_id=ONE, internal_name='Panels',
                display_name='Panels', custom_buildings=[], runtime_features=[])

    def test_declaration_roundtrips_and_omission_keeps_legacy_mappings(self):
        self.assertNotIn('resource_replacements',
                         mod_definition_mapping(parse_mod_definition(dict(self.BASE))))
        value = dict(self.BASE, merge=True,
                     resource_replacements=[replaces(TWO, 'AP10', 'MSuA')])
        parsed = parse_mod_definition(value)
        self.assertEqual(parsed.resource_replacements,
                         (ResourceReplacement('{' + TWO + '}', ('AP10', 'MSuA')),))
        self.assertEqual(mod_definition_mapping(parsed), value)
        self.assertEqual(_validate_definition_object(parsed), parsed)

    def test_malformed_declarations_are_rejected(self):
        cases = (
            ({}, 'must be an array'),
            (['AP10'], 'must be an object'),
            ([{'mod_id': TWO}], 'fields are invalid'),
            ([dict(replaces(TWO, 'AP10'), priority=1)], 'fields are invalid'),
            ([replaces('not-a-uuid', 'AP10')], 'must be a mod UUID'),
            ([replaces(ONE, 'AP10')], 'must name another package'),
            ([replaces(TWO, 'AP10'), replaces(TWO.upper(), 'AP05')], 'repeats'),
            ([replaces(TWO)], 'non-empty array'),
            ([replaces(TWO, 'AP1')], 'four printable ASCII'),
            ([replaces(TWO, 'AP10', 'AP10')], 'duplicate panel'),
        )
        for declaration, message in cases:
            with self.subTest(declaration=declaration):
                with self.assertRaisesRegex(PackageFormatError, message):
                    parse_mod_definition(dict(self.BASE, resource_replacements=declaration))
        legacy = dict(self.BASE, schema_version=2, runtime_capabilities=[],
                      resource_replacements=[replaces(TWO, 'AP10')])
        del legacy['runtime_features']
        with self.assertRaisesRegex(PackageFormatError, 'unknown resource_replacements'):
            parse_mod_definition(legacy)


class PanelResourceReplacementMergeTests(unittest.TestCase):
    def test_declared_replacement_chooses_the_declarer_for_that_pair(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            plain = selected(self, root / 'plain', ('One', ONE, None), ('Two', TWO, None))
            with self.assertRaisesRegex(ComposeError, 'conflicting'):
                merge_text_resources(root, plain, external_panel_behaviors=True)
            for winner, loser in ((ONE, TWO), (TWO, ONE)):
                with self.subTest(winner=winner):
                    inventories = selected(self, root / winner,
                        ('One', ONE, [replaces(TWO, 'AP10')] if winner == ONE else None),
                        ('Two', TWO, [replaces(ONE, 'AP10')] if winner == TWO else None))
                    result = merge_text_resources(root, inventories, external_panel_behaviors=True)
                    chosen = inventories[0] if winner == ONE else inventories[1]
                    output = merged(result)
                    for resource in chosen.resources:
                        self.assertEqual(output[resource.section, resource.key],
                                         resource.entry.data)
                    self.assertEqual(result.dialog_renames, ())

    def test_one_declaration_may_cover_several_targets(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventories = selected(self, root,
                ('One', ONE, [replaces(TWO, 'AP10'), replaces(THREE, 'AP10')]),
                ('Two', TWO, None), ('Three', THREE, None))
            output = merged(merge_text_resources(root, inventories, external_panel_behaviors=True))
            for resource in inventories[0].resources:
                self.assertEqual(output[resource.section, resource.key], resource.entry.data)

    def test_an_unselected_target_leaves_the_package_unchanged(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventories = selected(self, root, ('One', ONE, [replaces(TWO, 'AP10')]))
            output = merged(merge_text_resources(root, inventories, external_panel_behaviors=True))
            for resource in inventories[0].resources:
                self.assertEqual(output[resource.section, resource.key], resource.entry.data)

    def test_an_undeclared_third_package_still_conflicts(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventories = selected(self, root, ('One', ONE, [replaces(TWO, 'AP10')]),
                                   ('Two', TWO, None), ('Three', THREE, None))
            with self.assertRaisesRegex(ComposeError, 'conflicting'):
                merge_text_resources(root, inventories, external_panel_behaviors=True)

    def test_competing_declarations_are_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventories = selected(self, root, ('One', ONE, [replaces(TWO, 'AP10')]),
                                   ('Two', TWO, [replaces(ONE, 'AP10')]))
            with self.assertRaisesRegex(ComposeError, 'declared as a replacement by both'):
                merge_text_resources(root, inventories, external_panel_behaviors=True)

    def test_a_layout_only_target_is_replaced_by_the_complete_window(self):
        # A plain art/layout patch often ships a changed SMNU with no STRT text.
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            path, definition = package(root, 'Two', TWO)
            archive = CamArchive((CamSection(b'SMNU', (
                CamEntry(b'AP10'.ljust(20, b'\0'), b'layout only'),)),))
            (path / 'Data/Content.cam').write_bytes(archive.to_bytes())
            two = prepared(path, TWO)
            self.assertTrue(two.ready, two.issues)
            one = selected(self, root / 'declarer', ('One', ONE, [replaces(TWO, 'AP10')]))[0]
            output = merged(merge_text_resources(root, (one, two.inventory),
                                                 external_panel_behaviors=True))
            for resource in one.resources:
                self.assertEqual(output[resource.section, resource.key], resource.entry.data)

    def test_preflight_rejects_a_declared_panel_the_package_does_not_ship(self):
        with TemporaryDirectory() as temporary:
            path, definition = package(Path(temporary), 'Panels')
            definition.update(merge=True, resource_replacements=[replaces(TWO, 'AP10', 'AP11')])
            write_definition(path, definition)
            result = prepared(path)
            self.assertFalse(result.ready)
            self.assertEqual([issue.code for issue in result.issues],
                             ['unshipped_replacement_panel'])
            self.assertIn('AP11', result.issues[0].message)


class WindowPreferenceReviewTests(unittest.TestCase):
    """Undeclared window collisions become one preferred-mod choice per pair."""

    WINDOW_LABELS = {'Window layout: AP10', 'Window text: AP10'}
    NO_STOCK = {'majesty': {}, 'majestyexpansion': {}}

    def test_an_undeclared_collision_is_a_pair_choice_not_a_stop(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventories = selected(self, root, ('One', ONE, None), ('Two', TWO, None))
            review = ScriptReviewSession()
            merge_text_resources(root, inventories, external_panel_behaviors=True,
                                 window_review=review)
            self.assertTrue(all(isinstance(c, WindowConflict) for c in review.unresolved))
            self.assertEqual({c.gameplay_label for c in review.unresolved}, self.WINDOW_LABELS)
            self.assertEqual(len(group_conflicts(review.unresolved)), 1)
            with self.assertRaises(ScriptReviewRequired):
                review.require_resolved()
            for winner, index in ((ONE, 0), (TWO, 1)):
                with self.subTest(winner=winner):
                    saved = ScriptReviewSession({pair_key(ONE, TWO): winner})
                    output = merged(merge_text_resources(root, inventories,
                        external_panel_behaviors=True, window_review=saved))
                    self.assertEqual(saved.unresolved, ())
                    for resource in inventories[index].resources:
                        self.assertEqual(output[resource.section, resource.key],
                                         resource.entry.data)

    def test_window_choices_join_the_consolidated_review_then_merge_again(self):
        # The order Prepare uses: provisional text merge, the one preference
        # dialog (raised from the Description review), then the final merge.
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventories = selected(self, root, ('One', ONE, None), ('Two', TWO, None))
            review = ScriptReviewSession()
            merge_text_resources(root, inventories, external_panel_behaviors=True,
                                 window_review=review)
            asked = []

            def choose(conflicts):
                asked.extend(conflicts)
                return {pair.identity: TWO for pair in group_conflicts(conflicts)}

            prepare_description_views(root, inventories, (), review, choose,
                                      stock_views=self.NO_STOCK)
            self.assertEqual({c.gameplay_label for c in asked}, self.WINDOW_LABELS)
            self.assertEqual(review.unresolved, ())
            output = merged(merge_text_resources(root, inventories,
                external_panel_behaviors=True, window_review=review))
            for resource in inventories[1].resources:
                self.assertEqual(output[resource.section, resource.key], resource.entry.data)
            # Without a resolver, an unanswered window choice still stops.
            unanswered = ScriptReviewSession()
            merge_text_resources(root, inventories, external_panel_behaviors=True,
                                 window_review=unanswered)
            with self.assertRaises(ScriptReviewRequired):
                prepare_description_views(root, inventories, (), unanswered, None,
                                          stock_views=self.NO_STOCK)

    def test_a_declared_replacement_is_never_asked(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventories = selected(self, root, ('One', ONE, [replaces(TWO, 'AP10')]),
                                   ('Two', TWO, None))
            review = ScriptReviewSession()
            output = merged(merge_text_resources(root, inventories,
                external_panel_behaviors=True, window_review=review))
            self.assertEqual(review.observed, ())
            for resource in inventories[0].resources:
                self.assertEqual(output[resource.section, resource.key], resource.entry.data)

    def test_identical_windows_ask_nothing(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            one_path, _ = package(root, 'One', ONE)
            two_path, _ = package(root, 'Two', TWO)
            (two_path / 'Data/Content.cam').write_bytes(
                (one_path / 'Data/Content.cam').read_bytes())
            inventories = tuple(prepared(path, identifier).inventory
                                for path, identifier in ((one_path, ONE), (two_path, TWO)))
            review = ScriptReviewSession()
            merge_text_resources(root, inventories, external_panel_behaviors=True,
                                 window_review=review)
            self.assertEqual(review.observed, ())


if __name__ == '__main__':
    unittest.main()

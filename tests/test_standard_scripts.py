from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
import struct
from tempfile import TemporaryDirectory

from majesty_cam.gpl import parse_gpl, SemanticMergeResult, DefinitionKind
from majesty_cam.compose import GplComposeResult, _build_manifest
from majesty_cam.standard_scripts import StandardScripts, Providers, for_dataset, _matches_source_locations
from majesty_cam.gpl_function_merge import merge_function, FunctionMergeError
from majesty_cam.script_review import ScriptCandidate, ScriptReviewSession, group_conflicts


def function(value=1, extra=''):
    return f'function Example(agent ThisAgent)\nbegin\n{extra}\nThisAgent\'s "Value" = {value};\nend\n'


def result(text):
    return GplComposeResult(SemanticMergeResult(parse_gpl(text).items, ()).emit_project_source_set(), (), (), (), ())


def provider(text, name='Native'):
    return StandardScripts(name, SimpleNamespace(mod_id=name, root=Path('.')), (),
                           (parse_gpl(text, name),), (), ())


class StandardScriptTests(TestCase):
    def compiled_provider(self, definitions, text=None, name='Compiled'):
        from test_bcd import compiled
        path = Path(name + '.gpl')
        target = Path(name + '.bcd')
        return replace(provider('', name),
            loads=(SimpleNamespace(sources=() if text is None else (SimpleNamespace(absolute_path=path),),
                                   target=SimpleNamespace(absolute_path=target, relative_path=str(target))),),
            sources=(), payloads=() if text is None else ((path, text.encode()),),
            compiled_payloads=((target, compiled(*definitions)),))

    def test_compiled_only_unrelated_definition_is_not_a_global_conflict(self):
        native = self.compiled_provider(((DefinitionKind.FUNCTION, 'Other'),))
        context = Providers((native,), None, Path('unused'))
        with patch('majesty_cam.standard_scripts.verify') as verify, \
             patch('pathlib.Path.read_bytes', side_effect=AssertionError('must use snapshot')):
            self.assertIsNone(context.lookup((DefinitionKind.FUNCTION, 'example')))
            verify.assert_not_called()
        with self.assertRaisesRegex(ValueError, r'Compiled.bcd supplies function:other'):
            context.lookup((DefinitionKind.FUNCTION, 'other'))

    def test_all_compiled_namespaces_are_guarded_and_indexed_once(self):
        from majesty_cam.bcd import definition_keys
        keys = tuple((k, '#owned' if k is DefinitionKind.EXPRESSION else 'owned') for k in DefinitionKind)
        native = self.compiled_provider(keys)
        with patch('majesty_cam.standard_scripts.definition_keys', wraps=definition_keys) as index:
            for scope in ('majesty', 'majestyexpansion'):
                context = Providers((native,), None, Path('unused'), scope)
                for key in keys:
                    with self.assertRaisesRegex(ValueError, 'supplies .*owned'):
                        context.lookup(key)
                self.assertIsNone(context.lookup((DefinitionKind.FUNCTION, 'not_owned')))
            self.assertEqual(index.call_count, 1)

    def test_compiled_native_scope_and_later_provider_still_apply(self):
        opaque = replace(self.compiled_provider(((DefinitionKind.FUNCTION, 'Example'),)), bases=('majestyexpansion',))
        self.assertIsNone(Providers((opaque,), None, Path('unused'), 'majesty').lookup((DefinitionKind.FUNCTION, 'example')))
        with patch('majesty_cam.standard_scripts.verify'):
            context = Providers((opaque, provider(function(), 'Last')), None, Path('unused'), 'majestyexpansion')
            self.assertEqual(context.lookup((DefinitionKind.FUNCTION, 'example')).text, function())

    def test_mixed_blocks_follow_load_order_and_verify_only_winning_source(self):
        known = self.compiled_provider(((DefinitionKind.FUNCTION, 'Example'),), function(), 'Known')
        opaque = self.compiled_provider(((DefinitionKind.FUNCTION, 'Other'),))
        native = replace(known, loads=known.loads + opaque.loads,
                         compiled_payloads=known.compiled_payloads + opaque.compiled_payloads)
        context = Providers((native,), None, Path('unused'))
        with patch('majesty_cam.standard_scripts.verify') as verify:
            self.assertIn('Example', context.lookup((DefinitionKind.FUNCTION, 'example')).text)
            verify.assert_called_once_with(native, Path('unused'), 0)
        shadow = self.compiled_provider(((DefinitionKind.FUNCTION, 'Example'),))
        replaced = replace(known, loads=known.loads + shadow.loads,
                           compiled_payloads=known.compiled_payloads + shadow.compiled_payloads)
        with self.assertRaisesRegex(ValueError, 'supplies function:example'):
            Providers((replaced,), None, Path('unused')).lookup((DefinitionKind.FUNCTION, 'example'))
        restored = replace(replaced, loads=tuple(reversed(replaced.loads)))
        with patch('majesty_cam.standard_scripts.verify') as verify:
            Providers((restored,), None, Path('unused')).lookup((DefinitionKind.FUNCTION, 'example'))
            verify.assert_called_once_with(restored, Path('unused'), 1)

    def test_partial_declared_source_does_not_hide_compiled_ownership(self):
        native = self.compiled_provider(((DefinitionKind.FUNCTION, 'Example'),), function().replace('Example', 'Unrelated'))
        with self.assertRaisesRegex(ValueError, 'supplies function:example'):
            Providers((native,), None, Path('unused')).lookup((DefinitionKind.FUNCTION, 'example'))

    def test_only_winning_block_sources_are_parsed_and_cached(self):
        known = self.compiled_provider(((DefinitionKind.FUNCTION, 'Example'),), function(), 'Known')
        broken = self.compiled_provider(((DefinitionKind.FUNCTION, 'Other'),), 'unparsed invalid text', 'Broken')
        native = replace(known, loads=known.loads + broken.loads,
                         payloads=known.payloads + broken.payloads,
                         compiled_payloads=known.compiled_payloads + broken.compiled_payloads)
        from majesty_cam.compose import _parse_semantic_source_file_cached
        with patch('majesty_cam.standard_scripts.verify'), patch(
                'majesty_cam.compose._parse_semantic_source_file_cached',
                wraps=_parse_semantic_source_file_cached) as parse:
            for scope in ('majesty', 'majestyexpansion'):
                context = Providers((native,), None, Path('unused'), scope)
                self.assertEqual(context.lookup((DefinitionKind.FUNCTION, 'example')).text, function())
            self.assertEqual(parse.call_count, 1)
            with self.assertRaisesRegex(ValueError, 'unparsed'):
                context.lookup((DefinitionKind.FUNCTION, 'other'))
        changed = replace(native, payloads=((known.payloads[0][0], function(9).encode()), *broken.payloads))
        with patch('majesty_cam.standard_scripts.verify'):
            context = Providers((changed,), None, Path('unused'), 'majesty')
            self.assertEqual(context.lookup((DefinitionKind.FUNCTION, 'example')).text, function(9))

    def test_review_collects_all_native_conflicts_and_replays_explicit_choices(self):
        from majesty_cam.script_review import ScriptReviewSession
        stock = function() + function().replace('Example', 'Other')
        authored = function(9) + function(10).replace('Example', 'Other') + function().replace('Example', 'Untouched')
        native = provider(function(7) + function(8).replace('Example', 'Other'), 'Effective Standard mod')
        context = Providers((native,), lambda _: {i.key: i for i in parse_gpl(stock).items}, Path('compiler'), 'majesty')
        source = SemanticMergeResult(parse_gpl(authored).items, ())
        review = ScriptReviewSession()
        with patch('majesty_cam.standard_scripts.verify'):
            candidates = {item.key: (ScriptCandidate('Merge A', item, 'merge-a'),) for item in source.items}
            partial = context.reconcile(source, review=review, merge_candidates=candidates)
            self.assertEqual([i.name for i in partial.items], ['Untouched'])
            self.assertEqual([c.name for c in review.unresolved], ['Example', 'Other'])
            self.assertEqual([c.candidates[0].label for c in review.unresolved], ['Effective Standard mod'] * 2)
            self.assertEqual(review.unresolved[0].candidates[1].label, 'Merge A')
            pairs = group_conflicts(review.conflicts)
            self.assertEqual(len(pairs), 1)
            review.apply({pair.identity: 'merge-a' for pair in pairs})
            resolved = context.reconcile(source, review=review, merge_candidates=candidates)
            self.assertEqual([i.text for i in resolved.items], [i.text for i in source.items])
            self.assertEqual(review.unresolved, ())

    def test_review_labels_can_name_only_actual_contributors_per_definition(self):
        from majesty_cam.script_review import ScriptReviewSession
        stock = function() + function().replace('Example', 'Other')
        authored = function(9) + function(10).replace('Example', 'Other')
        native = provider(function(7) + function(8).replace('Example', 'Other'))
        context = Providers((native,), lambda _: {i.key: i for i in parse_gpl(stock).items}, Path('compiler'), 'majesty')
        source = SemanticMergeResult(parse_gpl(authored).items, ())
        review = ScriptReviewSession()
        with patch('majesty_cam.standard_scripts.verify'):
            context.reconcile(source, review=review, merge_candidates={
                source.items[0].key: (ScriptCandidate('First', source.items[0]),),
                source.items[1].key: (ScriptCandidate('Second', source.items[1]),)})
        self.assertEqual([c.candidates[1].label for c in review.unresolved],
                         ['First', 'Second'])

    def test_review_without_stock_requires_proven_source_and_preserves_namespace(self):
        from majesty_cam.script_review import ScriptReviewSession
        native = provider('expression #Example 1\n')
        context = Providers((native,), None, Path('compiler'), 'majesty')
        authored = SemanticMergeResult(parse_gpl('expression #Example 2\n').items, ())
        candidates = {authored.items[0].key: (ScriptCandidate('Merge', authored.items[0]),)}
        review = ScriptReviewSession()
        with patch('majesty_cam.standard_scripts.verify', side_effect=ValueError('source does not match bytecode')):
            with self.assertRaisesRegex(ValueError, 'does not match bytecode'):
                context.reconcile(authored, review=review)
        self.assertEqual(review.conflicts, ())
        with patch('majesty_cam.standard_scripts.verify'):
            self.assertEqual(context.reconcile(authored, review=review, merge_candidates=candidates).items, ())
        entry = review.unresolved[0]
        self.assertIsNone(entry.base)
        self.assertEqual(entry.key, (DefinitionKind.EXPRESSION, '#example'))
        review.apply({pair.identity: 'native' for pair in group_conflicts(review.conflicts)})
        self.assertEqual(context.reconcile(authored, review=review, merge_candidates=candidates).items[0].text,
                         native.items[entry.key].text)

    def test_unattributed_manager_behavior_is_not_a_player_mod_choice(self):
        context = Providers((provider(function(8)),),
                            lambda _: {i.key: i for i in parse_gpl(function()).items},
                            Path('compiler'), 'majesty')
        review = ScriptReviewSession()
        with patch('majesty_cam.standard_scripts.verify'):
            with self.assertRaisesRegex(ValueError, 'cannot attribute'):
                context.reconcile(SemanticMergeResult(parse_gpl(function(9)).items, ()), review=review)
        self.assertEqual(review.conflicts, ())

    def test_review_cannot_override_opaque_native_ownership(self):
        from majesty_cam.script_review import ScriptReviewSession
        native = self.compiled_provider(((DefinitionKind.FUNCTION, 'Example'),))
        context = Providers((native,), None, Path('unused'), 'majesty')
        review = ScriptReviewSession()
        with self.assertRaisesRegex(ValueError, 'Source files are required'):
            context.reconcile(SemanticMergeResult(parse_gpl(function()).items, ()), review=review)
        self.assertEqual(review.conflicts, ())

    def test_review_skip_keys_keep_already_reviewed_items_and_do_not_add_fallbacks(self):
        from majesty_cam.script_review import ScriptReviewSession
        selected = parse_gpl(function(9)).items[0]
        missing = parse_gpl(function().replace('Example', 'Other')).items[0]
        context = Providers((provider(function(7)),), None, Path('unused'), 'majesty')
        with patch.object(context, 'lookup', side_effect=AssertionError('already reviewed')):
            output = context.reconcile(SemanticMergeResult((selected,), ()), (missing,),
                review=ScriptReviewSession(), skip_keys=(selected.key, missing.key))
        self.assertEqual(output.items, (selected,))

    def test_snapshot_loads_manifest_once_and_defers_parse_and_compilation(self):
        from majesty_cam import standard_scripts as scripts
        from majesty_cam.package import load_standard_component
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'mod.mmxml'
            manifest.write_text('<Mod id="11111111-1111-1111-1111-111111111111"><DisplayName>Sample</DisplayName>'
                '<DataConfiguration><Dataset base="Any"><Load><GPL><Target>Sample.bcd</Target>'
                '<Source>Sample.gpl</Source></GPL></Load></Dataset></DataConfiguration></Mod>')
            (root / 'Sample.gpl').write_text(function())
            (root / 'Sample.bcd').write_bytes(b'fixture')
            entry = SimpleNamespace(package_root=root, manifest_path=manifest,
                content_id='11111111-1111-1111-1111-111111111111', display_name='Sample')
            with patch.object(scripts, 'load_standard_component', wraps=load_standard_component) as load, \
                 patch('majesty_cam.compose._parse_semantic_source_file_cached') as parse, \
                 patch.object(scripts, 'definition_keys') as index, \
                 patch.object(scripts, 'verify') as verify:
                first = scripts.fingerprint((entry,))
                self.assertEqual(first, scripts.fingerprint((entry,)))
                self.assertEqual(load.call_count, 1)
                parse.assert_not_called()
                index.assert_not_called()
                verify.assert_not_called()
                (root / 'Sample.gpl').write_text(function(20))
                self.assertNotEqual(first, scripts.fingerprint((entry,)))
                self.assertEqual(load.call_count, 2)
                snapshot = scripts.read(entry)
                self.assertEqual(snapshot.compiled_payloads, (((root / 'Sample.bcd'), b'fixture'),))
                (root / 'Sample.bcd').write_bytes(b'changed compiled target')
                refreshed = scripts.read(entry)
                self.assertIsNot(snapshot, refreshed)
                self.assertNotEqual(snapshot.digests, refreshed.digests)
                self.assertEqual(refreshed.compiled_payloads[0][1], b'changed compiled target')
                index.assert_not_called()
            # Native source enumeration uses Dataset zero. An unused sibling
            # must not introduce missing-file errors or runtime definitions.
            manifest.write_text(manifest.read_text().replace('</DataConfiguration>',
                '<Dataset base="MajestyExpansion"><Load><GPL><Target>Missing.bcd</Target>'
                '</GPL></Load></Dataset></DataConfiguration>'))
            self.assertEqual(len(scripts.read(entry).loads), 1)

    def test_controller_selection_and_order_refresh_provider_identity(self):
        from majesty_cam.manager.build import BuildPlan, _require_current_plan_sources, ManagerBuildError
        from majesty_cam.manager.controller import ManagerController
        from majesty_cam.manager.catalog import CatalogEntry, CatalogKind, CatalogSource
        ids = ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222')
        entries = tuple(CatalogEntry(content_id=i, raw_content_id=i, display_name=i,
            kind=CatalogKind.STANDARD, source=CatalogSource.LOCAL_MODS, package_root=Path('.'),
            manifest_path=Path('unused.mmxml'), has_cam=False, merge_ready=False) for i in ids)
        state = SimpleNamespace(plan=BuildPlan((), (object(),), {}, {}, (), 'merge-only', (), merge_fingerprint='merge-only'),
            order=ids, catalog=SimpleNamespace(entries=entries), selections=dict.fromkeys(ids, False), standard_conflict_winners={})
        state._script_retry_fingerprint = 'merge-only'
        state._script_retry_preferences = {'stale': 'draft'}
        state._discard_stale_script_preferences = lambda: ManagerController._discard_stale_script_preferences(state)
        with patch('majesty_cam.standard_scripts.fingerprint', side_effect=lambda entries: '|'.join(e.content_id for e in entries)):
            state.selections[ids[0]] = True
            ManagerController._refresh_standard_plan(state)
            one = state.plan.fingerprint
            self.assertEqual(state._script_retry_preferences, {})
            self.assertEqual(state.plan.standard_script_entries, entries[:1])
            state.selections[ids[1]] = True
            ManagerController._refresh_standard_plan(state)
            two = state.plan.fingerprint
            self.assertNotEqual(two, one)
            state.order = tuple(reversed(ids))
            ManagerController._refresh_standard_plan(state)
            self.assertEqual(state.plan.standard_script_entries, tuple(reversed(entries)))
            self.assertNotEqual(state.plan.fingerprint, two)
            state.standard_conflict_winners = {'|'.join(ids): ids[1]}
            ManagerController._refresh_standard_plan(state)
            self.assertEqual(state.plan.standard_script_entries, entries)
            self.assertEqual(state.plan.fingerprint, two)
            state.selections = dict.fromkeys(ids, False)
            ManagerController._refresh_standard_plan(state)
            self.assertEqual(state.plan.standard_script_entries, ())
            self.assertEqual(state.plan.fingerprint, 'merge-only')
            with self.assertRaisesRegex(ManagerBuildError, 'do not match'):
                _require_current_plan_sources(replace(state.plan, selected_standard_ids=(ids[0],)), game_path=Path('.'), phase='test')

    def test_literal_else_wrapper_preserves_other_mod_edits(self):
        base = 'function Test()\nbegin\nif (A == 1) X = 1; else X = 2;\nend'
        wrapped = base.replace('if (A == 1)', 'if (B == 3) X = 3; else if (A == 1)')
        changed = base.replace('X = 2', 'X = 4')
        merged = merge_function(base, {'wrap':wrapped, 'native':changed}).lower()
        self.assertIn('b == 3', merged)
        self.assertIn('x = 4', merged)
        with self.assertRaises(FunctionMergeError):
            merge_function(base, {'wrap':wrapped, 'other':wrapped.replace('B == 3', 'C == 5')})

    def test_parameter_rename_does_not_invent_signature_conflict(self):
        stock = 'function Example(agent ThisAgent, integer Item_Cost)\nbegin\n$Charge(ThisAgent, Item_Cost);\nend'
        native = stock.replace('Item_Cost','ItemCost').replace('$Charge', '$DiscountCharge')
        generated = stock.replace('begin', 'begin\n$Observe(ThisAgent);')
        merged = self.preserve(generated, [provider(native)], stock).source_set.gpl_text.lower()
        self.assertIn('$discountcharge', merged)
        self.assertIn('$observe', merged)
    def preserve(self, generated, providers, stock):
        with patch('majesty_cam.standard_scripts.verify'):
            context = Providers(providers, lambda names: {i.key: i for i in parse_gpl(stock).items}, Path('compiler'))
            merged = context.prune(context.reconcile(SemanticMergeResult(parse_gpl(generated).items, ())))
            return replace(result(generated), source_set=merged.emit_project_source_set())

    def test_native_behavior_and_manager_hook_both_survive(self):
        merged = self.preserve(function(extra='$Observe(ThisAgent);'), [provider(function(7))], function())
        self.assertIn('7', merged.source_set.gpl_text)
        self.assertIn('observe', merged.source_set.gpl_text.lower())

    def test_source_ancestry_does_not_replace_native_dataset_fallbacks(self):
        from test_gpl_function_merge import decision, structure
        base = parse_gpl(decision(('A','B','D'))).items[0]
        sdk = parse_gpl(decision(('A','B','C','D'))).items[0]
        native = provider(decision(('A','C','B','D')))
        authored = SemanticMergeResult(parse_gpl(decision(('A','B','PrivateC','D'))).items, ())
        for scope, stock in (('majesty', base), ('majestyexpansion', sdk)):
            context = Providers((native,), lambda _: {stock.key: stock}, Path('compiler'), scope,
                                source_ancestor_loader=lambda _: {sdk.key: sdk})
            with self.subTest(scope=scope), patch('majesty_cam.standard_scripts.verify'):
                merged = context.reconcile(authored)
                self.assertEqual(structure(merged.items[0].text), structure(decision(('A','PrivateC','B','D'))))
                self.assertEqual(context.stock(('Shared',))[stock.key], stock)
                # Neither native-stock nor shared-ancestor copies undo a mod.
                for fallback in (stock, sdk):
                    self.assertEqual(context.reconcile(SemanticMergeResult((fallback,), ())).items[0].text,
                                     native.items[stock.key].text)

    def test_stock_dependency_cannot_restore_stock_over_native(self):
        merged = self.preserve(function(), [provider(function(7))], function())
        self.assertEqual(merged.source_set.gpl_text.strip(), '')

    def test_unrelated_native_script_is_not_emitted(self):
        merged = self.preserve(function(), [provider(function(7).replace('Example', 'Unrelated'))], function())
        self.assertNotIn('Unrelated', merged.source_set.gpl_text)

    def test_last_native_provider_wins_before_manager_patch(self):
        merged = self.preserve(function(extra='$Observe(ThisAgent);'),
                              [provider(function(7), 'First'), provider(function(8), 'Last')], function())
        self.assertIn('8', merged.source_set.gpl_text)
        self.assertNotIn('7', merged.source_set.gpl_text)

    def test_competing_gameplay_edit_names_mod_and_function(self):
        with self.assertRaisesRegex(ValueError, 'Native.*function:Example'):
            self.preserve(function(9), [provider(function(7))], function())

    def test_dataset_scope_is_preserved(self):
        source = provider(function())
        block = SimpleNamespace(sources=(Path('example.gpl'),))
        source = replace(source, loads=(block,), bases=('majestyexpansion',))
        self.assertEqual(for_dataset([source], 'majesty'), ())
        self.assertEqual(len(for_dataset([source], 'majestyexpansion')), 1)

    def test_unproven_dataset_output_fails_closed(self):
        native = replace(provider(function(7)), bases=('majestyexpansion',))
        with self.assertRaisesRegex(ValueError, 'Example|example'):
            self.preserve(function(), [native], function())

    def test_unrelated_scoped_provider_does_not_block_output(self):
        native = replace(provider(function(7).replace('Example', 'Other')), bases=('majestyexpansion',))
        with patch('majesty_cam.standard_scripts.verify') as verify:
            context = Providers((native,), lambda names: {}, Path('compiler'))
            context.reconcile(SemanticMergeResult(parse_gpl(function()).items, ()))
            verify.assert_not_called()

    def test_expansion_copy_is_not_assumed_to_exist_in_base(self):
        native = replace(provider(function()), bases=('majestyexpansion',))
        with self.assertRaisesRegex(ValueError, 'scoped output'):
            self.preserve(function(extra='$Observe(ThisAgent);'), [native], function())

    def test_opaque_provider_only_blocks_when_a_definition_needs_evidence(self):
        native = replace(provider(''), loads=(SimpleNamespace(sources=()),))
        context = Providers((native,), lambda names: {}, Path('compiler'))
        self.assertEqual(context.reconcile(SemanticMergeResult((), ())).items, ())
        with self.assertRaisesRegex(ValueError, 'cannot determine.*function:example'):
            context.lookup((DefinitionKind.FUNCTION, 'example'))

    def test_later_known_winner_does_not_need_earlier_opaque_source(self):
        opaque = replace(provider(''), loads=(SimpleNamespace(sources=()),))
        context = Providers((opaque, provider(function(), 'Last')), lambda names: {}, Path('compiler'))
        with patch('majesty_cam.standard_scripts.verify') as verify:
            self.assertEqual(context.lookup((DefinitionKind.FUNCTION, 'example')).text, function())
            self.assertEqual(verify.call_count, 1)

    def test_source_proof_failure_blocks_native_reconciliation(self):
        context = Providers((provider(function()),), lambda names: {}, Path('compiler'))
        with patch('majesty_cam.standard_scripts.verify', side_effect=ValueError('source does not match bytecode')):
            with self.assertRaisesRegex(ValueError, 'does not match bytecode'):
                context.reconcile(SemanticMergeResult(parse_gpl(function()).items, ()))

    def test_private_standard_participant_is_validated_and_hooked_in_pipeline(self):
        from test_private_hero_gpl import tree, CALLBACKS
        from majesty_cam.gpl_features import StockHeroQuestParticipant, StockHeroQuestLifecycle
        from majesty_cam.package import ModDefinition
        from majesty_cam.standard_scripts import participant_inventories
        from majesty_cam.compose import merge_gpl_resources, PackageInventory, SelectedMod
        callbacks = parse_gpl(CALLBACKS, 'quest provider')
        lifecycle = StockHeroQuestLifecycle('quest', ('mx_healer',), 'Resume', 'Consider', 'Reset', 'Death')
        quest_id = '11111111-1111-1111-1111-111111111111'
        native_id = '22222222-2222-2222-2222-222222222222'
        definition = ModDefinition(3, quest_id, 'quest', 'Quest provider', (), runtime_features=(lifecycle,))
        quest_package = SimpleNamespace(definition=definition, mod_id=quest_id, display_name='Quest provider')
        inventory = PackageInventory(SelectedMod('quest', quest_package), (), (), (), (), semantic_sources=(callbacks,))
        # participant_inventories only needs immutable package/definition fields.
        from majesty_cam.package import ModPackage, ModMetadata, LocalizedText
        package = ModPackage(Path('.'), Path('native.mmxml'),
            ModMetadata(native_id, (LocalizedText(None, 'Native'),), (), (), ()),
            replace(definition, mod_id=native_id, runtime_features=()))
        native = replace(provider(tree('Private_Healer', True).text), package=package,
            participants=(StockHeroQuestParticipant('private', 'Private_Healer', 'mx_healer'),))
        shadow = self.compiled_provider(((DefinitionKind.FUNCTION, 'Private_Healer'),))
        with self.assertRaisesRegex(ValueError, 'supplies function:private_healer'):
            participant_inventories((native, shadow))
        unrelated = self.compiled_provider(((DefinitionKind.FUNCTION, 'Other'),))
        self.assertEqual(len(participant_inventories((native, unrelated))), 1)
        context = Providers((native,), lambda names: {}, Path('compiler'))
        with patch('majesty_cam.standard_scripts.verify'):
            merged = merge_gpl_resources((inventory, *participant_inventories((native,))),
                standard_providers=context, stock_hero_trees={'mx_healer': tree('Healer_tree', True).items[0]})
        text = next(i.text for i in parse_gpl(merged.source_set.gpl_text).items if i.name == 'Private_Healer')
        self.assertIn('$Private_Hiring_Guard', text)
        self.assertLess(text.index('$Resume'), text.index('$Check_rewards'))
        self.assertLess(text.index('$Purchase_Bazaar'), text.index('$Consider'))

    def test_native_inputs_are_present_before_discovery_and_dependency_checks(self):
        from majesty_cam.compose import merge_gpl_resources
        generated = function(extra='$Observe(ThisAgent);')
        inventory = SimpleNamespace(selected=SimpleNamespace(alias='merge', semantic_passthrough=False,
            package=SimpleNamespace(definition=SimpleNamespace(runtime_features=()))),
            semantic_sources=(parse_gpl(generated),), gpl_loads=())
        context = Providers((provider(function(7)),), lambda names: {i.key:i for i in parse_gpl(function()).items}, Path('compiler'))
        seen = []
        def discover(value, *args):
            seen.append(value.render())
            return value
        with patch('majesty_cam.standard_scripts.verify'), patch('majesty_cam.compose.validate_gpl_feature_evidence', return_value=()), \
             patch('majesty_cam.spell_policy.compose_guards', side_effect=discover):
            merged = merge_gpl_resources((inventory,), standard_providers=context,
                                         dataset_dependency_resolver=discover)
        self.assertEqual(len(seen), 2)
        self.assertTrue(all('7' in text and 'observe' in text.lower() for text in seen))
        self.assertIn('7', merged.source_set.gpl_text)

    def test_filename_proof_cannot_mask_changed_code_or_strings(self):
        def envelope(body):
            data = bytearray(24) + body
            for offset in (0, 4, 16):
                struct.pack_into('<I', data, offset, len(data) - 4)
            return bytes(data)
        exact = envelope(b'code\0Source0.gpl\0literal\0')
        probe = envelope(b'code\0ProbeX0.gpl\0literal\0')
        runtime = envelope(b'code\0C:\\Author\\GPL\\Original.gpl\0literal\0')
        names = {b'Source0.gpl': 'GPL/Original.gpl'}
        self.assertTrue(_matches_source_locations(runtime, exact, probe, names))
        self.assertFalse(_matches_source_locations(runtime.replace(b'code', b'evil'), exact, probe, names))
        self.assertFalse(_matches_source_locations(runtime.replace(b'literal', b'altered'), exact, probe, names))
        self.assertFalse(_matches_source_locations(runtime, exact, exact, names))

    def test_installed_standard_potions_keep_native_forms_with_generic_policy(self):
        from majesty_cam.standard_scripts import read
        from majesty_cam.potion_policy import Plan, Action, POTIONS, parse_feature
        from majesty_cam.private_phantom_policy import POLICY
        from majesty_cam.stock_gpl import load_stock_function_ancestors
        from majesty_cam.compose import compile_gpl, prepare_final_gpl_resources, prepare_gpl_bundle, ComposeError
        from tempfile import TemporaryDirectory
        root = Path('C:/Program Files (x86)/Steam/steamapps/workshop/content/73230/3743606613')
        game = Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')
        if not (root/'Monster Kingdom.mmxml').is_file() or not (game/'SDK/Gplbcc.exe').is_file():
            self.skipTest('requires installed source fixture')
        native = read(SimpleNamespace(package_root=root, manifest_path=root/'Monster Kingdom.mmxml',
                      content_id='BFA127E5-3AE4-47BF-BEE0-BDC27BAEE50C', display_name='Native source fixture'))
        actions = tuple(Action(k,name,name+'_Effect','','P00'+str(n)) for n,(k,(_,name)) in enumerate(POTIONS.items()))
        plan = Plan((parse_feature(POLICY),),actions)
        with self.assertRaisesRegex(ComposeError, 'scoped output'):
            prepare_final_gpl_resources(game, (), potion_plan=plan, standard_script_inputs=(native,))
        merged = prepare_final_gpl_resources(game, (), potion_plan=plan,
                    standard_script_inputs=(native,), script_dataset='majestyexpansion')
        items = {i.normalized_name:i.text.lower() for i in parse_gpl(merged.source_set.gpl_text).items}
        for name in ('shapeshift_potion_effect','shapeshift_potion_end'):
            self.assertIn('mk_goblin_priest', items[name])
            self.assertIn('phantom', items[name])
        with TemporaryDirectory() as temp:
            compile_gpl(merged.source_set, game/'SDK/Gplbcc.exe', Path(temp)/'fixture')
            bundle = prepare_gpl_bundle(game, (), potion_plan=plan, standard_script_inputs=(native,))
            patches = dict(bundle.patches)
            self.assertIn('MajestyExpansion', patches)
            common = bundle.common.source_set.gpl_text.lower()
            self.assertNotIn('mk_goblin_priest', common)
            self.assertNotIn('mk_goblin_priest', patches.get('Majesty', result('')).source_set.gpl_text.lower())
            self.assertIn('mk_goblin_priest', patches['MajestyExpansion'].source_set.gpl_text.lower())
            for scope, output in bundle.outputs:
                if output.source_set.files:
                    compile_gpl(output.source_set, game/'SDK/Gplbcc.exe', Path(temp)/scope)

    def test_installed_native_hero_trees_keep_quest_callbacks_in_both_scopes(self):
        from majesty_cam.compose import PackageInventory, SelectedMod, prepare_gpl_bundle, compile_gpl
        from majesty_cam.standard_scripts import read
        from majesty_cam.gpl_features import StockHeroQuestLifecycle
        from majesty_cam.package import ModDefinition
        from test_private_hero_gpl import CALLBACKS
        game = Path('C:/Program Files (x86)/Steam/steamapps/common/Majesty HD')
        root = Path('C:/Program Files (x86)/Steam/steamapps/workshop/content/73230/3743606613')
        if not (root/'Monster Kingdom.mmxml').is_file() or not (game/'SDK/Gplbcc.exe').is_file():
            self.skipTest('requires installed source fixture')
        native = read(SimpleNamespace(package_root=root, manifest_path=root/'Monster Kingdom.mmxml',
                      content_id='BFA127E5-3AE4-47BF-BEE0-BDC27BAEE50C', display_name='Native source fixture'))
        lifecycle = StockHeroQuestLifecycle('quests', ('mx_healer', 'mx_adept', 'mx_monk'), 'Resume', 'Consider', 'Reset', 'Death')
        definition = ModDefinition(3, '11111111-1111-1111-1111-111111111111', 'Quest', 'Quest', (), runtime_features=(lifecycle,))
        package = SimpleNamespace(definition=definition, mod_id=definition.mod_id, display_name='Quest')
        callbacks = parse_gpl(CALLBACKS[:CALLBACKS.index('function reset_tasks')].replace('\nbegin', '\ndeclare\nbegin'))
        inventory = PackageInventory(SelectedMod('quest', package), (), (), (), (), semantic_sources=(callbacks,))
        bundle = prepare_gpl_bundle(game, (inventory,), standard_script_inputs=(native,))
        for scope in ('Majesty', 'MajestyExpansion'):
            outputs = (bundle.common, *(r for s, r in bundle.patches if s == scope))
            items = {i.normalized_name:i.text.lower() for r in outputs for i in parse_gpl(r.source_set.gpl_text).items}
            for tree_name in ('healer_tree', 'adept_tree', 'monk_tree'):
                self.assertIn('$resume', items[tree_name])
                self.assertIn('$consider', items[tree_name])
            self.assertIn('$reset', items['reset_tasks'])
            self.assertIn('$death', items['unit_call_deathscript'])
            if scope == 'Majesty':
                self.assertNotIn('$deletealleffectors', items['unit_call_deathscript'])
                self.assertNotIn('$stopmoving', items['reset_tasks'])
            else:
                self.assertIn('mk_deathstep', items['unit_call_deathscript'])
        with TemporaryDirectory() as temp:
            for scope, output in bundle.outputs:
                if output.source_set.files:
                    compile_gpl(output.source_set, game/'SDK/Gplbcc.exe', Path(temp)/scope)

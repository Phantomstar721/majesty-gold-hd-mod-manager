"""Event scan and composition use selected helpers from one source snapshot."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from majesty_cam.compose import (
    ComposeError, GplComposeResult, prepare_final_gpl_resources, prepare_gpl_bundle,
    validate_gpl_feature_evidence,
)
from majesty_cam.dataset_dependencies import DatasetSymbols, DestinationSources
from majesty_cam.gameplay_events import add_gameplay_event_observers
from majesty_cam.gpl import DefinitionKind, SemanticMergeResult, parse_gpl
from majesty_cam.potion_policy import Plan
from majesty_cam.shared_features import StockGameplayEventObserver
from majesty_cam.standard_scripts import StandardScripts


FEATURE = StockGameplayEventObserver("reward", "reward-flag-paid", "Observe")
STOCK_SOURCE = '''function explore_flag_poll(agent ThisAgent)
declare list heroes_near;
begin
    heroes_near = $List_Heroes_Near_Flag(ThisAgent);
    if ($ListSize(heroes_near) > 0)
        begin
            $playsound(ThisAgent, "completed_reward", "begin");
            $dropgoldinradius_sameplayer(ThisAgent, $GetAttribute(ThisAgent, #ATTRIB_RewardCost));
            $deletegamepiece(ThisAgent);
        end
end
function attack_flag_poll(agent ThisAgent)
declare agent target;
begin
    if ($isvalidgamepiece(thisagent) == FALSE) return;
    if (ThisAgent's "gavereward" != TRUE)
        begin
            target = $agentnumber($GetAttribute(ThisAgent, #ATTRIB_TargetID));
            if ($isdead(target))
                begin
                    $playsound(ThisAgent, "completed_reward", "begin");
                    ThisAgent's "gavereward" = TRUE;
                    $dropgoldinradius(ThisAgent, $GetAttribute(ThisAgent, #ATTRIB_RewardCost));
                    $deletegamepiece(ThisAgent);
                    return;
                end
        end
end
function attack_flag_death_callback(agent ThisAgent)
declare agent target;
begin
    if (ThisAgent's "gavereward" != TRUE)
        begin
            target = $agentnumber($GetAttribute(ThisAgent, #ATTRIB_TargetID));
            if ($isdead(target))
                begin
                    $playsound(ThisAgent, "completed_reward", "begin");
                    $dropgoldinradius(ThisAgent, $GetAttribute(ThisAgent, #ATTRIB_RewardCost));
                    ThisAgent's "gavereward" = TRUE;
                    $check_revert_teams(ThisAgent);
                    return;
                end
        end
end
function dropgoldinradius(agent ThisAgent, integer Amount)
declare begin $give_gold(ThisAgent, Amount); end
function dropgoldinradius_sameplayer(agent ThisAgent, integer Amount)
declare begin $give_gold(ThisAgent, Amount); end
function give_gold(agent ThisAgent, integer Amount)
declare begin end
'''
STOCK = {item.normalized_name: item for item in parse_gpl(STOCK_SOURCE).items}
CALLBACK = 'function Observe(agent Flag, agent Recipient, integer Amount) declare begin end\n'
HELPER = 'function PrivatePayout(agent Flag, integer Amount) declare begin $give_gold(Flag, Amount); end\n'


def inventory(text, *, index=1, features=(FEATURE,)):
    return SimpleNamespace(
        semantic_sources=(parse_gpl(text, "package-" + str(index)),), gpl_loads=(),
        selected=SimpleNamespace(alias="package-" + str(index), semantic_passthrough=False,
            package=SimpleNamespace(mod_id=f"12345678-1234-1234-1234-{index:012d}",
                definition=SimpleNamespace(runtime_features=features))))


class EventEvidenceSnapshotTests(unittest.TestCase):
    def check(self, inventories, *, stock=None, capture=None):
        empty_symbols = SimpleNamespace(expansion_functions=frozenset())
        def observe(*args, **kwargs):
            result = add_gameplay_event_observers(*args, **kwargs)
            if capture is not None:
                capture.append(result)
            return result
        with patch('majesty_cam.compose._load_stock_gameplay_event_items', return_value=stock or STOCK), \
             patch('majesty_cam.dataset_dependencies.load_dataset_symbols', return_value=empty_symbols), \
             patch('majesty_cam.compose.add_gameplay_event_observers', side_effect=observe):
            return validate_gpl_feature_evidence(inventories, game_path=Path('snapshot-fixture'))

    def authored(self):
        return STOCK['attack_flag_poll'].text.replace('$dropgoldinradius', '$PrivatePayout') + CALLBACK + HELPER

    def test_scan_retains_migrated_package_helper_without_merging_unrelated_conflict(self):
        first = inventory(self.authored() + 'function Unrelated() declare begin $First(); end')
        second = inventory('function Unrelated() declare begin $Second(); end', index=2, features=())
        observed = []
        self.check((first, second), capture=observed)
        output = {item.normalized_name: item.text for item in observed[0].items}
        self.assertIn('$MM_Event_AttackGold', output['attack_flag_poll'])
        self.assertTrue(any('privatepayout' not in name and name.startswith('mm_eg_')
                            and '$MM_Event_RewardPaid' in text for name, text in output.items()))
        self.assertNotIn('unrelated', output)

    def test_required_helper_conflict_is_not_hidden_by_stock_or_another_package(self):
        first = inventory(self.authored())
        second = inventory(HELPER.replace('Flag, Amount);', 'Flag, Amount + 1);'), index=2, features=())
        with self.assertRaisesRegex(ComposeError, 'PrivatePayout'):
            self.check((first, second))

    def test_package_helper_wins_over_same_named_stock_helper(self):
        package = inventory(self.authored())
        stock = dict(STOCK)
        stock['privatepayout'] = parse_gpl(HELPER.replace('Flag, Amount);', 'Flag, Amount + 8);')).items[0]
        observed = []
        self.check((package,), stock=stock, capture=observed)
        text = '\n'.join(item.text for item in observed[0].items)
        self.assertNotIn('Amount + 8', text)
        self.assertIn('$MM_Event_RewardPaid(MM_SourceContext, Flag, Amount)', text)

    def test_generated_clone_collision_in_helper_snapshot_is_detected(self):
        import hashlib
        generated = 'MM_EG_' + hashlib.sha256(b'privatepayout').hexdigest()[:24]
        package = inventory(self.authored() + f'function {generated}() declare begin end')
        with self.assertRaisesRegex(ComposeError, 'generated symbol collision'):
            self.check((package,))


class AnyEventSourceLookupTests(unittest.TestCase):
    def test_any_reuses_dataset_snapshot_and_selected_provider_precedence(self):
        stock_item = parse_gpl('function Award(agent Source) declare begin $Stock(); end').items[0]
        native_item = parse_gpl('function Award(agent Source) declare begin $Selected(); end').items[0]
        stock_loader = Mock(return_value=stock_item)
        symbols = SimpleNamespace(expansion_functions=frozenset(('award',)), base_functions=frozenset(('award',)),
                                  function_loader=stock_loader, base_function_loader=Mock(return_value=stock_item))
        native = StandardScripts('Selected', SimpleNamespace(mod_id='selected', root=Path('.')), (),
                                 (parse_gpl(native_item.text),), (), ())
        sentinel = object()
        def composed(*args, **kwargs):
            fallback = kwargs['stock_function_loader']
            key = (DefinitionKind.FUNCTION, 'award')
            self.assertEqual(fallback(('Award',))[key], stock_item)
            self.assertEqual(fallback(('award', 'NativeIntrinsic'))[key], stock_item)
            self.assertEqual(fallback(('OtherIntrinsic',)), {})
            providers = kwargs['standard_providers']
            self.assertEqual(providers.functions(('award',))[key].text, native_item.text)
            self.assertEqual(providers.functions(('NativeIntrinsic',)), {})
            return sentinel
        with patch('majesty_cam.dataset_dependencies.load_dataset_symbols', return_value=symbols) as snapshot, \
             patch('majesty_cam.compose.load_stock_function_ancestors',
                   side_effect=AssertionError('must not rescan SDK for individual helpers')), \
             patch('majesty_cam.standard_scripts.verify'), \
             patch('majesty_cam.compose.merge_gpl_resources', side_effect=composed):
            actual = prepare_final_gpl_resources(Path('snapshot-fixture'), (), potion_plan=Plan(),
                                                standard_script_inputs=(native,), script_dataset='any')
        self.assertIs(actual, sentinel)
        snapshot.assert_called_once()
        symbols.base_function_loader.assert_called_once_with('award')
        stock_loader.assert_called_once_with('award')


class DestinationSourceTests(unittest.TestCase):
    def sources(self):
        base = parse_gpl('function Award(agent Source) declare begin $Base(); end').items[0]
        expansion = parse_gpl('function Award(agent Source) declare begin $Expansion(); end').items[0]
        extra = parse_gpl('function Extra() declare begin end').items[0]
        expansion_loader = Mock(side_effect={'award': expansion, 'extra': extra}.__getitem__)
        base_loader = Mock(return_value=base)
        return (DatasetSymbols(frozenset(), {}, frozenset(('award',)), frozenset(('award', 'extra')),
                               expansion_loader, base_loader), base, expansion, extra)

    def test_destination_source_and_authored_ancestry_are_distinct_cached_operations(self):
        stock, base, expansion, _ = self.sources()
        view = DestinationSources(stock, 'majesty')
        self.assertEqual(view.function('Award'), base)
        self.assertEqual(view.functions(('AWARD', 'Intrinsic')), {base.key: base})
        self.assertEqual(view.ancestors(('Award', 'Intrinsic')), {base.key: expansion})
        self.assertEqual(view.ancestors(('AWARD',)), {base.key: expansion})
        stock.base_function_loader.assert_called_once_with('award')
        stock.function_loader.assert_called_once_with('award')

    def test_base_absent_compatibility_import_is_explicit(self):
        stock, base, _, extra = self.sources()
        view = DestinationSources(stock, 'majesty')
        self.assertIsNone(view.function('Extra'))
        stock.function_loader.assert_not_called()
        self.assertEqual(view.function('Extra', allow_expansion=True), extra)
        self.assertEqual(view.function('Award', allow_expansion=True), base)
        stock.function_loader.assert_called_once_with('extra')

    def test_any_cannot_replace_different_native_bodies(self):
        stock, _, expansion, _ = self.sources()
        view = DestinationSources(stock, 'any')
        self.assertEqual(view.ancestors(('award',)), {expansion.key: expansion})
        with self.assertRaisesRegex(ValueError, 'scoped output is required'):
            view.function('award')
        self.assertEqual(DestinationSources(stock, 'majestyexpansion').function('award'), expansion)

    def test_invalid_stock_loader_does_not_become_a_missing_intrinsic(self):
        stock, _, _, _ = self.sources()
        stock.base_function_loader.return_value = None
        with self.assertRaisesRegex(ValueError, 'different function for award'):
            DestinationSources(stock, 'majesty').function('award')

    def test_generated_stock_functions_are_partitioned_without_standard_inputs(self):
        stock, base, expansion, _ = self.sources()
        seen = []
        def prepared(_game, _inventories, **kwargs):
            self.assertIs(kwargs['dataset_symbols'], stock)
            view = DestinationSources(stock, kwargs['script_dataset'])
            selected = view.function('award')
            seen.append(selected)
            result = SemanticMergeResult((selected,), ()).emit_project_source_set()
            return GplComposeResult(result, (), (), (), ())
        with patch('majesty_cam.dataset_dependencies.load_dataset_symbols', return_value=stock) as snapshot, \
             patch('majesty_cam.compose.prepare_final_gpl_resources', side_effect=prepared):
            bundle = prepare_gpl_bundle(Path('snapshot-fixture'), (inventory(CALLBACK),))
        snapshot.assert_called_once()
        self.assertEqual(seen, [base, expansion])
        self.assertFalse(bundle.common.source_set.files)
        self.assertEqual([scope for scope, _ in bundle.patches], ['Majesty', 'MajestyExpansion'])


if __name__ == '__main__':
    unittest.main()

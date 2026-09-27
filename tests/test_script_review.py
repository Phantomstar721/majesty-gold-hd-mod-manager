from dataclasses import replace
import unittest
from unittest.mock import patch

from majesty_cam.gpl import parse_gpl, parse_dat
from majesty_cam.gpl_function_merge import FunctionMergeError, _Parser, merge_function
from majesty_cam.script_review import (
    ScriptCandidate, ScriptConflict, ScriptReviewRequired, ScriptReviewSession,
    group_conflicts, pair_key, validate_preferences,
)


def function(value=1, parameter='unit', kind='agent', name='Example'):
    return f'function {name}({kind} {parameter}) is integer\nbegin\nreturn {value};\nend\n'


def conflict(dataset='majesty', name='Example', owners=('first-id', 'second-id')):
    base = parse_gpl(function(name=name), 'Stock.gpl').items[0]
    return ScriptConflict(dataset, base.key, base.name, 'different return values', base, tuple(
        ScriptCandidate(owner.replace('-id', '').title(),
                        parse_gpl(function(index + 2, name=name), owner + '.gpl').items[0], owner)
        for index, owner in enumerate(owners)))


def choose(entry, winner=0):
    return {pair.identity: entry.candidates[winner].owner for pair in group_conflicts((entry,))}


class ScriptReviewTests(unittest.TestCase):
    def test_identity_is_stable_and_bound_to_exact_source_inputs_and_dataset(self):
        original = conflict()
        self.assertEqual(original.identity, conflict().identity)
        self.assertEqual(original.identity, replace(original, detail='different presentation').identity)
        self.assertNotEqual(original.identity, conflict('majestyexpansion').identity)
        self.assertNotEqual(original.identity, replace(original, base=None).identity)
        candidate = original.candidates[0]
        for change in ({'text': function(9)}, {'source_name': 'Moved.gpl'}, {'name': 'EXAMPLE'}):
            changed = replace(candidate, item=replace(candidate.item, **change))
            self.assertNotEqual(original.identity,
                replace(original, candidates=(changed, original.candidates[1])).identity)
        self.assertNotEqual(original.identity, replace(original, candidates=(
            replace(candidate, owner='different-owner'), original.candidates[1])).identity)

    def test_pair_identity_uses_real_owners_not_display_names_or_delimiters(self):
        original = conflict()
        renamed = replace(original, candidates=tuple(replace(item, label='Same name')
                                                    for item in original.candidates))
        self.assertEqual(group_conflicts((original,))[0].identity,
                         group_conflicts((renamed,))[0].identity)
        self.assertEqual(pair_key('a', 'b'), pair_key('b', 'a'))
        self.assertNotEqual(pair_key('a|b', 'c'), pair_key('a', 'b|c'))
        self.assertNotEqual(pair_key('a"b', 'c'), pair_key('a', 'b"c'))
        for owners in (('a', 'a'), ('', 'b'), ('a', 4)):
            with self.subTest(owners=owners), self.assertRaises(ValueError):
                pair_key(*owners)

    def test_candidate_owner_defaults_to_label_only_for_unidentified_fixtures(self):
        item = conflict().candidates[0].item
        self.assertEqual(ScriptCandidate('Legacy fixture', item).owner, 'Legacy fixture')
        with self.assertRaises(ValueError):
            ScriptCandidate('', item)
        with self.assertRaises(ValueError):
            ScriptCandidate('Label', item, 0)

    def test_one_pair_choice_covers_every_function_and_dataset(self):
        entries = (conflict(), conflict('majestyexpansion'),
                   conflict(name='SecondFunction'), conflict('majestyexpansion', name='SecondFunction'))
        grouped = group_conflicts((*entries, entries[0]))
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0].conflicts, entries)
        session = ScriptReviewSession()
        for entry in entries:
            self.assertIsNone(session.resolve(entry))
        self.assertEqual(session.observed, entries)
        with self.assertRaises(ScriptReviewRequired) as raised:
            session.require_resolved()
        self.assertEqual(raised.exception.pairs, grouped)
        session.apply({grouped[0].identity: 'second-id'})
        self.assertEqual(session.unresolved, ())
        session.require_resolved()
        for entry in entries:
            self.assertIs(session.resolve(entry), entry.candidates[1].item)
            self.assertEqual(session.winner(entry), 'second-id')

    def test_session_has_no_default_and_rejects_incomplete_or_unknown_choices_atomically(self):
        entries = (conflict(), conflict(name='Other', owners=('third', 'fourth')))
        session = ScriptReviewSession()
        for entry in entries:
            session.resolve(entry)
        for choices in ({}, choose(entries[0]),
                        {**choose(entries[0]), **choose(entries[1]), pair_key('extra', 'pair'): 'extra'}):
            with self.subTest(choices=choices), self.assertRaises(ValueError):
                session.apply(choices)
            self.assertEqual(session.decisions, {})
        session.apply({**choose(entries[0]), **choose(entries[1])})
        session.require_resolved()

    def test_three_mods_require_all_differing_pairs_and_select_one_complete_definition(self):
        entry = conflict(owners=('a', 'b', 'c'))
        session = ScriptReviewSession()
        session.resolve(entry)
        with self.assertRaisesRegex(ValueError, 'every conflicting pair'):
            session.apply({pair_key('a', 'b'): 'a', pair_key('a', 'c'): 'a'})
        session.apply({pair_key('a', 'b'): 'a', pair_key('a', 'c'): 'a', pair_key('b', 'c'): 'c'})
        self.assertIs(session.resolve(entry), entry.candidates[0].item)

    def test_only_incompatible_pair_is_prompted_and_safe_third_mod_edit_survives(self):
        stock = ('function Example(agent unit) is integer\ndeclare\ninteger x,y;\n'
                 'begin\nx=1;\ny=1;\nreturn x+y;\nend\n')
        base = parse_gpl(stock).items[0]
        variants = {'a': stock.replace('x=1;', 'x=2;'),
                    'b': stock.replace('y=1;', 'y=2;'),
                    'native': stock.replace('x=1;', 'x=3;')}
        entry = ScriptConflict('majesty', base.key, base.name, 'different x', base, tuple(
            ScriptCandidate(owner, parse_gpl(text).items[0], owner)
            for owner, text in variants.items()))
        with patch('majesty_cam.script_review.merge_function', wraps=merge_function) as merger:
            self.assertEqual([pair.identity for pair in group_conflicts((entry,))],
                             [pair_key('a', 'native')])
            analyzed = merger.call_count
            group_conflicts((entry,))
            self.assertEqual(merger.call_count, analyzed)
        session = ScriptReviewSession()
        self.assertIsNone(session.resolve(entry))
        session.apply({pair_key('a', 'native'): 'native'})
        expected = stock.replace('x=1;', 'x=3;').replace('y=1;', 'y=2;')
        self.assertEqual(_Parser(session.resolve(entry).text).function(), _Parser(expected).function())
        self.assertEqual(session.selected_owners(entry), ('b', 'native'))
        self.assertIsNone(session.winner(entry))

    def test_safe_remaining_edits_can_align_existing_bound_parameter_names(self):
        stock = ('function Example(agent unit) is integer\ndeclare\ninteger x,y;\n'
                 'begin\nx=1;\ny=1;\nreturn x+y;\nend\n')
        base = parse_gpl(stock).items[0]
        entry = ScriptConflict('majesty', base.key, base.name, 'supplied conflict', base, (
            ScriptCandidate('A', parse_gpl(stock.replace('x=1;', 'x=2;')).items[0]),
            ScriptCandidate('B', parse_gpl(stock.replace('y=1;', 'y=2;').replace('unit', 'hero')).items[0])))
        session = ScriptReviewSession()
        self.assertEqual(group_conflicts((entry,)), ())
        result = session.resolve(entry)
        self.assertEqual(_Parser(result.text).function(),
                         _Parser(stock.replace('x=1;', 'x=2;').replace('y=1;', 'y=2;')).function())

    def test_displaced_mod_does_not_suppress_another_compatible_mod(self):
        stock = ('function Example(agent unit) is integer\ndeclare\ninteger x,y;\n'
                 'begin\nx=1;\ny=1;\nreturn x+y;\nend\n')
        base = parse_gpl(stock).items[0]
        variants = {'a': stock.replace('x=1;', 'x=3;'),
                    'b': stock.replace('x=1;', 'x=2;').replace('y=1;', 'y=2;'),
                    'c': stock.replace('y=1;', 'y=3;')}
        entry = ScriptConflict('majesty', base.key, base.name, 'overlapping assignments', base, tuple(
            ScriptCandidate(owner, parse_gpl(text).items[0], owner)
            for owner, text in variants.items()))
        session = ScriptReviewSession()
        self.assertIsNone(session.resolve(entry))
        session.apply({pair_key('a', 'b'): 'a', pair_key('b', 'c'): 'b'})
        expected = stock.replace('x=1;', 'x=3;').replace('y=1;', 'y=3;')
        self.assertEqual(session.selected_owners(entry), ('a', 'c'))
        self.assertEqual(_Parser(session.resolve(entry).text).function(), _Parser(expected).function())

    def test_higher_order_conflict_falls_back_to_explicit_whole_definition_priority(self):
        entry = conflict(owners=('a', 'b', 'c'))

        def only_pairs_combine(base, variants, **kwargs):
            if len(variants) > 2:
                raise FunctionMergeError('higher-order overlap')
            return next(iter(variants.values()))

        with patch('majesty_cam.script_review.merge_function', side_effect=only_pairs_combine):
            self.assertEqual(len(group_conflicts((entry,))), 3)
            self.assertTrue(entry.whole_definition_priority)
            session = ScriptReviewSession()
            self.assertIsNone(session.resolve(entry))
            session.apply({pair_key('a', 'b'): 'a', pair_key('a', 'c'): 'a', pair_key('b', 'c'): 'b'})
            self.assertIs(session.resolve(entry), entry.candidates[0].item)

    def test_review_merge_does_not_assume_native_query_helpers_are_unmodified(self):
        entry = conflict()

        def need_builtin_proof(base, variants, *, function_lookup):
            function_lookup('haswaypoints')
            return next(iter(variants.values()))

        with patch('majesty_cam.script_review.merge_function', side_effect=need_builtin_proof):
            self.assertEqual(len(group_conflicts((entry,))), 1)
            session = ScriptReviewSession()
            self.assertIsNone(session.resolve(entry))
            session.apply(choose(entry))
            self.assertIs(session.resolve(entry), entry.candidates[0].item)

    def test_cycles_are_rejected_across_separate_functions_not_just_one_conflict(self):
        entries = (conflict(name='First', owners=('a', 'b')),
                   conflict(name='Second', owners=('b', 'c')),
                   conflict('majestyexpansion', 'Third', ('a', 'c')))
        session = ScriptReviewSession()
        for entry in entries:
            session.resolve(entry)
        cycle = {pair_key('a', 'b'): 'a', pair_key('b', 'c'): 'b', pair_key('a', 'c'): 'c'}
        with self.assertRaisesRegex(ValueError, 'contradict'):
            session.apply(cycle)
        self.assertEqual(session.decisions, {})
        with self.assertRaisesRegex(ValueError, 'contradict'):
            ScriptReviewSession(cycle)

    def test_long_saved_preference_chain_does_not_use_recursive_cycle_detection(self):
        chain = {pair_key(str(index), str(index + 1)): str(index)
                 for index in range(4095)}
        self.assertEqual(validate_preferences(chain), chain)
        with self.assertRaisesRegex(ValueError, 'contradict'):
            validate_preferences({**chain, pair_key('0', '4095'): '4095'})

    def test_identical_instructions_do_not_require_a_player_choice(self):
        original = conflict()
        repeated = replace(original.candidates[1], item=replace(original.candidates[0].item,
                            text='// only presentation differs\n' + original.candidates[0].item.text))
        entry = replace(original, candidates=(original.candidates[0], repeated))
        self.assertEqual(group_conflicts((entry,)), ())
        session = ScriptReviewSession()
        self.assertEqual(session.resolve(entry).text, original.candidates[0].item.text)
        self.assertEqual(session.unresolved, ())
        session.require_resolved()

    def test_equal_versions_with_a_third_mod_use_only_differing_pairs(self):
        entry = conflict(owners=('a', 'b', 'c'))
        entry = replace(entry, candidates=(entry.candidates[0],
            replace(entry.candidates[1], item=entry.candidates[0].item), entry.candidates[2]))
        self.assertEqual({pair.identity for pair in group_conflicts((entry,))},
                         {pair_key('a', 'c'), pair_key('b', 'c')})
        session = ScriptReviewSession()
        session.resolve(entry)
        session.apply({pair_key('a', 'c'): 'a', pair_key('b', 'c'): 'b'})
        self.assertIs(session.resolve(entry), entry.candidates[0].item)

    def test_preloaded_preferences_are_copied_and_can_be_revised_as_full_pair_mapping(self):
        entry = conflict()
        choices = choose(entry)
        session = ScriptReviewSession(choices)
        choices.clear()
        self.assertIs(session.resolve(entry), entry.candidates[0].item)
        session.apply(choose(entry, 1))
        self.assertIs(session.resolve(entry), entry.candidates[1].item)
        other = conflict(name='Other', owners=('x', 'y'))
        self.assertIsNone(session.resolve(other))
        session.apply({**choose(entry, 1), **choose(other)})
        self.assertEqual(session.applicable_decisions, {**choose(entry, 1), **choose(other)})

    def test_changed_sources_keep_pair_preference_but_are_revalidated(self):
        original = conflict()
        session = ScriptReviewSession(choose(original))
        self.assertIs(session.resolve(original), original.candidates[0].item)
        changed = replace(original, candidates=(replace(original.candidates[0],
            item=replace(original.candidates[0].item, text=function(9))), original.candidates[1]))
        self.assertNotEqual(original.identity, changed.identity)
        self.assertEqual(session.resolve(changed).text, function(9))
        invalid = replace(changed, candidates=(replace(changed.candidates[0],
            item=replace(changed.candidates[0].item, text=function(kind='integer'))), changed.candidates[1]))
        with self.assertRaisesRegex(ValueError, 'parameter or return types'):
            session.resolve(invalid)

    def test_applicable_preferences_exclude_unobserved_pairs(self):
        entry = conflict()
        session = ScriptReviewSession({**choose(entry), pair_key('unseen-a', 'unseen-b'): 'unseen-a'})
        self.assertEqual(session.applicable_decisions, {})
        session.resolve(entry)
        self.assertEqual(session.applicable_decisions, choose(entry))

    def test_raw_source_invalid_owners_and_direct_mutation_cannot_bypass_choices(self):
        entry = conflict()
        identity = group_conflicts((entry,))[0].identity
        for choices in ({identity: function()}, {identity: 'not-a-contributor'},
                        {entry.identity: function()}, {identity: None}):
            with self.subTest(choices=choices), self.assertRaises(ValueError):
                ScriptReviewSession(choices)
        session = ScriptReviewSession(choose(entry))
        session.resolve(entry)
        session.decisions[identity] = function()
        with self.assertRaises(ValueError):
            session.require_resolved()

    def test_one_owner_cannot_supply_competing_definitions(self):
        entry = conflict()
        entry = replace(entry, candidates=(entry.candidates[0],
            replace(entry.candidates[1], owner=entry.candidates[0].owner)))
        with self.assertRaisesRegex(ValueError, 'one mod supplies competing'):
            group_conflicts((entry,))

    def test_selected_definition_requires_complete_safe_source(self):
        original = conflict()
        for text in ('', function().replace('Example', 'Other'), function() + function(),
                     'unknown directive\n' + function(), function() + '\n$Unknown();',
                     function().replace('return 1;', 'if (true) begin return 1;'),
                     'expression #Example 4\n', '// \u2603\n' + function(),
                     '<<<<<<< A\n' + function(),
                     function().replace('return 1;', 'foreach value in values do return value;')):
            entry = replace(original, candidates=(replace(original.candidates[0],
                item=replace(original.candidates[0].item, text=text)), original.candidates[1]))
            with self.subTest(text=text), self.assertRaises(ValueError):
                entry.validate_choice('first-id')

    def test_abi_preserves_parameter_and_return_types_not_parameter_spelling(self):
        original = conflict()
        renamed = replace(original, candidates=(replace(original.candidates[0],
            item=parse_gpl(function(2, parameter='renamed')).items[0]), original.candidates[1]))
        self.assertEqual(renamed.validate_choice('first-id').name, 'Example')
        for text in (function(kind='integer'), function().replace(' is integer', ''),
                     function().replace(' is integer', ' is boolean'),
                     function().replace('agent unit', 'agent unit, agent other'),
                     function().replace('agent unit', 'agent unit, agent unit')):
            entry = replace(original, candidates=(replace(original.candidates[0],
                item=parse_gpl(text).items[0]), original.candidates[1]))
            with self.subTest(text=text), self.assertRaises(ValueError):
                entry.validate_choice('first-id')

    def test_stock_void_header_forms_have_the_same_signature(self):
        for body in ('begin\n$Observe(unit);\nend\n',
                     'declare\ninteger value;\nbegin\nvalue = 1;\nend\n'):
            implicit = 'function Example(agent unit)\n' + body
            stock = 'function Example(agent unit) is\n' + body
            entry = conflict()
            entry = replace(entry, base=parse_gpl(implicit).items[0], candidates=(
                ScriptCandidate('Stock', parse_gpl(stock).items[0]),))
            self.assertEqual(entry.validate_choice('Stock').text, stock)

    def test_nonfunction_records_select_original_mod_version(self):
        for parser, left, right in ((parse_gpl, 'expression #Value 1\n', 'expression #Value 2\n'),
                                   (parse_dat, '[Values]\nA=1\n[end]\n', '[Values]\nA=2\n[end]\n')):
            item = parser(left).items[0]
            entry = ScriptConflict('majesty', item.key, item.name, 'different additions', None,
                (ScriptCandidate('A', item), ScriptCandidate('B', parser(right).items[0])))
            session = ScriptReviewSession()
            session.resolve(entry)
            session.apply({pair_key('A', 'B'): 'B'})
            self.assertIs(session.resolve(entry), entry.candidates[1].item)


if __name__ == '__main__':
    unittest.main()

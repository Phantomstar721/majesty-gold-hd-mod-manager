"""Accepted compatibility is an indivisible contender, not reopened raw edits.

These fixtures use parsed in-memory sources only; they never prepare a profile.
"""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from majesty_cam import compose
from majesty_cam.gpl import parse_gpl
from majesty_cam.script_review import (
    ScriptCandidate, ScriptConflict, ScriptReviewSession, group_conflicts, pair_key,
)
from majesty_cam.standard_scripts import Providers
from test_standard_scripts import provider


def function(value):
    return f'function Shared() is integer\nbegin\nreturn {value};\nend\n'


class CompatibilityPreferenceTests(unittest.TestCase):
    def setUp(self):
        contexts = ExitStack()
        self.addCleanup(contexts.close)
        self.sources = {
            'first': parse_gpl(function(2), 'first.gpl'),
            'second': parse_gpl(function(3), 'second.gpl'),
        }
        self.stock = {item.key: item for item in parse_gpl(function(1), 'stock.gpl').items}
        self.accepted = parse_gpl(function(5), 'compatibility.gpl').items[0]
        self.key = self.accepted.key
        self.native = provider(function(4), 'Native mod')
        contexts.enter_context(patch('majesty_cam.compose._parse_inventory_gpl_sources',
            side_effect=lambda inventory: [self.sources[inventory.selected.alias]]))
        contexts.enter_context(patch('majesty_cam.standard_scripts.verify'))
        contexts.enter_context(patch('majesty_cam.dataset_dependencies.load_dataset_symbols',
                                     return_value=object()))

    @property
    def inventories(self):
        return tuple(SimpleNamespace(selected=SimpleNamespace(alias=owner,
            package=SimpleNamespace(display_name=owner.title(), mod_id=owner + '-id',
                definition=SimpleNamespace(runtime_features=()))))
            for owner in self.sources)

    def merged(self, session, *, dataset='any', native=True, scoped=True, selected=None):
        options = {'resolution_owners': {self.key: selected}} if selected else {
            'semantic_resolutions': {self.key: compose.ScopedSemanticResolution(
                self.accepted, frozenset(('first', 'second'))) if scoped else self.accepted}}
        providers = (Providers((self.native,), lambda names: self.stock, Path('unused'), dataset)
                     if native else None)
        return compose.merge_gpl_resources(self.inventories,
            stock_function_loader=lambda names: self.stock,
            standard_providers=providers, script_review=session, script_dataset=dataset, **options)

    def choose(self, session, winner):
        session.apply({pair.identity: (winner if winner == 'native mod' else
            next(candidate.owner for candidate in (pair.left, pair.right)
                 if candidate.owner != 'native mod'))
            for pair in group_conflicts(session.observed)})

    def assert_accepted_candidates(self, session):
        self.assertTrue(session.observed)
        for conflict in session.observed:
            candidates = {candidate.owner: candidate for candidate in conflict.candidates}
            self.assertEqual(set(candidates), {'first-id', 'second-id', 'native mod'})
            for owner in ('first-id', 'second-id'):
                self.assertEqual(candidates[owner].item.text, self.accepted.text)
            self.assertEqual({frozenset(group) for group in conflict.compatibility_groups},
                             {frozenset(('first-id', 'second-id'))})
        self.assertEqual({pair.identity for pair in group_conflicts(session.observed)}, {
            pair_key('first-id', 'native mod'), pair_key('second-id', 'native mod')})

    def test_scoped_accepted_body_replaces_raw_candidates_without_internal_pair(self):
        session = ScriptReviewSession()
        self.merged(session)
        self.assert_accepted_candidates(session)

    def test_preferring_both_participants_keeps_accepted_body(self):
        session = ScriptReviewSession()
        pending = self.merged(session)
        self.choose(session, 'compatibility')
        text = pending.resume().source_set.gpl_text
        self.assertIn('return 5', text)
        self.assertNotIn('return 2', text)
        self.assertNotIn('return 3', text)
        self.assertNotIn('return 4', text)

    def test_preferring_native_removes_accepted_body_without_restoring_raw(self):
        session = ScriptReviewSession()
        pending = self.merged(session)
        self.choose(session, 'native mod')
        result = pending.resume()
        self.assertNotIn('function Shared', result.source_set.gpl_text,
                         'the native owner already supplies the chosen definition')

    def test_split_outside_preferences_rejected_atomically(self):
        session = ScriptReviewSession()
        self.merged(session)
        split = {pair_key('first-id', 'native mod'): 'first-id',
                 pair_key('second-id', 'native mod'): 'native mod'}
        with self.assertRaises(ValueError) as raised:
            session.apply(split)
        self.assertIn('First', str(raised.exception))
        self.assertIn('Second', str(raised.exception))
        self.assertEqual(session.decisions, {})

    def test_scoped_participants_do_not_include_outside_duplicate_source(self):
        self.sources['outside'] = parse_gpl(function(2), 'outside.gpl')
        session = ScriptReviewSession()
        self.merged(session)
        self.assert_accepted_candidates(session)

    def test_unscoped_explicit_resolution_retains_all_actual_contributors(self):
        self.sources['outside'] = parse_gpl(function(7), 'outside.gpl')
        session = ScriptReviewSession()
        self.merged(session, scoped=False)
        conflict = session.observed[0]
        self.assertEqual({frozenset(group) for group in conflict.compatibility_groups},
            {frozenset(('first-id', 'second-id', 'outside-id'))})
        for candidate in conflict.candidates:
            if candidate.owner != 'native mod':
                self.assertEqual(candidate.item.text, self.accepted.text)

    def test_owner_resolution_does_not_resurrect_rejected_owner(self):
        session = ScriptReviewSession()
        pending = self.merged(session, selected='first')
        self.assertEqual({candidate.owner for candidate in session.observed[0].candidates},
                         {'first-id', 'native mod'})
        self.assertFalse(session.observed[0].compatibility_groups)
        self.choose(session, 'compatibility')
        text = pending.resume().source_set.gpl_text
        self.assertIn('return 2', text)
        self.assertNotIn('return 3', text)

    def test_same_pair_choices_apply_to_each_quest_scope(self):
        session = ScriptReviewSession()
        pending = [self.merged(session, dataset=scope)
                   for scope in ('majesty', 'majestyexpansion')]
        self.assertEqual({conflict.dataset for conflict in session.observed},
                         {'majesty', 'majestyexpansion'})
        self.assert_accepted_candidates(session)
        self.choose(session, 'compatibility')
        for view in pending:
            self.assertIn('return 5', view.resume().source_set.gpl_text)

    def test_no_native_overlap_keeps_accepted_body_without_review(self):
        session = ScriptReviewSession()
        result = self.merged(session, native=False)
        self.assertFalse(session.observed)
        self.assertIn('return 5', result.source_set.gpl_text)

    def test_matching_native_body_does_not_reopen_accepted_compatibility(self):
        self.native = provider(self.accepted.text, 'Native mod')
        session = ScriptReviewSession()
        result = self.merged(session)
        self.assertFalse(session.observed)
        self.assertNotIn('function Shared', result.source_set.gpl_text)

    def test_safely_mergeable_native_edit_keeps_accepted_and_native_changes(self):
        stock = ('function Shared()\ndeclare\ninteger x;\ninteger y;\n'
                 'begin\nx=1;\ny=1;\nend\n')
        self.stock = {item.key: item for item in parse_gpl(stock, 'stock.gpl').items}
        self.sources = {name: parse_gpl(stock.replace('x=1;', f'x={value};'), name)
                        for name, value in (('first', 2), ('second', 3))}
        self.accepted = parse_gpl(stock.replace('x=1;', 'x=5;'), 'compatibility.gpl').items[0]
        self.native = provider(stock.replace('y=1;', 'y=4;'), 'Native mod')
        session = ScriptReviewSession()
        result = self.merged(session)
        self.assertFalse(session.observed)
        instructions = result.source_set.gpl_text.replace(' ', '')
        self.assertIn('x=5;', instructions)
        self.assertIn('y=4;', instructions)

    def test_group_cannot_claim_missing_or_different_body_participant(self):
        candidates = (ScriptCandidate('First', self.accepted, 'first-id'),
                      ScriptCandidate('Second', self.sources['second'].items[0], 'second-id'))
        for members in (('first-id', 'absent-id'), ('first-id', 'second-id')):
            with self.subTest(members=members):
                conflict = ScriptConflict('any', self.key, 'Shared', 'fixture',
                    self.stock[self.key], candidates, compatibility_groups=(members,))
                with self.assertRaises(ValueError):
                    group_conflicts((conflict,))


if __name__ == '__main__':
    unittest.main()

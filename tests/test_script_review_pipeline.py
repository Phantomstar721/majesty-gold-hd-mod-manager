"""Source-only review fixtures. Never prepares an installed Manager profile."""
from dataclasses import replace
from contextlib import ExitStack
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from threading import Event, Thread

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from majesty_cam import compose
from majesty_cam.gpl import parse_gpl
from majesty_cam.script_review import (ScriptReviewSession, ScriptReviewRequired,
                                     ScriptReviewCancelled, ScriptConflict, ScriptCandidate,
                                     pair_key, group_conflicts)
from majesty_cam.standard_scripts import Providers
from majesty_cam.manager.build import _read_mod_preferences, MANAGER_OUTPUT_SENTINEL
from test_standard_scripts import provider


def function(name, value):
    return f'function {name}() is integer\nbegin\nreturn {value};\nend\n'


def prefer_mods(conflicts, order=('first', 'second', 'Native mod')):
    """One consistent preference per mod pair, independent of quest scope."""
    priority = {label: index for index, label in enumerate(order)}
    result = {}
    for pair in group_conflicts(conflicts):
        winner = min((pair.left, pair.right), key=lambda candidate: priority[candidate.label])
        result[pair.identity] = winner.owner
    return result


class ScriptReviewPipelineTests(unittest.TestCase):
    def setUp(self):
        contexts = ExitStack()
        self.addCleanup(contexts.close)
        self.sources = {
            'first': parse_gpl(function('Shared', 2) + function('Other', 7)
                               + function('NativeOverlap', 9) + function('Unique', 11), 'first.gpl'),
            'second': parse_gpl(function('Shared', 3) + function('Other', 8), 'second.gpl'),
        }
        self.inventories = tuple(SimpleNamespace(selected=SimpleNamespace(alias=name))
                                 for name in self.sources)
        self.native = provider(function('Shared', 4) + function('NativeOverlap', 5), 'Native mod')
        self.stock = {item.key: item for item in parse_gpl(''.join(function(name, 1)
            for name in ('Shared', 'Other', 'NativeOverlap')), 'stock.gpl').items}
        self.scopes = []
        self.parse = contexts.enter_context(patch('majesty_cam.compose._parse_inventory_gpl_sources',
            side_effect=lambda inv: [self.sources[inv.selected.alias]]))
        contexts.enter_context(patch('majesty_cam.standard_scripts.verify'))
        contexts.enter_context(patch('majesty_cam.dataset_dependencies.load_dataset_symbols', return_value=object()))

    def run_bundle(self, resolver=None, session=None):
        def prepare(_game, inventories, *, script_dataset, script_review, **_kwargs):
            self.scopes.append(script_dataset)
            providers = Providers((self.native,), lambda names: self.stock, Path('unused'), script_dataset)
            return compose.merge_gpl_resources(inventories, stock_function_loader=lambda names: self.stock,
                standard_providers=providers, script_review=script_review, script_dataset=script_dataset)
        with patch('majesty_cam.compose.prepare_final_gpl_resources', side_effect=prepare):
            return compose.prepare_gpl_bundle(Path('unused'), self.inventories,
                standard_script_inputs=(SimpleNamespace(loads=(object(),), participants=()),),
                script_conflict_resolver=resolver, script_review=session)

    def test_both_scopes_and_all_contributors_reviewed_once_without_reanalysis(self):
        observed = []
        def choose(conflicts):
            observed.extend(conflicts)
            self.assertEqual(self.scopes, ['majesty', 'majestyexpansion'])
            self.assertEqual(self.parse.call_count, 4)
            shared = [c for c in conflicts if c.name == 'Shared']
            self.assertEqual(len(shared), 2)
            self.assertEqual([c.label for c in shared[0].candidates],
                             ['first', 'second', 'Native mod'])
            return prefer_mods(conflicts)
        bundle = self.run_bundle(choose)
        self.assertEqual(len(observed), 6)
        self.assertEqual(self.parse.call_count, 4, 'resuming must not repeat authored source analysis')
        self.assertEqual(bundle.patches, (), 'the same preferred mods win in both scopes')
        self.assertIn('Unique', bundle.common.source_set.gpl_text)
        self.assertIn('return 2', bundle.common.source_set.gpl_text)
        self.assertEqual(len(bundle.common.mod_preference_resolutions), 3)

    def test_unresolved_views_never_run_generated_transforms(self):
        with patch('majesty_cam.compose.compose_potion_policy') as transform:
            with self.assertRaises(ScriptReviewRequired) as raised:
                self.run_bundle()
            self.assertEqual(len(raised.exception.conflicts), 6)
            self.assertEqual(self.scopes, ['majesty', 'majestyexpansion'])
            transform.assert_not_called()

    def test_cancel_and_incomplete_decisions_do_not_resume(self):
        for resolver, error in ((lambda conflicts: None, ScriptReviewCancelled),
                                (lambda conflicts: {}, ValueError)):
            with self.subTest(error=error), patch('majesty_cam.compose.compose_potion_policy') as transform:
                with self.assertRaises(error):
                    self.run_bundle(resolver)
                transform.assert_not_called()

    def test_exact_saved_choices_skip_dialog_but_still_validate_and_transform(self):
        session = ScriptReviewSession()
        self.run_bundle(prefer_mods, session)
        choices = dict(session.decisions)
        self.scopes.clear()
        forbidden = Mock(side_effect=AssertionError('unchanged sources should reuse decisions'))
        repeated = ScriptReviewSession(choices)
        with patch('majesty_cam.compose.compose_potion_policy', wraps=compose.compose_potion_policy) as transform:
            self.run_bundle(forbidden, repeated)
            self.assertEqual(transform.call_count, 2)
        self.assertEqual(repeated.decisions, choices)
        # The policy follows actual mod owners, not per-body identities. Build
        # persistence (below) handles invalidation when the full plan changes.
        self.native = provider(function('Shared', 10) + function('NativeOverlap', 5), 'Native mod')
        self.run_bundle(forbidden, ScriptReviewSession(choices))

    def test_review_can_change_prior_pair_for_already_resolved_rules(self):
        session = ScriptReviewSession({pair_key('first', 'second'): 'first'})
        observed = []
        def choose(conflicts):
            observed.extend(conflicts)
            return prefer_mods(conflicts, ('Native mod', 'second', 'first'))
        bundle = self.run_bundle(choose, session)
        self.assertIn('Other', {c.name for c in observed})
        items = {item.name: item.text for item in parse_gpl(bundle.common.source_set.gpl_text).items}
        self.assertIn('return 8', items['Other'])
        self.assertNotIn('Shared', items, 'the preferred Standard mod already supplies this version')
        self.assertNotIn('NativeOverlap', items)
        self.assertTrue(all(session.winner(conflict) == 'native mod'
                            for conflict in session.conflicts if conflict.name == 'Shared'))

    def test_safe_third_mod_edit_survives_real_pair_preference(self):
        base = ('function Shared()\ndeclare\ninteger x;\ninteger y;\n'
                'begin\nx=1;\ny=1;\nend\n')
        self.sources = {
            'first': parse_gpl(base.replace('x=1;', 'x=2;'), 'first.gpl'),
            'second': parse_gpl(base.replace('y=1;', 'y=2;'), 'second.gpl'),
        }
        self.stock = {item.key: item for item in parse_gpl(base, 'stock.gpl').items}
        self.native = provider(base.replace('x=1;', 'x=3;'), 'Native mod')
        def choose(conflicts):
            pairs = group_conflicts(conflicts)
            self.assertEqual([{pair.left.label, pair.right.label} for pair in pairs],
                             [{'first', 'Native mod'}])
            return prefer_mods(conflicts, ('Native mod', 'first', 'second'))
        bundle = self.run_bundle(choose)
        instructions = bundle.common.source_set.gpl_text.replace(' ', '')
        self.assertIn('x=3;', instructions)
        self.assertIn('y=2;', instructions, 'a third mod\'s safely mergeable edit must survive')

    def test_opaque_native_owner_is_not_a_selectable_bypass(self):
        with patch.object(Providers, 'lookup', side_effect=ValueError('matching manifest Source files required')):
            chooser = Mock()
            with self.assertRaisesRegex(compose.ComposeError, 'Script analysis is blocked') as raised:
                self.run_bundle(chooser)
        self.assertIn('majesty:', str(raised.exception))
        self.assertIn('majestyexpansion:', str(raised.exception))
        self.assertIn('have not completed', str(raised.exception))
        chooser.assert_not_called()

    def test_resolved_sources_still_pass_generated_validation(self):
        with patch('majesty_cam.compose.compose_potion_policy', side_effect=ValueError('required callback absent')):
            with self.assertRaisesRegex(compose.ComposeError, 'script choices could not pass') as raised:
                self.run_bundle(prefer_mods)
        self.assertIn('majesty: required callback absent', str(raised.exception))
        self.assertIn('majestyexpansion: required callback absent', str(raised.exception))

    def test_single_scope_without_native_inputs_uses_same_review_path(self):
        session = ScriptReviewSession()
        with patch('majesty_cam.compose.prepare_final_gpl_resources', side_effect=lambda _g, inv, **kw:
                   compose.merge_gpl_resources(inv, stock_function_loader=lambda names: self.stock,
                       script_review=kw['script_review'], script_dataset=kw['script_dataset'])):
            bundle = compose.prepare_gpl_bundle(Path('unused'), self.inventories, script_review=session,
                script_conflict_resolver=prefer_mods)
        self.assertEqual(bundle.patches, ())
        self.assertEqual(len(session.conflicts), 2)
        self.assertTrue(all(c.dataset == 'any' for c in session.conflicts))

    def test_preferred_merge_mod_remains_output_when_native_would_otherwise_win(self):
        session = ScriptReviewSession()
        bundle = self.run_bundle(prefer_mods, session)
        self.assertIn('function Shared', bundle.common.source_set.gpl_text)
        self.assertIn('return 2', bundle.common.source_set.gpl_text)
        self.assertNotIn('return 4', bundle.common.source_set.gpl_text)

    def test_native_helper_change_also_surfaces_its_proof_dependent_caller(self):
        base = 'function Shared(agent unit)\ndeclare\ninteger a;\nbegin\na=1;\nend\n'
        first = base.replace('a=1;', 'if ($Guard(unit)) begin $First(unit); end\na=1;')
        second = base.replace('a=1;', 'if (unit\'s "Title" == "B") begin $Second(unit); end\na=1;')
        guard = ('function Guard(agent unit) is boolean\nbegin\n'
                 'if (unit\'s "Title" != "A") begin return false; end\nreturn true;\nend\n')
        self.sources = {'first': parse_gpl(first + guard, 'first.gpl'),
                        'second': parse_gpl(second, 'second.gpl')}
        self.stock = {item.key: item for item in parse_gpl(base, 'stock.gpl').items}
        self.native = provider('function Guard(agent unit) is boolean\nbegin\nreturn true;\nend\n', 'Native mod')
        session = ScriptReviewSession()
        def choose(conflicts):
            self.assertEqual({c.name for c in conflicts}, {'Shared', 'Guard'})
            return prefer_mods(conflicts, ('Native mod', 'first', 'second'))
        bundle = self.run_bundle(choose, session)
        self.assertEqual(len(session.conflicts), 4)
        self.assertNotIn('"A"', bundle.common.source_set.gpl_text)
        self.assertIn('$Guard(unit)', bundle.common.source_set.gpl_text)


class SavedModPreferenceTests(unittest.TestCase):
    def test_cancel_preserves_prior_output_and_force_review_ignores_saved_choices(self):
        from majesty_cam.manager.build import BuildPlan, build_merged_package
        for force in (False, True):
            with self.subTest(force=force), TemporaryDirectory() as temp:
                root = Path(temp)
                game = root / 'Game'
                game.mkdir()
                (game / 'MajestyHD.exe').write_bytes(b'fixture')
                target = root / 'Mods' / 'Majesty Mod Manager - Merged'
                target.mkdir(parents=True)
                saved = {pair_key('first', 'second'): 'first'}
                sentinel = json.dumps({'schema_version': 7, 'fingerprint': 'current', 'mod_preferences': saved})
                (target / MANAGER_OUTPUT_SENTINEL).write_text(sentinel)
                paths = SimpleNamespace(local_mods_root=target.parent, merged_output_root=target,
                    game_path=game, game_executable=game / 'MajestyHD.exe')
                selected = SimpleNamespace(ready=True, inventory=None, selected_mod=object(), content_id='fixture')
                plan = BuildPlan((), (selected,), {}, {}, (), 'current', (), stock_compose_inputs=(('fixture', 'hash'),))
                first, second = (parse_gpl(function('Shared', value)).items[0] for value in (2, 3))
                conflict = ScriptConflict('any', first.key, first.name, 'overlap', None,
                    (ScriptCandidate('first', first), ScriptCandidate('second', second)))
                chooser = Mock(return_value=None)
                def pause(_game, staging, _selected, **kwargs):
                    self.assertEqual(kwargs['script_review'].decisions, {} if force else saved)
                    kwargs['script_review'].resolve(conflict)
                    self.assertIsNone(kwargs['script_conflict_resolver']((conflict,)))
                    raise ScriptReviewCancelled('cancelled')
                with patch('majesty_cam.manager.build.compose_package', side_effect=pause), \
                        patch('majesty_cam.manager.build._require_current_plan_sources'), \
                        patch('majesty_cam.manager.build._publish_staging') as publish:
                    with self.assertRaises(ScriptReviewCancelled):
                        build_merged_package(plan, paths, script_conflict_resolver=chooser,
                                             review_scripts=force)
                publish.assert_not_called()
                chooser.assert_called_once_with((conflict,), preferences={} if force else saved)
                self.assertEqual((target / MANAGER_OUTPUT_SENTINEL).read_text(), sentinel)
                self.assertFalse(list(target.parent.glob('.MajestyModManager-build-*')))

    def test_only_successful_matching_plan_choices_are_reused(self):
        with TemporaryDirectory() as temp:
            target = Path(temp)
            marker = target / MANAGER_OUTPUT_SENTINEL
            self.assertEqual(_read_mod_preferences(target, 'current'), {})
            saved = {pair_key('first', 'second'): 'first'}
            marker.write_text(json.dumps({'schema_version': 7, 'fingerprint': 'current', 'mod_preferences': saved}))
            self.assertEqual(_read_mod_preferences(target, 'current'), saved)
            self.assertEqual(_read_mod_preferences(target, 'changed'), {})
            for payload in ([],
                            {'schema_version': 6, 'fingerprint': 'current', 'script_choices': {'id': 'text'}},
                            {'schema_version': 7, 'fingerprint': 'current', 'mod_preferences': ['bad']},
                            {'schema_version': 7, 'fingerprint': 'current', 'mod_preferences': {'bad': 1}},
                            {'schema_version': 7, 'fingerprint': 'current', 'mod_preferences': {'bad': 'first'}},
                            {'schema_version': 7, 'fingerprint': 'current', 'mod_preferences': {
                                pair_key('first', 'second'): 'third'}},
                            {'schema_version': 7, 'fingerprint': 'current', 'mod_preferences': {
                                pair_key('first', 'second'): 'first', pair_key('second', 'third'): 'second',
                                pair_key('first', 'third'): 'third'}}):
                marker.write_text(json.dumps(payload))
                self.assertEqual(_read_mod_preferences(target, 'current'), {})
            marker.write_text('not json')
            self.assertEqual(_read_mod_preferences(target, 'current'), {})


from majesty_cam.manager import app as manager_app


@unittest.skipIf(manager_app._PYSIDE_IMPORT_ERROR is not None, 'optional desktop runtime unavailable')
class ScriptReviewWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = manager_app.QApplication.instance() or manager_app.QApplication(['review-bridge-tests'])

    def test_worker_cancellation_is_not_reported_as_a_build_error(self):
        def action(progress):
            raise ScriptReviewCancelled('cancelled')
        worker = manager_app._ControllerTask(action)
        cancelled, error, finished, result = Mock(), Mock(), Mock(), Mock()
        worker.signals.cancelled.connect(cancelled)
        worker.signals.error.connect(error)
        worker.signals.finished.connect(finished)
        worker.signals.result.connect(result)
        worker.run()
        cancelled.assert_called_once_with()
        finished.assert_called_once_with()
        error.assert_not_called()
        result.assert_not_called()

    def test_request_bridge_releases_for_choices_errors_cancel_and_shutdown(self):
        for mode in ('choice', 'error', 'cancel', 'shutdown'):
            with self.subTest(mode=mode):
                ready = Event()
                captured = []
                state = SimpleNamespace(_shutting_down=Event(), _pending_script_review=None,
                    script_review_requested=SimpleNamespace(emit=lambda request: ready.set()))
                def run():
                    try:
                        captured.append(manager_app.ManagerWindow._request_script_review(
                            state, ('conflict',), preferences={pair_key('first', 'second'): 'first'}))
                    except ValueError as exc:
                        captured.append(str(exc))
                thread = Thread(target=run, daemon=True)
                thread.start()
                self.assertTrue(ready.wait(2))
                request = state._pending_script_review
                self.assertEqual(request.preferences, {pair_key('first', 'second'): 'first'})
                if mode == 'choice':
                    request.decisions = {pair_key('first', 'second'): 'second'}
                elif mode == 'error':
                    request.error = ValueError('dialog failed')
                if mode == 'shutdown':
                    manager_app.ManagerWindow._cancel_script_review(state)
                else:
                    request.finished.set()
                thread.join(2)
                self.assertFalse(thread.is_alive())
                self.assertEqual(captured, [{pair_key('first', 'second'): 'second'} if mode == 'choice'
                                           else 'dialog failed' if mode == 'error' else None])

    def test_dialog_failure_always_releases_waiting_worker(self):
        state = SimpleNamespace(_shutting_down=Event())
        request = manager_app._ScriptReviewRequest(())
        with patch('majesty_cam.manager.script_review_dialog.ScriptReviewDialog', side_effect=ValueError('bad dialog')):
            manager_app.ManagerWindow._review_script_conflicts(state, request)
        self.assertTrue(request.finished.is_set())
        self.assertIsInstance(request.error, ValueError)

    def test_dialog_receives_preferences_and_returns_only_mod_choices(self):
        state = SimpleNamespace(_shutting_down=Event())
        saved = {pair_key('first', 'second'): 'first'}
        revised = {pair_key('first', 'second'): 'second'}
        request = manager_app._ScriptReviewRequest(('conflict',), saved)
        dialog = Mock(decisions=revised)
        dialog.exec.return_value = manager_app.QDialog.DialogCode.Accepted
        with patch('majesty_cam.manager.script_review_dialog.ScriptReviewDialog', return_value=dialog) as factory:
            manager_app.ManagerWindow._review_script_conflicts(state, request)
        factory.assert_called_once_with(('conflict',), parent=state, preferences=saved)
        self.assertTrue(request.finished.is_set())
        self.assertEqual(request.decisions, revised)
        self.assertIsNone(request.error)


if __name__ == '__main__':
    unittest.main()

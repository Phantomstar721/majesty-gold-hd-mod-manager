import unittest
from pathlib import Path
from types import SimpleNamespace as NS

from majesty_cam.cam import CamEntry, pad_name
from majesty_cam.compose import CamResource, merge_sound_resources
from majesty_cam.sound_review import collect_sound_conflicts, sound_resolutions
from majesty_cam.script_review import ScriptReviewSession, ScriptReviewRequired, pair_key, group_conflicts


def inventory(owner, rows):
    package = NS(mod_id=owner, metadata=NS(display_name='Mod ' + owner))
    return NS(selected=NS(alias='alias-' + owner, package=package), resources=tuple(
        CamResource('alias-' + owner, Path(owner), 0, 0, index, section,
                    CamEntry(pad_name(key), payload))
        for index, (section, key, payload) in enumerate(rows)))


class SoundReviewTests(unittest.TestCase):
    def test_both_sound_sections_choose_whole_record_and_keep_unrelated(self):
        for winner in ('a', 'b'):
            inventories = tuple(inventory(owner, [(b'DSND', b'TEST', owner.encode()),
                (b'WAVE', b'TEST', (owner * 2).encode()),
                (b'DSND', (owner * 4).encode(), b'unrelated')]) for owner in ('a', 'b'))
            review = ScriptReviewSession()
            conflicts = collect_sound_conflicts(inventories, review, {})
            self.assertEqual(len(group_conflicts(conflicts)), 1)
            self.assertEqual(len(conflicts), 2)
            with self.assertRaises(ScriptReviewRequired):
                sound_resolutions(inventories, review, conflicts)
            review.apply({pair_key('a', 'b'): winner})
            waves, sounds, _ = merge_sound_resources(inventories,
                named_resolutions=sound_resolutions(inventories, review, conflicts))
            self.assertEqual(waves.sections[0].entries[0].data, (winner * 2).encode())
            self.assertEqual(sounds.sections[0].entries[0].data, winner.encode())
            self.assertEqual(len(sounds.sections[0].entries), 3)

    def test_native_last_record_and_stock_copies_are_not_conflicts(self):
        rows = [(b'DSND', b'TEST', b'old'), (b'DSND', b'TEST', b'same')]
        inventories = (inventory('a', rows), inventory('b', rows[-1:]),
                       inventory('c', [(b'DSND', b'TEST', b'stock')]))
        self.assertEqual(collect_sound_conflicts(inventories, ScriptReviewSession(),
                         {(b'DSND', b'TEST'): b'stock'}), ())

    def test_cached_pair_preference_and_three_owners(self):
        inventories = tuple(inventory(o, [(b'DSND', b'TEST', o.encode())]) for o in ('a', 'b', 'c'))
        choices = {pair_key('a', 'b'): 'b', pair_key('a', 'c'): 'c', pair_key('b', 'c'): 'c'}
        review = ScriptReviewSession(choices)
        conflicts = collect_sound_conflicts(inventories, review, {})
        self.assertFalse(review.unresolved)
        self.assertEqual(sound_resolutions(inventories, review, conflicts)[(b'DSND', b'TEST')].entry.data, b'c')

    def test_sound_and_xml_share_one_pair_choice(self):
        from test_description_review import conflict, record
        inventories = tuple(inventory(o, [(b'DSND', b'TEST', o.encode())]) for o in ('a', 'b'))
        review = ScriptReviewSession()
        sounds = collect_sound_conflicts(inventories, review, {})
        xml = conflict(('a', record(10)), ('b', record(20)))
        review.resolve(xml)
        self.assertEqual(len(group_conflicts(review.observed)), 1)
        review.apply({pair_key('a', 'b'): 'b'})
        self.assertEqual(review.resolve(xml)._fingerprint, record(20)._fingerprint)
        self.assertEqual(review.resolve(sounds[0]).data, b'b')

    def test_player_labels_do_not_require_script_items(self):
        from majesty_cam.manager.script_review_dialog import _gameplay_label, _gameplay_descriptions
        inventories = tuple(inventory(o, [(b'DSND', b'TEST', o.encode())]) for o in ('a', 'b'))
        conflicts = collect_sound_conflicts(inventories, ScriptReviewSession(), {})
        self.assertEqual(_gameplay_label(conflicts[0]), 'Sound definition: TEST')
        self.assertIn('shared ID', _gameplay_descriptions(conflicts))

    def test_sound_only_conflict_reaches_resource_review_and_cancels(self):
        from unittest.mock import patch
        from majesty_cam.description_composition import prepare_description_views
        from majesty_cam.descriptions import parse_descriptions
        from majesty_cam.script_review import ScriptReviewCancelled
        inventories = tuple(inventory(o, [(b'DSND', b'TEST', o.encode())]) for o in ('a', 'b'))
        review = ScriptReviewSession()
        collect_sound_conflicts(inventories, review, {})
        seen = []
        def cancel(conflicts):
            seen.extend(conflicts)
            return None
        with patch('majesty_cam.compose._load_effective_stock_descriptions', return_value={}), \
             patch('majesty_cam.compose.merge_description_resources', return_value=NS(document=parse_descriptions(b'<Majesty/>'))):
            with self.assertRaises(ScriptReviewCancelled):
                prepare_description_views(Path('.'), inventories, (), review, cancel)
        self.assertEqual(seen[0].key, (b'DSND', b'TEST'))

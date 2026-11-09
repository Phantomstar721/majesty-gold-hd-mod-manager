import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from test_conflict_preview import entry, catalog_for
from majesty_cam.manager.build import standard_content_conflicts
from majesty_cam.manager.standard_review import StandardReviewConflict, native_choices, validate_native_choices
from majesty_cam.script_review import pair_key
from majesty_cam.manager.script_review_dialog import ScriptReviewDialog
from PySide6.QtWidgets import QApplication, QDialog


class StandardReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_all_pairs_one_dialog_cancel_and_cycle_repair(self):
        entries = [entry(i, 'Mod ' + str(i), {'function:damage': str(i)}) for i in range(1, 4)]
        catalog = catalog_for(*entries)
        selected = {e.content_id: True for e in entries}
        conflicts = standard_content_conflicts(catalog, selected)
        wrapped = tuple(StandardReviewConflict(c) for c in conflicts)
        def validate(choices):
            validate_native_choices(catalog, selected, native_choices(conflicts, choices))
        a, b, c = (e.content_id for e in entries)
        choices = {pair_key(a,b):a, pair_key(b,c):b, pair_key(a,c):c}
        dialog = ScriptReviewDialog(wrapped, preferences=choices, validate_choices=validate)
        self.assertEqual(len(dialog.pairs), 3)
        self.assertTrue(all(w.isHidden() for w in dialog.pair_details.values()))
        dialog.accept()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertTrue(dialog.error.text())
        dialog.choice_buttons[pair_key(a,c)][a].click()
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        cancelled = ScriptReviewDialog(wrapped, preferences=choices)
        cancelled.reject()
        self.assertEqual(cancelled.decisions, {})

    def test_required_order_is_checked_before_acceptance(self):
        a = entry(1, 'A', {'function:damage':'a'})
        b = entry(2, 'B', {'function:damage':'b'}, load_after_ids=(a.content_id,))
        with self.assertRaises(ValueError):
            validate_native_choices(catalog_for(a,b), {a.content_id:True,b.content_id:True},
                                    {'|'.join(sorted((a.content_id,b.content_id))):a.content_id})

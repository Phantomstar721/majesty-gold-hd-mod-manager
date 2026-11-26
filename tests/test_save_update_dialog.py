from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from majesty_cam.manager import save_update_dialog as update_ui
from majesty_cam.manager.saves import SaveState, plan_save_updates, read_mod_list

from test_save_updates import A, B, C, make_save, make_target, save_records


@unittest.skipIf(update_ui._PYSIDE_IMPORT_ERROR is not None, "optional desktop runtime unavailable")
class SaveUpdateDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.application = QApplication.instance() or QApplication(["save-update-tests"])

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.addCleanup(self.folder.cleanup)
        target = make_target()
        for name, members in (("Day 1", (A, C)), ("Day 2", (A, C)), ("Day 3", (A, B, C))):
            (self.root / f"{name}.GMP").write_bytes(make_save(save_records(members)))
        self.dialog = update_ui.SaveUpdateDialog(lambda: plan_save_updates(self.root, target), self.root, "Target")
        self.addCleanup(self.dialog.close)

    def items(self):
        return [self.dialog.tree.topLevelItem(i) for i in range(self.dialog.tree.topLevelItemCount())]

    def test_nothing_is_ticked_and_only_updatable_saves_can_be(self):
        from PySide6.QtCore import Qt
        checkable = [i for i in self.items() if i.flags() & Qt.ItemFlag.ItemIsUserCheckable]
        self.assertEqual(sorted(i.text(0) for i in checkable), ["Day 1", "Day 2"])
        self.assertTrue(all(i.checkState(0) == Qt.CheckState.Unchecked for i in checkable))
        self.assertFalse(self.dialog.apply_button.isEnabled())
        current = next(i for i in self.items() if i.text(0) == "Day 3")
        self.assertFalse(current.flags() & Qt.ItemFlag.ItemIsUserCheckable)
        self.assertIn("2 can be updated", self.dialog.counts.text())

    def test_only_the_ticked_save_gets_an_updated_copy(self):
        from PySide6.QtCore import Qt
        chosen = next(i for i in self.items() if i.text(0) == "Day 1")
        chosen.setCheckState(0, Qt.CheckState.Checked)
        self.assertEqual(self.dialog.apply_button.text(), "Update 1 Selected Save")
        before = (self.root / "Day 1.GMP").read_bytes()
        with patch.object(update_ui.QMessageBox, "information") as shown:
            self.dialog.apply()
        self.assertEqual(sorted(p.name for p in self.root.glob("*(updated)*")), ["Day 1 (updated).GMP"])
        self.assertEqual((self.root / "Day 1.GMP").read_bytes(), before)
        self.assertIn("Day 1 (updated).GMP", shown.call_args.args[2])
        self.assertEqual(len(read_mod_list((self.root / "Day 1 (updated).GMP").read_bytes()).records), 4)
        states = {plan.path.name: plan.state for plan in self.dialog.plans}
        self.assertIs(states["Day 1.GMP"], SaveState.UPDATED)
        self.assertIs(states["Day 2.GMP"], SaveState.UPDATABLE)

    def test_cautions_ask_again_and_no_means_nothing_is_written(self):
        from PySide6.QtCore import Qt
        stock = {"majestyexpansion": frozenset()}
        target = make_target(unit_types={B: frozenset({"new1"})}, stock=stock)
        dialog = update_ui.SaveUpdateDialog(lambda: plan_save_updates(self.root, target), self.root, "Target")
        self.addCleanup(dialog.close)
        item = next(dialog.tree.topLevelItem(i) for i in range(dialog.tree.topLevelItemCount())
                    if dialog.tree.topLevelItem(i).text(0) == "Day 2")
        item.setCheckState(0, Qt.CheckState.Checked)
        with patch.object(update_ui.QMessageBox, "question",
                          return_value=update_ui.QMessageBox.StandardButton.No) as asked:
            dialog.apply()
        asked.assert_called_once()
        self.assertEqual(list(self.root.glob("*(updated)*")), [])


if __name__ == "__main__":
    unittest.main()

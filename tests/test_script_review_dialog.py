from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from majesty_cam.gpl import DefinitionKind, SemanticItem
from majesty_cam.script_review import ScriptCandidate, ScriptConflict
from majesty_cam.manager import script_review_dialog as review_ui


def item(value, name="Shared"):
    text = f"function {name}(agent unit)\ndeclare\ninteger value;\nbegin\nvalue={value};\nend\n"
    return SemanticItem.resolved(DefinitionKind.FUNCTION, name, text)


def conflict(dataset="majesty", name="Shared", owners=("first", "second"), labels=None):
    labels = labels or tuple(owner.title() + " mod" for owner in owners)
    return ScriptConflict(
        dataset=dataset, key=(DefinitionKind.FUNCTION, name.casefold()), name=name,
        detail="Competing instructions <literal> & technical detail",
        base=item(1, name),
        candidates=tuple(ScriptCandidate(label, item(value, name), owner=owner)
                         for value, (owner, label) in enumerate(zip(owners, labels), 2)),
    )


@unittest.skipIf(review_ui._PYSIDE_IMPORT_ERROR is not None, "optional desktop runtime unavailable")
class ScriptReviewDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.application = QApplication.instance() or QApplication(["script-review-tests"])

    def dialog(self, *conflicts, **kwargs):
        dialog = review_ui.ScriptReviewDialog(conflicts, **kwargs)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def choose(self, dialog, row=0, owner=None):
        pair = dialog.pairs[row]
        owner = owner or pair.left.owner
        dialog.choice_buttons[pair.identity][owner].click()
        return pair.identity, owner

    def test_one_preference_covers_every_rule_and_both_quest_scopes(self):
        dialog = self.dialog(conflict(name="Damage"), conflict(name="Potion_Check"),
                             conflict("majestyexpansion", name="Damage"))
        self.assertEqual(len(dialog.pairs), 1)
        self.assertEqual(dialog.decisions, {})
        self.assertFalse(dialog.continue_button.isEnabled())
        self.assertFalse(any(button.isChecked() for button in
                             dialog.choice_buttons[dialog.pairs[0].identity].values()))
        dialog.accept()
        self.assertEqual(dialog.result(), review_ui.QDialog.DialogCode.Rejected)
        key, owner = self.choose(dialog)
        self.assertTrue(dialog.continue_button.isEnabled())
        self.assertEqual(dialog.progress.text(), "1 of 1 mod preferences chosen")
        self.assertEqual(dialog.decisions, {})
        dialog.continue_button.click()
        self.assertEqual(dialog.result(), review_ui.QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.decisions, {key: owner})

    def test_gameplay_summary_is_aggregated_without_code_or_technical_names(self):
        from PySide6.QtWidgets import QLabel, QPlainTextEdit, QTextEdit
        dialog = self.dialog(conflict(name="Damage"), conflict(name="Potion_Check"),
                             conflict("majestyexpansion", name="Uninterpreted_Mod_Function"))
        summary = dialog.pair_summaries[dialog.pairs[0].identity].text()
        self.assertIn("Attack damage", summary)
        self.assertIn("Potion use", summary)
        self.assertIn("Other gameplay changes", summary)
        self.assertIn("Original and expansion quests", summary)
        self.assertFalse(dialog.findChildren(QPlainTextEdit))
        self.assertFalse(dialog.findChildren(QTextEdit))
        visible_text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
        for unwanted in ("Potion_Check", "Uninterpreted_Mod_Function", "<literal>",
                         "value=", "Competing instructions"):
            self.assertNotIn(unwanted, visible_text)
        self.assertIn("conflicting behavior", dialog.warning.text())
        self.assertIn("may be replaced", dialog.warning.text())

    def test_gameplay_descriptions_explain_known_roles_once_across_scopes(self):
        from PySide6.QtWidgets import QLabel
        dialog = self.dialog(conflict(name="Random_Hero_Type"), conflict(name="Spell_Extra_Value"),
                             conflict(name="Guild_Title"),
                             conflict("majestyexpansion", name="Random_Hero_Type"))
        pair = dialog.pairs[0]
        summary = dialog.pair_summaries[pair.identity].text()
        description = dialog.pair_descriptions[pair.identity].text()
        self.assertIn("Random hero arrivals", summary)
        self.assertIn("Confidence in battle", summary)
        self.assertIn("Finding a home guild", summary)
        self.assertNotIn("Other gameplay changes", summary)
        self.assertEqual(description.count("Embassy/outpost"), 1)
        self.assertIn("fight or flee, not the damage", description)
        self.assertIn("hero's home", description)
        self.assertEqual(dialog.pair_descriptions[pair.identity].textFormat(), review_ui.Qt.TextFormat.PlainText)
        visible_text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
        for name in ("Random_Hero_Type", "Spell_Extra_Value", "Guild_Title"):
            self.assertNotIn(name, visible_text)
        self.assertIn("not the exact changes each mod makes", dialog.warning.text())

    def test_existing_compatibility_is_explained_without_an_internal_pair_or_code(self):
        from PySide6.QtWidgets import QLabel
        shared = conflict(name="Random_Hero_Type", owners=("first", "second", "third"))
        shared = replace(shared, compatibility_groups=(("first", "second"),), candidates=(
            shared.candidates[0], replace(shared.candidates[1], item=shared.candidates[0].item),
            shared.candidates[2]))
        dialog = self.dialog(shared, replace(shared, dataset="majestyexpansion"))
        self.assertEqual(len(dialog.pairs), 2)
        for pair in dialog.pairs:
            self.assertNotEqual({pair.left.owner, pair.right.owner}, {"first", "second"})
            note = dialog.pair_compatibility_notes[pair.identity].text()
            self.assertEqual(note.count("Existing compatibility"), 1)
            self.assertIn("First mod and Second mod together for Random hero arrivals", note)
            self.assertIn("Use consistent preferences", note)
        visible_text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
        self.assertNotIn("Random_Hero_Type", visible_text)
        self.assertNotIn("value=", visible_text)

    def test_one_choice_for_each_pair_not_one_for_each_definition(self):
        first = conflict(name="Damage")
        second = conflict(name="Potion_Check", owners=("first", "third"))
        dialog = self.dialog(first, second)
        self.assertEqual(len(dialog.pairs), 2)
        self.choose(dialog)
        self.assertFalse(dialog.continue_button.isEnabled())
        self.choose(dialog, 1)
        self.assertTrue(dialog.continue_button.isEnabled())

    def test_preferences_use_stable_ids_and_only_known_winners_are_preselected(self):
        current = conflict(labels=("A & B", "Second <literal>"))
        initial = self.dialog(current)
        key = initial.pairs[0].identity
        dialog = self.dialog(current, preferences={key: "second", "unrelated": "first"})
        self.assertEqual(dialog.decisions, {})
        self.assertTrue(dialog.choice_buttons[key]["second"].isChecked())
        self.assertTrue(dialog.continue_button.isEnabled())
        self.assertEqual(dialog.choice_buttons[key]["first"].text(), "A && B")
        dialog.accept()
        self.assertEqual(dialog.decisions, {key: "second"})
        unknown = self.dialog(current, preferences={key: "missing"})
        self.assertFalse(unknown.continue_button.isEnabled())

    def test_changing_preference_replaces_only_that_pair(self):
        dialog = self.dialog(conflict(), conflict(owners=("first", "third"), name="Damage"))
        choices = dict(self.choose(dialog, row) for row in range(len(dialog.pairs)))
        pair = dialog.pairs[0]
        choices[pair.identity] = pair.right.owner
        self.choose(dialog, owner=pair.right.owner)
        self.assertFalse(dialog.choice_buttons[pair.identity][pair.left.owner].isChecked())
        dialog.accept()
        self.assertEqual(dialog.decisions, choices)

    def test_cycles_between_three_mods_are_rejected_without_partial_decisions(self):
        dialog = self.dialog(conflict(owners=("first", "second", "third")))
        self.assertEqual(len(dialog.pairs), 3)
        winners = {frozenset(("first", "second")): "first",
                   frozenset(("second", "third")): "second",
                   frozenset(("first", "third")): "third"}
        for row, pair in enumerate(dialog.pairs):
            self.choose(dialog, row, winners[frozenset((pair.left.owner, pair.right.owner))])
        dialog.accept()
        self.assertEqual(dialog.result(), review_ui.QDialog.DialogCode.Rejected)
        self.assertEqual(dialog.decisions, {})
        self.assertTrue(dialog.error.text())
        for row, pair in enumerate(dialog.pairs):
            if {pair.left.owner, pair.right.owner} == {"first", "third"}:
                self.choose(dialog, row, "first")
        self.assertFalse(dialog.error.text())
        dialog.accept()
        self.assertEqual(dialog.result(), review_ui.QDialog.DialogCode.Accepted)

    def test_cancel_does_not_return_choices(self):
        dialog = self.dialog(conflict())
        self.choose(dialog)
        dialog.cancel_button.click()
        self.assertEqual(dialog.result(), review_ui.QDialog.DialogCode.Rejected)
        self.assertEqual(dialog.decisions, {})

    def test_validation_failure_keeps_dialog_open(self):
        dialog = self.dialog(conflict())
        self.choose(dialog)
        with patch.object(review_ui.ScriptReviewSession, "apply", side_effect=ValueError("Choose a consistent preference.")):
            dialog.accept()
        self.assertEqual(dialog.result(), review_ui.QDialog.DialogCode.Rejected)
        self.assertEqual(dialog.decisions, {})
        self.assertEqual(dialog.error.text(), "Choose a consistent preference.")

    def test_scope_and_mod_labels_are_literal(self):
        dialog = self.dialog(conflict("majestyexpansion", labels=("<b>One</b>", "Two & Three")))
        pair = dialog.pairs[0]
        summary = dialog.pair_summaries[pair.identity]
        self.assertIn("Expansion quests", summary.text())
        self.assertEqual(summary.textFormat(), review_ui.Qt.TextFormat.PlainText)

    def test_light_and_dark_system_palettes_keep_readable_text(self):
        from PySide6.QtGui import QColor, QPalette
        old_palette = self.application.palette()
        old_stylesheet = self.application.styleSheet()
        self.addCleanup(self.application.setPalette, old_palette)
        self.addCleanup(self.application.setStyleSheet, old_stylesheet)
        theme = Path(review_ui.__file__).with_name("theme.qss").read_text(encoding="utf-8")
        self.application.setStyleSheet(theme)
        for background, foreground in (("#ffffff", "#000000"), ("#000000", "#ffffff")):
            palette = QPalette()
            for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base):
                palette.setColor(role, QColor(background))
            for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text):
                palette.setColor(role, QColor(foreground))
            self.application.setPalette(palette)
            dialog = self.dialog(conflict())
            dialog.ensurePolished()
            button = next(iter(dialog.choice_buttons[dialog.pairs[0].identity].values()))
            for widget, text_role in ((dialog.introduction, QPalette.ColorRole.WindowText),
                                      (button, QPalette.ColorRole.ButtonText)):
                widget.ensurePolished()
                self.assertEqual(widget.palette().color(text_role).name(), "#eee8d9")


if __name__ == "__main__":
    unittest.main()

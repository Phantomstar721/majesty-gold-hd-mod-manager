"""Player-facing mod preferences for changes that cannot be safely combined."""
from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from ..script_review import ScriptReviewSession, group_conflicts
from .conflict_preview import rule_explanation, rule_label

if TYPE_CHECKING:
    from ..script_review import ScriptConflict

try:  # Command-line use does not require the optional desktop runtime.
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QButtonGroup, QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
        QScrollArea, QVBoxLayout, QWidget,
    )
except ImportError as exc:  # pragma: no cover - optional dependency.
    _PYSIDE_IMPORT_ERROR = exc
else:
    _PYSIDE_IMPORT_ERROR = None


def _scope_label(conflicts) -> str:
    scopes = {conflict.dataset.casefold() for conflict in conflicts}
    if "any" in scopes or {"majesty", "majestyexpansion"} <= scopes:
        return "Original and expansion quests"
    if scopes == {"majesty"}:
        return "Original quests"
    if scopes == {"majestyexpansion"}:
        return "Expansion quests"
    return "Selected quests"


def _gameplay_label(conflict) -> str:
    label = rule_label(f"{conflict.key[0].value}:{conflict.key[1]}")
    # Do not expose language terms or pretend to understand unknown changes.
    return {
        "Other script behavior (effect not interpreted)": "Other gameplay changes",
        "Shared script settings": "Shared game settings",
        "Script declarations": "Shared game behavior",
    }.get(label, label)


def _gameplay_descriptions(conflicts) -> str:
    descriptions = set()
    for conflict in conflicts:
        explanation = rule_explanation(f"{conflict.key[0].value}:{conflict.key[1]}")
        if explanation:
            descriptions.add((_gameplay_label(conflict), explanation))
    return "\n".join(f"{label}: {explanation}" for label, explanation in sorted(descriptions))


def _compatibility_notes(pair) -> str:
    groups = {}
    endpoints = {pair.left.owner, pair.right.owner}
    for conflict in pair.conflicts:
        labels = {candidate.owner: candidate.label for candidate in conflict.candidates}
        for group in conflict.compatibility_groups:
            owners = set(group)
            if endpoints & owners and endpoints - owners:
                names = tuple(sorted(labels[owner] for owner in group))
                groups.setdefault(names, set()).add(_gameplay_label(conflict))
    return "\n".join(
        f"Existing compatibility keeps {' and '.join(names)} together for {', '.join(sorted(categories))}. "
        "Use consistent preferences against the other mod for this shared behavior."
        for names, categories in sorted(groups.items()))


# Pair explicit surfaces with text colours even when Windows uses light mode.
_DIALOG_STYLE = """
QDialog#scriptReviewDialog, QDialog#scriptReviewDialog QWidget {
    color: #eee8d9; background-color: #181410;
}
QDialog#scriptReviewDialog QScrollArea { border: none; }
QDialog#scriptReviewDialog QFrame[conflictCard="true"] {
    background-color: #211b14; border: 1px solid #5c4c32; border-radius: 4px;
}
QDialog#scriptReviewDialog QFrame[conflictCard="true"] QLabel {
    background-color: transparent; border: none;
}
QDialog#scriptReviewDialog QPushButton {
    color: #eee8d9; background-color: #241e15;
    border: 1px solid #806735; border-radius: 3px; padding: 8px 12px;
}
QDialog#scriptReviewDialog QPushButton:checked {
    color: #fff9e9; background-color: #614c20; border: 2px solid #e4c36c;
}
QDialog#scriptReviewDialog QPushButton:disabled { color: #958b7e; border-color: #4a4038; }
QDialog#scriptReviewDialog QPushButton:focus { border-color: #e4c36c; }
QDialog#scriptReviewDialog QLabel#scriptReviewError { color: #ffb3a7; }
"""


if _PYSIDE_IMPORT_ERROR is None:

    class ScriptReviewDialog(QDialog):
        """One explicit preference per mod pair, across all affected rules/scopes."""

        def __init__(self, conflicts: Sequence["ScriptConflict"], parent=None, *, preferences=None):
            super().__init__(parent)
            self.conflicts = tuple(conflicts)
            self.pairs = group_conflicts(self.conflicts)
            self.decisions = {}
            self._choices = {}
            self._groups = []
            self.choice_buttons = {}
            self.pair_summaries = {}
            self.pair_descriptions = {}
            self.pair_compatibility_notes = {}
            self.pair_outcomes = {}
            self.setObjectName("scriptReviewDialog")
            self.setWindowTitle("Majesty Mod Manager — Choose preferred mods")
            self.setStyleSheet(_DIALOG_STYLE)
            layout = QVBoxLayout(self)
            self.introduction = self._label(
                "The Manager has combined the changes it can safely merge. For the remaining "
                "overlaps, choose your preferred mod in each pair. That preference applies "
                "to every unresolved conflict between those two mods.")
            layout.addWidget(self.introduction)
            self.warning = self._label(
                "Both mods stay enabled. Your preferred mod wins their conflicting behavior; "
                "the other mod's changes there may be replaced. Independently compatible "
                "changes are kept. The descriptions below explain what the shared behavior "
                "controls, not the exact changes each mod makes.")
            layout.addWidget(self.warning)
            self.progress = self._label("")
            self.progress.setAccessibleName("Mod preference progress")
            layout.addWidget(self.progress)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            content = QWidget()
            cards = QVBoxLayout(content)
            cards.setContentsMargins(0, 0, 8, 0)
            for pair in self.pairs:
                card = QFrame()
                card.setProperty("conflictCard", True)
                card_layout = QVBoxLayout(card)
                heading = self._label(f"{pair.left.label} / {pair.right.label}")
                heading_font = heading.font()
                heading_font.setBold(True)
                heading.setFont(heading_font)
                card_layout.addWidget(heading)
                categories = sorted({_gameplay_label(conflict) for conflict in pair.conflicts})
                summary = self._label(
                    "Affected: " + ", ".join(categories) + "\n" + _scope_label(pair.conflicts))
                self.pair_summaries[pair.identity] = summary
                card_layout.addWidget(summary)
                description = _gameplay_descriptions(pair.conflicts)
                if description:
                    explanation = self._label(description)
                    self.pair_descriptions[pair.identity] = explanation
                    card_layout.addWidget(explanation)
                compatibility = _compatibility_notes(pair)
                if compatibility:
                    note = self._label(compatibility)
                    self.pair_compatibility_notes[pair.identity] = note
                    card_layout.addWidget(note)
                group = QButtonGroup(self)
                group.setExclusive(True)
                self._groups.append(group)
                buttons = {}
                for candidate in (pair.left, pair.right):
                    button = self._button(candidate.label.replace("&", "&&"))
                    button.setCheckable(True)
                    button.setAccessibleName(f"Prefer {candidate.label}")
                    button.setToolTip(f"Use {candidate.label} for every unresolved conflict between these mods.")
                    button.clicked.connect(
                        lambda checked=False, p=pair, c=candidate: self._choose(p, c))
                    group.addButton(button)
                    buttons[candidate.owner] = button
                    card_layout.addWidget(button)
                self.choice_buttons[pair.identity] = buttons
                outcome = self._label("Choose your preferred mod.")
                self.pair_outcomes[pair.identity] = outcome
                card_layout.addWidget(outcome)
                cards.addWidget(card)
            cards.addStretch(1)
            scroll.setWidget(content)
            layout.addWidget(scroll, 1)
            self.error = self._label("")
            self.error.setObjectName("scriptReviewError")
            self.error.setAccessibleName("Mod preference issue")
            layout.addWidget(self.error)
            actions = QHBoxLayout()
            actions.addStretch(1)
            self.cancel_button = self._button("Cancel")
            self.cancel_button.clicked.connect(self.reject)
            actions.addWidget(self.cancel_button)
            self.continue_button = self._button("Continue preparing")
            self.continue_button.clicked.connect(self.accept)
            actions.addWidget(self.continue_button)
            layout.addLayout(actions)
            for pair in self.pairs:
                selected = dict(preferences or {}).get(pair.identity)
                candidate = next((c for c in (pair.left, pair.right) if c.owner == selected), None)
                if candidate is not None:
                    self.choice_buttons[pair.identity][candidate.owner].setChecked(True)
                    self._choose(pair, candidate)
            self._update_progress()
            available = self.screen().availableGeometry()
            preferred_height = min(740, 240 + 190 * len(self.pairs))
            self.resize(min(760, available.width() - 50), min(preferred_height, available.height() - 60))

        @staticmethod
        def _label(text):
            label = QLabel(text)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            return label

        @staticmethod
        def _button(text):
            button = QPushButton(text)
            button.setAutoDefault(False)
            return button

        def _choose(self, pair, candidate):
            self._choices[pair.identity] = candidate.owner
            self.pair_outcomes[pair.identity].setText(
                f"{candidate.label} is preferred for all conflicts between these two mods.")
            self.error.clear()
            self._update_progress()

        def _update_progress(self):
            count = len(self._choices)
            self.progress.setText(f"{count} of {len(self.pairs)} mod preferences chosen")
            self.continue_button.setEnabled(count == len(self.pairs))

        def accept(self):
            if len(self._choices) != len(self.pairs):
                return
            # Share exactly the build's consistency checks, including cycles
            # across three or more mods; never publish a partial choice set.
            session = ScriptReviewSession()
            try:
                for conflict in self.conflicts:
                    session.resolve(conflict)
                session.apply(self._choices)
            except ValueError as exc:
                self.error.setText(str(exc))
                return
            self.decisions = dict(self._choices)
            super().accept()

        def reject(self):
            self.decisions = {}
            super().reject()

else:  # pragma: no cover - optional dependency.

    class ScriptReviewDialog:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("Mod preference review requires the optional PySide6 desktop runtime") from _PYSIDE_IMPORT_ERROR

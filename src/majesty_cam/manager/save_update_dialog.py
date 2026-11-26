"""Player-chosen save updates: pick saves, write updated copies beside them."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from .saves import SaveState, SaveUpdateError, SaveUpdatePlan, write_updated_copy

try:  # Command-line use does not require the optional desktop runtime.
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import (
        QApplication, QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
        QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    )
except ImportError as exc:  # pragma: no cover - optional dependency.
    _PYSIDE_IMPORT_ERROR = exc
else:
    _PYSIDE_IMPORT_ERROR = None


STATUS_TEXT = {
    SaveState.UPDATABLE: "Can be updated",
    SaveState.CAUTION: "Can be updated, with a caution",
    SaveState.CURRENT: "Already uses your current mods",
    SaveState.UPDATED: "Already updated",
    SaveState.BLOCKED: "Not updated",
    SaveState.UNREADABLE: "Cannot be read",
}
_STATE_ORDER = {SaveState.UPDATABLE: 0, SaveState.CAUTION: 1, SaveState.BLOCKED: 2,
                SaveState.UPDATED: 3, SaveState.CURRENT: 4, SaveState.UNREADABLE: 5}

INTRO_TEXT = (
    "Tick the saves you want to keep playing with your current mods. Each one is written as a new copy "
    "named \"(updated)\" beside the original, which is not changed. A save is only offered when updating "
    "it adds mods: a save that would lose a mod, or that uses mods outside your current selection, is "
    "left as it is."
)


def plan_details(plan: SaveUpdatePlan) -> str:
    """The details pane text for one save."""

    lines = [plan.path.name]
    if plan.save_name or plan.quest_name:
        lines.append(" · ".join(part for part in (plan.save_name, plan.quest_name) if part))
    if plan.profile_label:
        lines.append(plan.profile_label)
    lines.append("")
    lines.append(f"{STATUS_TEXT[plan.state]}: {plan.summary}")
    lines.extend(plan.details)
    if plan.cautions:
        lines.append("")
        lines.append("Cautions:")
        lines.extend(f"• {caution}" for caution in plan.cautions)
    return "\n".join(lines)


def counts_text(plans: Sequence[SaveUpdatePlan]) -> str:
    offered = sum(plan.selectable for plan in plans)
    cautions = sum(plan.state is SaveState.CAUTION for plan in plans)
    left = sum(plan.state in (SaveState.BLOCKED, SaveState.UNREADABLE) for plan in plans)
    current = sum(plan.state in (SaveState.CURRENT, SaveState.UPDATED) for plan in plans)
    parts = [f"{offered} can be updated" + (f" ({cautions} with cautions)" if cautions else ""),
             f"{current} already current", f"{left} left as they are"]
    return f"{len(plans)} saves: " + " · ".join(parts)


_DIALOG_STYLE = """
QDialog#saveUpdateDialog, QDialog#saveUpdateDialog QWidget {
    color: #eee8d9; background-color: #181410;
}
QDialog#saveUpdateDialog QTreeWidget {
    background-color: #211b14; alternate-background-color: #1c1711;
    border: 1px solid #5c4c32;
}
QDialog#saveUpdateDialog QTreeWidget::item:selected { background-color: #614c20; color: #fff9e9; }
QDialog#saveUpdateDialog QHeaderView::section {
    background-color: #241e15; color: #eee8d9; border: none; border-right: 1px solid #5c4c32;
    padding: 4px 6px;
}
QDialog#saveUpdateDialog QLabel#saveUpdateDetails {
    background-color: #211b14; border: 1px solid #5c4c32; border-radius: 4px; padding: 8px;
}
QDialog#saveUpdateDialog QPushButton {
    color: #eee8d9; background-color: #241e15;
    border: 1px solid #806735; border-radius: 3px; padding: 8px 12px; min-height: 0;
}
QDialog#saveUpdateDialog QPushButton:disabled { color: #958b7e; border-color: #4a4038; }
QDialog#saveUpdateDialog QPushButton:focus { border-color: #e4c36c; }
QDialog#saveUpdateDialog QPushButton#saveUpdateApply:enabled { border: 2px solid #e4c36c; }
"""


if _PYSIDE_IMPORT_ERROR is None:

    class SaveUpdateDialog(QDialog):
        """Lists saves with their update decision; writes only the ticked ones."""

        def __init__(
            self,
            plans_provider: Callable[[], Sequence[SaveUpdatePlan]],
            saves_folder: Path,
            target_text: str,
            parent=None,
        ):
            super().__init__(parent)
            self.setObjectName("saveUpdateDialog")
            self.setWindowTitle("Update Saves")
            self.setStyleSheet(_DIALOG_STYLE)
            self.resize(980, 620)
            self._plans_provider = plans_provider
            self._saves_folder = saves_folder
            self.plans: tuple[SaveUpdatePlan, ...] = ()
            self.written: list[Path] = []

            layout = QVBoxLayout(self)
            intro = QLabel(INTRO_TEXT)
            intro.setWordWrap(True)
            layout.addWidget(intro)
            target = QLabel(target_text)
            target.setWordWrap(True)
            target.setObjectName("saveUpdateTarget")
            layout.addWidget(target)

            self.tree = QTreeWidget()
            self.tree.setObjectName("saveUpdateList")
            self.tree.setColumnCount(3)
            self.tree.setHeaderLabels(("Save", "Game", "Status"))
            self.tree.setRootIsDecorated(False)
            self.tree.setAlternatingRowColors(True)
            self.tree.setUniformRowHeights(True)
            header = self.tree.header()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self.tree.setColumnWidth(0, 300)
            self.tree.setColumnWidth(1, 240)
            self.tree.itemChanged.connect(self._item_changed)
            self.tree.currentItemChanged.connect(self._show_details)
            layout.addWidget(self.tree, 3)

            self.details = QLabel()
            self.details.setObjectName("saveUpdateDetails")
            self.details.setWordWrap(True)
            self.details.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.details.setMinimumHeight(130)
            layout.addWidget(self.details, 1)

            self.counts = QLabel()
            layout.addWidget(self.counts)

            buttons = QHBoxLayout()
            self.open_folder_button = QPushButton("Open Saves Folder")
            self.open_folder_button.clicked.connect(self._open_folder)
            buttons.addWidget(self.open_folder_button)
            self.refresh_button = QPushButton("Refresh")
            self.refresh_button.clicked.connect(self.refresh)
            buttons.addWidget(self.refresh_button)
            buttons.addStretch(1)
            self.apply_button = QPushButton("Update Selected Saves")
            self.apply_button.setObjectName("saveUpdateApply")
            self.apply_button.clicked.connect(self.apply)
            buttons.addWidget(self.apply_button)
            close = QPushButton("Close")
            close.clicked.connect(self.reject)
            buttons.addWidget(close)
            layout.addLayout(buttons)
            self.refresh()

        # ------------------------------------------------------------------
        def refresh(self) -> None:
            self.plans = tuple(sorted(self._plans_provider(),
                                      key=lambda plan: (_STATE_ORDER[plan.state], plan.path.name.casefold())))
            self.tree.blockSignals(True)
            self.tree.clear()
            for plan in self.plans:
                status = (STATUS_TEXT[plan.state] if plan.state is SaveState.CURRENT
                          else f"{STATUS_TEXT[plan.state]} - {plan.summary}")
                item = QTreeWidgetItem((plan.path.stem, plan.quest_name, status))
                item.setData(0, Qt.ItemDataRole.UserRole, plan)
                item.setToolTip(2, plan.summary)
                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                if plan.selectable:
                    item.setFlags(flags | Qt.ItemFlag.ItemIsUserCheckable)
                    # Nothing is ticked for the player: each update is a choice.
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    item.setFlags(flags)
                    for column in range(3):
                        item.setForeground(column, Qt.GlobalColor.gray)
                self.tree.addTopLevelItem(item)
            self.tree.blockSignals(False)
            self.counts.setText(counts_text(self.plans))
            if self.tree.topLevelItemCount():
                self.tree.setCurrentItem(self.tree.topLevelItem(0))
            else:
                self.details.setText("No saves were found in " + str(self._saves_folder))
            self._update_apply()

        def selected_plans(self) -> tuple[SaveUpdatePlan, ...]:
            chosen = []
            for index in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(index)
                plan = item.data(0, Qt.ItemDataRole.UserRole)
                if plan.selectable and item.checkState(0) == Qt.CheckState.Checked:
                    chosen.append(plan)
            return tuple(chosen)

        def apply(self) -> None:
            chosen = self.selected_plans()
            if not chosen:
                return
            cautioned = [plan for plan in chosen if plan.cautions]
            if cautioned:
                listing = "\n".join(f"• {plan.path.stem}: {plan.cautions[0]}" for plan in cautioned[:8])
                more = f"\n…and {len(cautioned) - 8} more." if len(cautioned) > 8 else ""
                answer = QMessageBox.question(
                    self, "Update Saves",
                    "Some selected saves have cautions:\n\n" + listing + more
                    + "\n\nThe originals stay as they are either way. Update these saves too?",
                )
                if answer != QMessageBox.StandardButton.Yes:
                    return
            written, failed = [], []
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                for plan in chosen:
                    try:
                        written.append(write_updated_copy(plan))
                    except SaveUpdateError as exc:
                        failed.append(str(exc))
            finally:
                QApplication.restoreOverrideCursor()
            self.written.extend(written)
            message = []
            if written:
                message.append("Updated copies written:\n" + "\n".join(f"• {path.name}" for path in written))
                message.append("Load those in the game. The original saves were not changed.")
            if failed:
                message.append("Not written:\n" + "\n".join(f"• {text}" for text in failed))
            (QMessageBox.warning if failed else QMessageBox.information)(
                self, "Update Saves", "\n\n".join(message))
            self.refresh()

        # ------------------------------------------------------------------
        def _item_changed(self, _item, _column) -> None:
            self._update_apply()

        def _update_apply(self) -> None:
            count = len(self.selected_plans())
            self.apply_button.setEnabled(count > 0)
            self.apply_button.setText("Update Selected Saves" if count == 0
                                      else f"Update {count} Selected Save{'s' if count != 1 else ''}")

        def _show_details(self, current, _previous) -> None:
            plan = current.data(0, Qt.ItemDataRole.UserRole) if current is not None else None
            self.details.setText(plan_details(plan) if plan is not None else "")

        def _open_folder(self) -> None:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._saves_folder))):
                QMessageBox.warning(self, "Update Saves", f"Could not open {self._saves_folder}")

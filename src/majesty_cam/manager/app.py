"""Qt Widgets shell for the Majesty Mod Manager.

The UI intentionally stays thin: discovery, selection policy, composition,
QOL preflight, and process launch all remain owned by :class:`ManagerController`.
PySide6 is imported defensively so the command-line merger continues to work in
environments where the optional desktop runtime has not been bundled yet.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from pathlib import Path
import sys
import traceback
from typing import Callable, Iterable, Optional

from .catalog import CatalogEntry, CatalogKind, CatalogSource, IssueSeverity
from .brand_assets import BrandAssets, ensure_brand_assets
from .controller import ControllerSnapshot, ManagerController
from .preflight import PreparedMergeMod
from .workshop import open_workshop_item


try:  # Keep non-GUI merger imports usable without the optional Qt runtime.
    from PySide6.QtCore import (
        QObject,
        QRunnable,
        QSize,
        QThreadPool,
        QTimer,
        Qt,
        Signal,
        Slot,
    )
    from PySide6.QtGui import (
        QColor,
        QCloseEvent,
        QFont,
        QIcon,
        QKeySequence,
        QPainter,
        QPixmap,
        QShortcut,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QProgressBar,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - depends on the packaged runtime.
    _PYSIDE_IMPORT_ERROR: Optional[ImportError] = exc
else:
    _PYSIDE_IMPORT_ERROR = None


APP_NAME = "Majesty Mod Manager"
APP_VERSION = "Proof of Concept"
APP_USER_MODEL_ID = "MajestyGoldHD.ModManager"
PHANTOMS_HAUNT_ID = "8c48289e-7c70-4426-8913-133f3544a182"
_MANAGER_ICON_PATH = Path(__file__).with_name("assets") / "manager-icon.ico"
_REQUIRED_QOL_HELPERS = (
    ("visitor", "Generic Visitor Lists"),
    ("remember", "Remember Active Mods"),
)


def _set_windows_app_user_model_id() -> None:
    """Give the manager a stable taskbar identity separate from Majesty itself."""

    if sys.platform != "win32":
        return
    try:
        setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        setter(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        # Older/embedded Windows hosts may not expose the shell API.  Qt's
        # explicit window icon still keeps the manager visually distinct.
        return


def _manager_icon() -> "QIcon":
    """Load the bundled manager icon used by Qt and the packaged executable."""

    return QIcon(str(_MANAGER_ICON_PATH))


@dataclass(frozen=True)
class _LegacyQolUtility:
    """Temporary view over the original two-item QOL status tuple."""

    key: str
    name: str
    description: str
    status: str
    detail: str
    required_for_manager: bool = True
    can_install: bool = False
    can_remove: bool = False


if _PYSIDE_IMPORT_ERROR is None:

    class _ElidingLabel(QLabel):
        """Keep long install paths readable without forcing the window wider."""

        def __init__(self, text: str = "", parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self._full_text = text
            self.setToolTip(text)
            self._update_text()

        def setFullText(self, text: str) -> None:
            self._full_text = text
            self.setToolTip(text)
            self._update_text()

        def resizeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
            super().resizeEvent(event)
            self._update_text()

        def _update_text(self) -> None:
            width = max(30, self.contentsRect().width())
            elided = self.fontMetrics().elidedText(
                self._full_text,
                Qt.TextElideMode.ElideMiddle,
                width,
            )
            super().setText(elided)


    class _BrandedHeader(QFrame):
        """Header which can use locally extracted stock texture when available."""

        def __init__(self, texture_path: Optional[Path] = None) -> None:
            super().__init__()
            self._texture = QPixmap(str(texture_path)) if texture_path else QPixmap()

        def paintEvent(self, event) -> None:  # type: ignore[no-untyped-def]
            super().paintEvent(event)
            if self._texture.isNull():
                return
            painter = QPainter(self)
            painter.setOpacity(0.42)
            cover = self._texture.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                (self.width() - cover.width()) // 2,
                (self.height() - cover.height()) // 2,
                cover,
            )
            painter.setOpacity(1.0)
            painter.fillRect(self.rect(), QColor(18, 14, 9, 150))


    class _SteamButton(QPushButton):
        """Compact Steam Workshop link using the canonical Steam icon."""

        def __init__(self, mod_name: str, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self.setObjectName("steamLinkButton")
            self.setFixedSize(28, 28)
            icon_path = Path(__file__).with_name("assets") / "steam.svg"
            self.setIcon(QIcon(str(icon_path)))
            self.setIconSize(QSize(22, 22))
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setAccessibleName(f"Open {mod_name} on Steam")
            self.setToolTip(f"Open {mod_name}'s Steam Workshop page")


    class _TaskSignals(QObject):
        result = Signal(object)
        error = Signal(str, str)
        progress = Signal(str)
        finished = Signal()


    class _ControllerTask(QRunnable):
        """Run one controller boundary without blocking Qt's event loop."""

        def __init__(self, action: Callable[[Callable[[str], None]], object]) -> None:
            super().__init__()
            self.action = action
            self.signals = _TaskSignals()

        @Slot()
        def run(self) -> None:
            try:
                result = self.action(self.signals.progress.emit)
            except Exception as exc:  # The UI is the controller's error boundary.
                self.signals.error.emit(str(exc) or type(exc).__name__, traceback.format_exc())
            else:
                self.signals.result.emit(result)
            finally:
                self.signals.finished.emit()


    class _ModCard(QFrame):
        selection_changed = Signal(str, bool)
        steam_requested = Signal(str)

        def __init__(
            self,
            entry: CatalogEntry,
            *,
            selected: bool,
            prepared: Optional[PreparedMergeMod],
            blocked_preflight: Optional[PreparedMergeMod],
            parent: Optional[QWidget] = None,
        ) -> None:
            super().__init__(parent)
            self.entry = entry
            self.prepared = prepared or blocked_preflight
            self.setObjectName("modCard")
            self.setProperty("kind", entry.kind.value)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

            tool_delivery = bool(getattr(entry, "tool_delivery", False))
            deep_invalid = bool(blocked_preflight and not blocked_preflight.ready)
            invalid_merge = entry.kind is CatalogKind.MERGE and not entry.generated and (
                not entry.selectable or deep_invalid
            )
            if invalid_merge:
                state = "invalid"
            elif tool_delivery:
                state = "tool"
            elif entry.generated or not entry.selectable:
                state = "disabled"
            elif selected:
                state = "active"
            else:
                state = "ready"
            self.setProperty("state", state)

            outer = QHBoxLayout(self)
            outer.setContentsMargins(17, 14, 17, 14)
            outer.setSpacing(14)

            if entry.kind is CatalogKind.QUEST:
                marker = QLabel("Q")
                marker.setObjectName("questMarker")
                marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
                marker.setFixedSize(30, 30)
                marker.setToolTip("Quest catalog item — selected inside Majesty")
                outer.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)
            elif tool_delivery:
                marker = QLabel("i")
                marker.setObjectName("toolMarker")
                marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
                marker.setFixedSize(30, 30)
                marker.setToolTip(
                    "This is a separate modding tool, not something Majesty turns on."
                )
                outer.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)
            else:
                check = QCheckBox()
                check.setAccessibleName(f"Enable {entry.display_name}")
                check.setCursor(Qt.CursorShape.PointingHandCursor)
                check.setChecked(bool(selected and entry.selectable and not deep_invalid))
                check.setEnabled(entry.selectable and not deep_invalid)
                check.setToolTip(
                    "Included in your launch setup"
                    if check.isEnabled()
                    else "This item cannot be selected safely"
                )
                check.stateChanged.connect(
                    lambda value, content_id=entry.content_id: self._emit_selection(
                        content_id,
                        value == Qt.CheckState.Checked.value,
                    )
                )
                outer.addWidget(check, 0, Qt.AlignmentFlag.AlignTop)

            body = QVBoxLayout()
            body.setSpacing(6)
            outer.addLayout(body, 1)

            heading = QHBoxLayout()
            heading.setSpacing(8)
            name = QLabel(entry.display_name)
            name.setObjectName("modName")
            name.setProperty("invalid", invalid_merge)
            name.setWordWrap(False)
            name.setMinimumWidth(260)
            name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            name.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            heading.addWidget(name)

            if self.prepared is not None and self.prepared.badge:
                badge = QLabel("SUPPORTED")
                badge.setObjectName("compatibilityBadge")
                badge.setToolTip(self.prepared.badge)
                badge.setFixedHeight(21)
                badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                heading.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
            elif entry.compatibility_applied:
                badge = QLabel("COMPATIBLE")
                badge.setObjectName("compatibilityBadge")
                badge.setToolTip(
                    "The manager knows how to combine this version safely."
                )
                badge.setFixedHeight(21)
                badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                heading.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

            heading.addStretch(1)

            status = QLabel(
                _status_text(
                    entry,
                    invalid_merge=invalid_merge,
                    tool_delivery=tool_delivery,
                )
            )
            status.setObjectName("cardStatus")
            status.setProperty("tone", "danger" if invalid_merge else "normal")
            heading.addWidget(status)

            workshop_item_id = str(
                getattr(entry, "workshop_item_id", "") or ""
            ).strip()
            if workshop_item_id:
                steam_button = _SteamButton(entry.display_name)
                steam_button.clicked.connect(
                    lambda _checked=False, item_id=workshop_item_id: (
                        self.steam_requested.emit(item_id)
                    )
                )
                heading.addWidget(steam_button, 0, Qt.AlignmentFlag.AlignVCenter)
            body.addLayout(heading)

            metadata = QHBoxLayout()
            metadata.setSpacing(8)
            source = QLabel(_source_text(entry.source))
            source.setObjectName("sourceBadge")
            metadata.addWidget(source)

            kind = QLabel(_kind_text(entry, tool_delivery=tool_delivery))
            kind.setObjectName("kindBadge")
            kind.setProperty("catalogKind", entry.kind.value)
            metadata.addWidget(kind)
            source.setToolTip(str(entry.manifest_path))
            metadata.addStretch(1)
            body.addLayout(metadata)

            messages = [_player_issue_text(issue.code, issue.message) for issue in entry.issues]
            if blocked_preflight is not None:
                messages.extend(
                    _player_issue_text(issue.code, issue.message)
                    for issue in blocked_preflight.issues
                )
            if _is_phantoms_haunt(entry):
                messages.insert(
                    0,
                    "If included, Phantom's Haunt uses the manager's improved version "
                    "so Majesty's original Elf Guild remains unchanged.",
                )
            if entry.kind is CatalogKind.QUEST and not messages:
                messages.append(
                    "Choose this adventure from Majesty's quest screen after launch."
                )
            if messages:
                detail = QLabel("  •  ".join(dict.fromkeys(messages)))
                detail.setObjectName("cardDetail")
                detail.setProperty("tone", "danger" if invalid_merge else "muted")
                detail.setWordWrap(True)
                body.addWidget(detail)

            self.search_text = " ".join(
                (
                    entry.display_name,
                    entry.content_id or entry.raw_content_id or "",
                    entry.source.value,
                    entry.kind.value,
                    " ".join(messages),
                    self.prepared.badge if self.prepared and self.prepared.badge else "",
                )
            ).casefold()

        def _emit_selection(self, content_id: Optional[str], enabled: bool) -> None:
            if content_id:
                self.selection_changed.emit(content_id, enabled)


    class _CatalogPage(QWidget):
        bulk_selection = Signal(object, bool)
        selection_changed = Signal(str, bool)
        steam_requested = Signal(str)

        def __init__(self, kind: CatalogKind, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self.kind = kind
            self.cards: list[_ModCard] = []

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            toolbar = QFrame()
            toolbar.setObjectName("catalogToolbar")
            bar = QHBoxLayout(toolbar)
            bar.setContentsMargins(18, 13, 18, 13)
            bar.setSpacing(9)

            description = QLabel(_section_description(kind))
            description.setObjectName("sectionDescription")
            description.setWordWrap(True)
            bar.addWidget(description, 1)

            self.select_all_button: Optional[QPushButton] = None
            self.clear_button: Optional[QPushButton] = None
            if kind is not CatalogKind.QUEST:
                self.select_all_button = QPushButton("Select All")
                self.select_all_button.setProperty("role", "quiet")
                self.select_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
                self.select_all_button.clicked.connect(
                    lambda _checked=False: self.bulk_selection.emit(self.kind, True)
                )
                bar.addWidget(self.select_all_button)

                self.clear_button = QPushButton("Clear")
                self.clear_button.setProperty("role", "quiet")
                self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
                self.clear_button.clicked.connect(
                    lambda _checked=False: self.bulk_selection.emit(self.kind, False)
                )
                bar.addWidget(self.clear_button)
            else:
                quest_note = QLabel("CHOOSE IN MAJESTY")
                quest_note.setObjectName("neutralBadge")
                quest_note.setToolTip(
                    "Choose quests from Majesty's quest screen after you launch."
                )
                bar.addWidget(quest_note)
            layout.addWidget(toolbar)

            self.scroll = QScrollArea()
            self.scroll.setObjectName("catalogScroll")
            self.scroll.setWidgetResizable(True)
            self.scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.host = QWidget()
            self.host.setObjectName("catalogHost")
            self.card_layout = QVBoxLayout(self.host)
            self.card_layout.setContentsMargins(18, 17, 18, 22)
            self.card_layout.setSpacing(10)
            self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.empty = QLabel("No content detected in this section.")
            self.empty.setObjectName("emptyState")
            self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_layout.addWidget(self.empty)
            self.card_layout.addStretch(1)
            self.scroll.setWidget(self.host)
            layout.addWidget(self.scroll, 1)

        def populate(
            self,
            entries: Iterable[CatalogEntry],
            snapshot: ControllerSnapshot,
            prepared: dict[str, PreparedMergeMod],
            blocked: dict[str, PreparedMergeMod],
        ) -> None:
            while self.card_layout.count():
                item = self.card_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self.cards = []

            for entry in entries:
                item = prepared.get(entry.content_id or "")
                blocked_item = blocked.get(entry.content_id or "")
                card = _ModCard(
                    entry,
                    selected=bool(
                        entry.content_id
                        and snapshot.selections.get(entry.content_id, False)
                    ),
                    prepared=item,
                    blocked_preflight=blocked_item,
                )
                card.selection_changed.connect(self.selection_changed.emit)
                card.steam_requested.connect(self.steam_requested.emit)
                self.card_layout.addWidget(card)
                self.cards.append(card)

            self.empty = QLabel(
                "No content detected in this section."
                if self.cards
                else _empty_text(self.kind)
            )
            self.empty.setObjectName("emptyState")
            self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.empty.setVisible(not self.cards)
            self.card_layout.addWidget(self.empty)
            self.card_layout.addStretch(1)

        def filter(self, text: str) -> None:
            query = text.strip().casefold()
            visible = 0
            for card in self.cards:
                match = not query or query in card.search_text
                card.setVisible(match)
                visible += int(match)
            self.empty.setText(
                "No matching content."
                if self.cards and query
                else _empty_text(self.kind)
            )
            self.empty.setVisible(visible == 0)

        def set_interactions_enabled(self, enabled: bool) -> None:
            if self.select_all_button is not None:
                self.select_all_button.setEnabled(enabled)
            if self.clear_button is not None:
                self.clear_button.setEnabled(enabled)


    class _QolCard(QFrame):
        change_requested = Signal(str, bool)

        def __init__(self, utility: object, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self.utility = utility
            self.key = str(getattr(utility, "key", ""))
            self.can_install = bool(getattr(utility, "can_install", False))
            self.can_remove = bool(getattr(utility, "can_remove", False))
            required = bool(getattr(utility, "required_for_manager", False))
            status = str(getattr(utility, "status", "error")).casefold()

            self.setObjectName("qolCard")
            self.setProperty("state", status)
            outer = QHBoxLayout(self)
            outer.setContentsMargins(17, 15, 17, 15)
            outer.setSpacing(14)

            emblem = QLabel("Q")
            emblem.setObjectName("qolMarker")
            emblem.setAlignment(Qt.AlignmentFlag.AlignCenter)
            emblem.setFixedSize(34, 34)
            outer.addWidget(emblem, 0, Qt.AlignmentFlag.AlignTop)

            body = QVBoxLayout()
            body.setSpacing(6)
            outer.addLayout(body, 1)

            heading = QHBoxLayout()
            heading.setSpacing(8)
            name = QLabel(str(getattr(utility, "name", self.key or "Utility")))
            name.setObjectName("modName")
            name.setWordWrap(False)
            name.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            heading.addWidget(name, 0, Qt.AlignmentFlag.AlignVCenter)

            status_badge = QLabel(_qol_status_text(status))
            status_badge.setObjectName("qolStatusBadge")
            status_badge.setProperty("state", status)
            status_badge.setFixedHeight(21)
            status_badge.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Fixed,
            )
            status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            heading.addWidget(status_badge, 0, Qt.AlignmentFlag.AlignVCenter)

            if required:
                required_badge = QLabel("REQUIRED FOR THE MANAGER")
                required_badge.setObjectName("requiredBadge")
                required_badge.setFixedHeight(21)
                required_badge.setSizePolicy(
                    QSizePolicy.Policy.Fixed,
                    QSizePolicy.Policy.Fixed,
                )
                required_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                heading.addWidget(required_badge, 0, Qt.AlignmentFlag.AlignVCenter)

            heading.addStretch(1)

            self.action_button: Optional[QPushButton] = None
            if self.can_install:
                self.action_button = QPushButton("Install")
                self.action_button.setProperty("role", "outline")
                self.action_button.clicked.connect(
                    lambda _checked=False: self.change_requested.emit(self.key, True)
                )
            elif self.can_remove:
                self.action_button = QPushButton("Remove")
                self.action_button.setProperty("role", "quiet")
                self.action_button.clicked.connect(
                    lambda _checked=False: self.change_requested.emit(self.key, False)
                )
            if self.action_button is not None:
                self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
                heading.addWidget(
                    self.action_button,
                    0,
                    Qt.AlignmentFlag.AlignVCenter,
                )
            body.addLayout(heading)

            description = QLabel(str(getattr(utility, "description", "")))
            description.setObjectName("qolDescription")
            description.setWordWrap(True)
            body.addWidget(description)

            self.search_text = " ".join(
                (
                    self.key,
                    str(getattr(utility, "name", "")),
                    str(getattr(utility, "description", "")),
                    status,
                )
            ).casefold()

        def set_action_enabled(self, enabled: bool) -> None:
            if self.action_button is not None:
                self.action_button.setEnabled(enabled)


    class _QolPage(QWidget):
        change_requested = Signal(str, bool)
        batch_requested = Signal(object, bool)

        def __init__(self, parent: Optional[QWidget] = None) -> None:
            super().__init__(parent)
            self.cards: list[_QolCard] = []
            self._install_keys: tuple[str, ...] = ()
            self._remove_keys: tuple[str, ...] = ()

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            toolbar = QFrame()
            toolbar.setObjectName("catalogToolbar")
            bar = QHBoxLayout(toolbar)
            bar.setContentsMargins(18, 13, 18, 13)
            bar.setSpacing(9)
            description = QLabel(
                "Helpful game improvements detected for this Majesty version. "
                "Required helpers keep your saved choices and combined mods working."
            )
            description.setObjectName("sectionDescription")
            description.setWordWrap(True)
            bar.addWidget(description, 1)

            self.install_all_button = QPushButton("Install All")
            self.install_all_button.setProperty("role", "outline")
            self.install_all_button.clicked.connect(self._install_all)
            bar.addWidget(self.install_all_button)
            self.remove_optional_button = QPushButton("Remove Optional")
            self.remove_optional_button.setProperty("role", "quiet")
            self.remove_optional_button.clicked.connect(self._remove_optional)
            bar.addWidget(self.remove_optional_button)
            layout.addWidget(toolbar)

            self.scroll = QScrollArea()
            self.scroll.setObjectName("catalogScroll")
            self.scroll.setWidgetResizable(True)
            self.scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.host = QWidget()
            self.host.setObjectName("catalogHost")
            self.card_layout = QVBoxLayout(self.host)
            self.card_layout.setContentsMargins(18, 17, 18, 22)
            self.card_layout.setSpacing(10)
            self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.empty = QLabel("Checking available quality-of-life helpers…")
            self.empty.setObjectName("emptyState")
            self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_layout.addWidget(self.empty)
            self.card_layout.addStretch(1)
            self.scroll.setWidget(self.host)
            layout.addWidget(self.scroll, 1)

        def populate(self, utilities: Iterable[object]) -> None:
            while self.card_layout.count():
                item = self.card_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self.cards = []
            install_keys: list[str] = []
            remove_keys: list[str] = []
            for utility in sorted(utilities, key=_qol_sort_key):
                card = _QolCard(utility)
                card.change_requested.connect(self.change_requested.emit)
                self.card_layout.addWidget(card)
                self.cards.append(card)
                if card.can_install:
                    install_keys.append(card.key)
                if card.can_remove and not bool(
                    getattr(utility, "required_for_manager", False)
                ):
                    remove_keys.append(card.key)
            self._install_keys = tuple(install_keys)
            self._remove_keys = tuple(remove_keys)

            self.empty = QLabel(
                "No quality-of-life helpers were found for this Majesty version."
            )
            self.empty.setObjectName("emptyState")
            self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.empty.setVisible(not self.cards)
            self.card_layout.addWidget(self.empty)
            self.card_layout.addStretch(1)
            self.install_all_button.setEnabled(bool(self._install_keys))
            self.remove_optional_button.setEnabled(bool(self._remove_keys))

        def filter(self, text: str) -> None:
            query = text.strip().casefold()
            visible = 0
            for card in self.cards:
                match = not query or query in card.search_text
                card.setVisible(match)
                visible += int(match)
            self.empty.setText(
                "No matching helpers."
                if self.cards and query
                else "No quality-of-life helpers were found for this Majesty version."
            )
            self.empty.setVisible(visible == 0)

        def set_interactions_enabled(self, enabled: bool) -> None:
            self.install_all_button.setEnabled(enabled and bool(self._install_keys))
            self.remove_optional_button.setEnabled(enabled and bool(self._remove_keys))
            for card in self.cards:
                card.set_action_enabled(enabled)

        def _install_all(self) -> None:
            if self._install_keys:
                self.batch_requested.emit(self._install_keys, True)

        def _remove_optional(self) -> None:
            if self._remove_keys:
                self.batch_requested.emit(self._remove_keys, False)


    class ManagerWindow(QMainWindow):
        """The user-facing manager shell backed by one ManagerController."""

        steam_requested = Signal(str)

        def __init__(self, controller: Optional[ManagerController] = None) -> None:
            super().__init__()
            manager_icon = _manager_icon()
            if not manager_icon.isNull():
                self.setWindowIcon(manager_icon)
            self.controller = controller or ManagerController()
            self.snapshot: Optional[ControllerSnapshot] = None
            self.prepared_cache: dict[str, PreparedMergeMod] = {}
            self.blocked_cache: dict[str, PreparedMergeMod] = {}
            self._workers: set[_ControllerTask] = set()
            self._busy = False
            self._task_name = ""
            self._initial_qol_check_complete = False
            self.steam_requested.connect(self._open_workshop_item)

            try:
                self.brand_assets = ensure_brand_assets(
                    self.controller.paths.game_path,
                    self.controller.paths.profile_path.parent / "theme",
                )
            except Exception as exc:
                self.brand_assets = BrandAssets(None, None, None, (str(exc),))

            self.setWindowTitle(APP_NAME)
            self.setMinimumSize(980, 640)
            self.resize(1180, 760)
            self.setObjectName("managerWindow")
            self._build_ui()
            self._load_theme()

            QShortcut(QKeySequence.StandardKey.Find, self, activated=self.search.setFocus)
            QShortcut(QKeySequence("F5"), self, activated=self.scan)
            QTimer.singleShot(0, self.scan)

        def _build_ui(self) -> None:
            root = QWidget()
            root.setObjectName("appRoot")
            self.setCentralWidget(root)
            page = QVBoxLayout(root)
            page.setContentsMargins(0, 0, 0, 0)
            page.setSpacing(0)

            header = _BrandedHeader(self.brand_assets.header_texture)
            header.setObjectName("appHeader")
            header_layout = QHBoxLayout(header)
            header_layout.setContentsMargins(24, 18, 24, 16)
            header_layout.setSpacing(15)

            crest = QLabel("M")
            crest.setObjectName("crest")
            crest.setAlignment(Qt.AlignmentFlag.AlignCenter)
            crest.setFixedSize(48, 48)
            if self.brand_assets.icon:
                game_icon = QIcon(str(self.brand_assets.icon))
                if not game_icon.isNull():
                    crest.setPixmap(game_icon.pixmap(42, 42))
                    crest.setObjectName("crestImage")
            header_layout.addWidget(crest)

            titles = QVBoxLayout()
            titles.setSpacing(1)
            eyebrow = QLabel("MAJESTY GOLD HD")
            eyebrow.setObjectName("eyebrow")
            titles.addWidget(eyebrow)
            title = QLabel(APP_NAME)
            title.setObjectName("appTitle")
            titles.addWidget(title)
            tagline = QLabel("Choose your adventures, mods, and game helpers")
            tagline.setObjectName("tagline")
            titles.addWidget(tagline)
            header_layout.addLayout(titles)
            header_layout.addStretch(1)

            game_version = QVBoxLayout()
            game_version.setSpacing(3)
            version_label = QLabel("GAME VERSION")
            version_label.setObjectName("microLabel")
            game_version.addWidget(version_label)
            self.game_build = QLabel("Checking…")
            self.game_build.setObjectName("gameBuild")
            self.game_build.setProperty("state", "pending")
            game_version.addWidget(self.game_build)
            header_layout.addLayout(game_version)

            install = QVBoxLayout()
            install.setSpacing(3)
            install_label = QLabel("GAME INSTALL")
            install_label.setObjectName("microLabel")
            install.addWidget(install_label)
            self.install_path = _ElidingLabel(str(self.controller.paths.game_path))
            self.install_path.setObjectName("installPath")
            self.install_path.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self.install_path.setMinimumWidth(140)
            self.install_path.setMaximumWidth(260)
            self.install_path.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            install.addWidget(self.install_path)
            header_layout.addLayout(install)

            self.rescan_button = QPushButton("Rescan")
            self.rescan_button.setProperty("role", "outline")
            self.rescan_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.rescan_button.setToolTip("Rescan installed mods and quests (F5)")
            self.rescan_button.clicked.connect(self.scan)
            header_layout.addWidget(self.rescan_button)
            page.addWidget(header)

            navigation = QFrame()
            navigation.setObjectName("navigationBar")
            nav = QHBoxLayout(navigation)
            nav.setContentsMargins(20, 10, 20, 10)
            nav.setSpacing(14)
            self.search = QLineEdit()
            self.search.setObjectName("catalogSearch")
            self.search.setPlaceholderText("Search installed content…")
            self.search.setClearButtonEnabled(True)
            self.search.setMaximumWidth(360)
            self.search.textChanged.connect(self._filter_pages)
            nav.addWidget(self.search)
            nav.addStretch(1)
            self.selection_note = QLabel("Scanning installed content…")
            self.selection_note.setObjectName("selectionNote")
            nav.addWidget(self.selection_note)
            page.addWidget(navigation)

            self.notice_bar = QFrame()
            self.notice_bar.setObjectName("noticeBar")
            notice_layout = QHBoxLayout(self.notice_bar)
            notice_layout.setContentsMargins(18, 8, 18, 8)
            self.notice_text = QLabel()
            self.notice_text.setObjectName("noticeText")
            self.notice_text.setWordWrap(True)
            notice_layout.addWidget(self.notice_text, 1)
            notice_dismiss = QPushButton("Dismiss")
            notice_dismiss.setProperty("role", "quiet")
            notice_dismiss.clicked.connect(self.notice_bar.hide)
            notice_layout.addWidget(notice_dismiss)
            self.notice_bar.hide()
            page.addWidget(self.notice_bar)

            self.tabs = QTabWidget()
            self.tabs.setObjectName("catalogTabs")
            self.pages: dict[CatalogKind, _CatalogPage] = {}
            for kind, label in (
                (CatalogKind.MERGE, "Merge"),
                (CatalogKind.STANDARD, "Standard"),
                (CatalogKind.QUEST, "Quests"),
            ):
                catalog_page = _CatalogPage(kind)
                catalog_page.bulk_selection.connect(self._bulk_selection)
                catalog_page.selection_changed.connect(self._selection_changed)
                catalog_page.steam_requested.connect(self.steam_requested.emit)
                self.pages[kind] = catalog_page
                self.tabs.addTab(catalog_page, label)
            self.qol_page = _QolPage()
            self.qol_page.change_requested.connect(self._change_qol)
            self.qol_page.batch_requested.connect(self._change_qol_batch)
            self.tabs.addTab(self.qol_page, "Quality of Life")
            page.addWidget(self.tabs, 1)

            footer = QFrame()
            footer.setObjectName("stickyFooter")
            footer_layout = QHBoxLayout(footer)
            footer_layout.setContentsMargins(22, 13, 22, 13)
            footer_layout.setSpacing(16)

            self.counts = QLabel("—")
            self.counts.setObjectName("footerPrimary")
            footer_layout.addWidget(self.counts, 1)

            activity = QVBoxLayout()
            activity.setSpacing(4)
            self.build_state = QLabel("Scanning installed content…")
            self.build_state.setObjectName("buildState")
            activity.addWidget(self.build_state)
            self.progress = QProgressBar()
            self.progress.setObjectName("managerProgress")
            self.progress.setRange(0, 0)
            self.progress.setTextVisible(False)
            self.progress.setFixedWidth(210)
            self.progress.hide()
            activity.addWidget(self.progress)
            footer_layout.addLayout(activity)

            self.build_button = QPushButton("Prepare Selected Mods")
            self.build_button.setObjectName("buildButton")
            self.build_button.setProperty("role", "outline")
            self.build_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.build_button.clicked.connect(self.build)
            self.build_button.setEnabled(False)
            footer_layout.addWidget(self.build_button)

            self.launch_button = QPushButton("Launch Majesty")
            self.launch_button.setObjectName("launchButton")
            self.launch_button.setProperty("role", "primary")
            self.launch_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.launch_button.clicked.connect(self.launch)
            self.launch_button.setEnabled(False)
            footer_layout.addWidget(self.launch_button)
            page.addWidget(footer)

        def _load_theme(self) -> None:
            theme_path = Path(__file__).with_name("theme.qss")
            try:
                stylesheet = theme_path.read_text(encoding="utf-8")
                check_icon = theme_path.with_name("assets") / "check.svg"
                stylesheet = stylesheet.replace(
                    "@CHECK_ICON@", check_icon.resolve().as_posix()
                )
                self.setStyleSheet(stylesheet)
            except OSError as exc:
                QMessageBox.warning(
                    self,
                    "Theme unavailable",
                    f"The manager could not load its theme:\n{exc}",
                )

        @Slot()
        def scan(self) -> None:
            if self._busy:
                return
            self.prepared_cache.clear()
            self.blocked_cache.clear()
            self._run_task(
                "Looking for installed content",
                lambda progress: self.controller.scan(),
                self._scan_finished,
            )

        @Slot()
        def build(self) -> None:
            if (
                self._busy
                or self.snapshot is None
                or not self.snapshot.can_build
                or _missing_required_qol_helpers(self.snapshot)
            ):
                return
            self._run_task(
                "Preparing your selected mods",
                lambda progress: self.controller.build(progress=progress),
                self._build_finished,
            )

        @Slot()
        def launch(self) -> None:
            if (
                self._busy
                or self.snapshot is None
                or not self.snapshot.can_launch
                or _missing_required_qol_helpers(self.snapshot)
            ):
                return

            def action(progress: Callable[[str], None]) -> object:
                progress("Checking required game helpers")
                return self.controller.launch()

            self._run_task("Launching Majesty", action, self._launch_finished)

        def _change_qol(self, key: str, install: bool) -> None:
            if self._busy or not hasattr(self.controller, "change_qol"):
                return
            verb = "Installing" if install else "Removing"
            self._run_task(
                f"{verb} game helper",
                lambda progress: self.controller.change_qol(key, install),
                self._qol_changed,
            )

        def _change_qol_batch(self, raw_keys: object, install: bool) -> None:
            if self._busy or not hasattr(self.controller, "change_qol"):
                return
            keys = tuple(str(key) for key in raw_keys)  # type: ignore[union-attr]
            if not keys:
                return

            def action(progress: Callable[[str], None]) -> object:
                snapshot: object = self.snapshot
                for index, key in enumerate(keys, start=1):
                    verb = "Installing" if install else "Removing"
                    progress(f"{verb} helper {index} of {len(keys)}")
                    snapshot = self.controller.change_qol(key, install)
                return snapshot

            self._run_task(
                "Installing game helpers" if install else "Removing optional helpers",
                action,
                self._qol_changed,
            )

        def _run_task(
            self,
            name: str,
            action: Callable[[Callable[[str], None]], object],
            success: Callable[[object], None],
        ) -> None:
            self._set_busy(True, name)
            worker = _ControllerTask(action)
            self._workers.add(worker)
            worker.signals.progress.connect(self._progress_changed)
            worker.signals.result.connect(success)
            worker.signals.error.connect(self._task_failed)
            worker.signals.finished.connect(lambda task=worker: self._task_finished(task))
            QThreadPool.globalInstance().start(worker)

        @Slot(str)
        def _progress_changed(self, message: str) -> None:
            self.build_state.setText(_player_progress_text(message))

        @Slot(str, str)
        def _task_failed(self, message: str, details: str) -> None:
            self.build_state.setText(f"{self._task_name} failed")
            dialog = QMessageBox(self)
            dialog.setIcon(QMessageBox.Icon.Critical)
            dialog.setWindowTitle(f"{APP_NAME} — Error")
            dialog.setText(_player_error_text(message))
            dialog.setInformativeText(
                "If this happened while building, your last completed setup is still safe."
            )
            dialog.setDetailedText(details)
            dialog.exec()

        def _task_finished(self, worker: _ControllerTask) -> None:
            self._workers.discard(worker)
            self._set_busy(False)
            if self.snapshot is not None:
                self._render_snapshot(self.snapshot)

        def _scan_finished(self, value: object) -> None:
            snapshot = _require_snapshot(value)
            snapshot = self._capture_and_exclude_blocked(snapshot)
            self.snapshot = snapshot
            self._render_snapshot(snapshot)
            self._show_initial_required_qol_prompt(snapshot)

        def _show_initial_required_qol_prompt(
            self, snapshot: ControllerSnapshot
        ) -> None:
            """Direct the first-run check to missing launch prerequisites once."""

            if self._initial_qol_check_complete:
                return
            self._initial_qol_check_complete = True
            missing = _missing_required_qol_helpers(snapshot)
            if not missing:
                return

            self.tabs.setCurrentWidget(self.qol_page)
            helper_list = "\n".join(f"• {name}" for name in missing)
            QMessageBox.warning(
                self,
                "Required Quality of Life patches",
                "Majesty Mod Manager requires the following patches before you "
                "can Prepare Selected Mods or Launch Majesty:\n\n"
                f"{helper_list}\n\n"
                "Install them from this tab to continue.",
            )

        def _build_finished(self, value: object) -> None:
            try:
                result, snapshot = value  # type: ignore[misc]
            except (TypeError, ValueError) as exc:
                raise RuntimeError("Controller returned an invalid build result") from exc
            snapshot = _require_snapshot(snapshot)
            self.snapshot = snapshot
            self.build_state.setText("Your selected mods are ready")
            self._render_snapshot(snapshot)

        def _launch_finished(self, value: object) -> None:
            try:
                result, snapshot = value  # type: ignore[misc]
            except (TypeError, ValueError) as exc:
                raise RuntimeError("Controller returned an invalid launch result") from exc
            self.snapshot = _require_snapshot(snapshot)
            self.build_state.setText(f"Majesty started · process {result.launcher_pid}")
            self._render_snapshot(self.snapshot)

        def _qol_changed(self, value: object) -> None:
            self.snapshot = _require_snapshot(value)
            self._render_snapshot(self.snapshot)

        def _capture_and_exclude_blocked(
            self, snapshot: ControllerSnapshot
        ) -> ControllerSnapshot:
            """Keep deep preflight failures visible but outside the profile.

            Catalog validation catches the ordinary missing-contract case.  A
            selected package can still fail the stricter composer inventory;
            those inputs are cached for the red diagnostic card and deselected
            through the controller so they cannot poison every future build.
            """

            blocked = [item for item in snapshot.plan.selected_merge if not item.ready]
            for item in blocked:
                self.blocked_cache[item.content_id] = item
                if snapshot.selections.get(item.content_id, False):
                    snapshot = self.controller.set_selected(item.content_id, False)
            return snapshot

        def _selection_changed(self, content_id: str, enabled: bool) -> None:
            if self._busy:
                return
            try:
                snapshot = self.controller.set_selected(content_id, enabled)
                snapshot = self._capture_and_exclude_blocked(snapshot)
            except Exception as exc:
                self._show_interaction_error("Could not update selection", exc)
                return
            self.snapshot = snapshot
            self._render_snapshot(snapshot)

        def _bulk_selection(self, raw_kind: object, enabled: bool) -> None:
            if self._busy:
                return
            try:
                kind = raw_kind if isinstance(raw_kind, CatalogKind) else CatalogKind(raw_kind)
                snapshot = self.controller.select_all(kind, enabled)
                snapshot = self._capture_and_exclude_blocked(snapshot)
            except Exception as exc:
                self._show_interaction_error("Could not update selections", exc)
                return
            self.snapshot = snapshot
            self._render_snapshot(snapshot)

        def _show_interaction_error(self, title: str, exc: Exception) -> None:
            QMessageBox.critical(self, title, str(exc) or type(exc).__name__)

        @Slot(str)
        def _open_workshop_item(self, item_id: str) -> None:
            try:
                open_workshop_item(item_id)
            except (ValueError, OSError) as exc:
                self._show_interaction_error(
                    "Could not open Steam Workshop",
                    exc,
                )

        def _render_snapshot(self, snapshot: ControllerSnapshot) -> None:
            for item in snapshot.plan.selected_merge:
                self.prepared_cache[item.content_id] = item
                if item.ready:
                    self.blocked_cache.pop(item.content_id, None)

            entries_by_kind = {
                CatalogKind.STANDARD: tuple(
                    entry for entry in snapshot.catalog.standard if not entry.generated
                ),
                CatalogKind.QUEST: tuple(
                    entry for entry in snapshot.catalog.quests if not entry.generated
                ),
                CatalogKind.MERGE: tuple(
                    entry for entry in snapshot.catalog.merge if not entry.generated
                ),
            }
            for index, kind in enumerate(
                (CatalogKind.MERGE, CatalogKind.STANDARD, CatalogKind.QUEST)
            ):
                entries = entries_by_kind[kind]
                self.pages[kind].populate(
                    entries,
                    snapshot,
                    self.prepared_cache,
                    self.blocked_cache,
                )
                self.tabs.setTabText(index, f"{_tab_name(kind)}   {len(entries)}")
            utilities = _snapshot_qol_utilities(snapshot)
            self.qol_page.populate(utilities)
            self.tabs.setTabText(3, f"Quality of Life   {len(utilities)}")
            self._filter_pages(self.search.text())

            selected_standard = sum(
                1
                for entry in entries_by_kind[CatalogKind.STANDARD]
                if entry.content_id and snapshot.selections.get(entry.content_id, False)
            )
            selected_merge = sum(
                1
                for entry in entries_by_kind[CatalogKind.MERGE]
                if entry.content_id and snapshot.selections.get(entry.content_id, False)
            )
            self.counts.setText(
                f"{selected_standard} Standard  ·  {selected_merge} Merge  ·  "
                f"{len(entries_by_kind[CatalogKind.QUEST])} Quests found"
            )
            source_label = {
                "defaults": "Compatible mods are selected automatically",
                "remembered": "Your last Majesty mod choices are loaded",
                "manager": "Your saved choices are loaded",
            }.get(snapshot.selection_source, snapshot.selection_source)
            self.selection_note.setText(source_label)
            self.selection_note.setToolTip("")
            self._render_notices(snapshot)
            self._render_game_build(snapshot)
            self._render_build_state(snapshot)
            self._set_interactions_enabled(not self._busy)

        def _render_notices(self, snapshot: ControllerSnapshot) -> None:
            notices = tuple(
                _player_notice_text(item)
                for item in (*snapshot.notices, *self.brand_assets.issues)
            )
            if not notices:
                self.notice_bar.hide()
                return
            suffix = f"  (+{len(notices) - 1} more)" if len(notices) > 1 else ""
            self.notice_text.setText(notices[0] + suffix)
            self.notice_text.setToolTip("\n\n".join(notices))
            self.notice_bar.show()

        def _render_game_build(self, snapshot: ControllerSnapshot) -> None:
            if hasattr(snapshot, "game_build"):
                game_build = getattr(snapshot, "game_build")
                if game_build is None:
                    text, state = "Unsupported build", "danger"
                    tooltip = (
                        "This Majesty version is not yet supported by the Mod Manager."
                    )
                else:
                    version = getattr(game_build, "version", "")
                    label = str(game_build.display_name)
                    text, state = (
                        f"{label}  ·  {version}" if version else label,
                        "ready",
                    )
                    tooltip = f"Detected Majesty version {version}" if version else text
            else:
                text, state = "Majesty Gold HD", "pending"
                tooltip = "Game version details will appear after the version check."
            self.game_build.setText(text)
            self.game_build.setToolTip(tooltip)
            _set_dynamic_property(self.game_build, "state", state)

        def _render_build_state(self, snapshot: ControllerSnapshot) -> None:
            if self._busy:
                return
            required_qol_ready = not _missing_required_qol_helpers(snapshot)
            if snapshot.plan.issues:
                self.build_state.setText("One of your choices needs attention")
                self.build_state.setToolTip(
                    "\n".join(
                        _player_issue_text(issue.code, issue.message)
                        for issue in snapshot.plan.issues
                    )
                )
            elif not snapshot.plan.has_merge:
                self.build_state.setText("Ready — no combined setup is needed")
                self.build_state.setToolTip(
                    "Your selected Standard mods can be loaded as they are."
                )
            elif snapshot.build_required:
                self.build_state.setText("Prepare your selected Merge mods before launching")
                self.build_state.setToolTip(
                    "The manager needs to combine these mods into one playable setup."
                )
            else:
                self.build_state.setText("Your selected mods are ready")
                self.build_state.setToolTip(
                    str(snapshot.managed_build.output_root)
                    if snapshot.managed_build
                    else ""
                )

            self.build_button.setText(
                "Prepare Again"
                if snapshot.managed_build is not None
                else "Prepare Selected Mods"
            )
            self.build_button.setEnabled(snapshot.can_build and required_qol_ready)
            self.build_button.setToolTip(
                (
                    "Install the required patches on the Quality of Life tab first."
                    if not required_qol_ready
                    else "Combine the selected Merge mods into one setup Majesty can load."
                    if snapshot.plan.has_merge
                    else "Select at least one supported Merge mod to build a setup."
                )
            )
            self.launch_button.setEnabled(snapshot.can_launch and required_qol_ready)
            if not required_qol_ready:
                launch_tip = (
                    "Install the required patches on the Quality of Life tab first."
                )
            elif snapshot.can_launch:
                launch_tip = (
                    "Save these choices and start Majesty with support for combined mods."
                )
            elif snapshot.build_required:
                launch_tip = "Prepare the current Merge setup before launching."
            else:
                launch_tip = (
                    "Majesty or required launch files could not be found, or one of "
                    "your choices still needs attention."
                )
            self.launch_button.setToolTip(launch_tip)

        def _set_busy(self, busy: bool, message: str = "") -> None:
            self._busy = busy
            if message:
                self._task_name = message
                self.build_state.setText(message)
            self.progress.setVisible(busy)
            self.rescan_button.setEnabled(not busy)
            self.build_button.setEnabled(False if busy else self.build_button.isEnabled())
            self.launch_button.setEnabled(False if busy else self.launch_button.isEnabled())
            self._set_interactions_enabled(not busy)

        def _set_interactions_enabled(self, enabled: bool) -> None:
            self.search.setEnabled(enabled)
            for catalog_page in self.pages.values():
                catalog_page.set_interactions_enabled(enabled)
            self.qol_page.set_interactions_enabled(enabled)
            if not enabled:
                self.build_button.setEnabled(False)
                self.launch_button.setEnabled(False)

        @Slot(str)
        def _filter_pages(self, text: str) -> None:
            for catalog_page in self.pages.values():
                catalog_page.filter(text)
            self.qol_page.filter(text)

        def closeEvent(self, event: QCloseEvent) -> None:
            if self._busy:
                QMessageBox.information(
                    self,
                    APP_NAME,
                    "Please wait for the current check, build, or launch step to finish.",
                )
                event.ignore()
                return
            event.accept()


def _require_snapshot(value: object) -> "ControllerSnapshot":
    if not isinstance(value, ControllerSnapshot):
        raise RuntimeError("Controller returned an invalid snapshot")
    return value


def _source_text(source: "CatalogSource") -> str:
    return {
        CatalogSource.LOCAL_MODS: "LOCAL MODS",
        CatalogSource.LOCAL_QUESTS: "LOCAL QUESTS",
        CatalogSource.WORKSHOP: "STEAM WORKSHOP",
    }[source]


def _tab_name(kind: "CatalogKind") -> str:
    return {
        CatalogKind.STANDARD: "Standard",
        CatalogKind.QUEST: "Quests",
        CatalogKind.MERGE: "Merge",
    }[kind]


def _section_description(kind: "CatalogKind") -> str:
    return {
        CatalogKind.STANDARD: (
            "Mods Majesty can load on their own. Choose the ones you want active "
            "for your next game."
        ),
        CatalogKind.QUEST: (
            "Extra adventures and maps found on this computer. Choose one inside "
            "Majesty after launch."
        ),
        CatalogKind.MERGE: (
            "Mods that change the same parts of Majesty. The manager combines your "
            "choices into one playable setup. Red entries need an update first."
        ),
    }[kind]


def _empty_text(kind: "CatalogKind") -> str:
    return {
        CatalogKind.STANDARD: "No Standard mods detected.",
        CatalogKind.QUEST: "No extra quests or maps were detected.",
        CatalogKind.MERGE: "No mods that need combining were detected.",
    }[kind]


def _status_text(
    entry: "CatalogEntry", *, invalid_merge: bool, tool_delivery: bool = False
) -> str:
    if tool_delivery:
        return "TOOL ONLY — NOT A GAME MOD"
    if invalid_merge:
        return "CAN'T COMBINE YET"
    if any(issue.severity is IssueSeverity.ERROR for issue in entry.issues):
        return "NEEDS ATTENTION"
    if entry.kind is CatalogKind.QUEST:
        return "CHOOSE IN MAJESTY"
    if entry.kind is CatalogKind.MERGE:
        return "READY TO COMBINE"
    return "READY"


def _kind_text(entry: "CatalogEntry", *, tool_delivery: bool = False) -> str:
    if tool_delivery:
        return "TOOL"
    return {
        CatalogKind.STANDARD: "MOD",
        CatalogKind.QUEST: "QUEST",
        CatalogKind.MERGE: "COMBINE",
    }[entry.kind]


def _is_phantoms_haunt(entry: "CatalogEntry") -> bool:
    raw_id = entry.content_id or entry.raw_content_id or ""
    return str(raw_id).strip().strip("{}").casefold() == PHANTOMS_HAUNT_ID


def _player_issue_text(code: str, message: str) -> str:
    friendly = {
        "non_gameplay_tool_delivery": (
            "This Workshop item delivers a separate setup tool. It is listed for "
            "reference and is not turned on inside Majesty."
        ),
        "missing_merge_definition": (
            "This mod has not been prepared for safe combining yet. Ask its author "
            "for a Mod Manager compatibility update."
        ),
        "invalid_merge_definition": (
            "This mod's compatibility information is damaged or does not match "
            "the installed version."
        ),
        "legacy_merge_definition_requires_adapter": (
            "This mod uses an older compatibility format that cannot describe "
            "everything needed for safe combining. Its author must update it, "
            "or the Mod Manager must provide a trusted compatibility adapter."
        ),
        "package_preflight_failed": (
            "The manager could not verify all files this mod needs."
        ),
        "unsupported_runtime_capability": (
            "This mod needs a game feature the manager does not support yet."
        ),
        "unsafe_custom_text_binding": (
            "This mod changes in-game status text, but the manager could not "
            "safely connect every changed message to the script that uses it."
        ),
        "unsafe_private_activity_text": (
            "One or more selected mods change in-game status text in a way the "
            "manager cannot safely combine."
        ),
        "merge_preflight_error": (
            "The manager could not complete this mod's compatibility check."
        ),
        "duplicate_content_id": (
            "This item is installed more than once. Keep one copy, then rescan."
        ),
        "ambiguous_manifests": (
            "This download contains more than one mod entry, so it cannot be "
            "managed safely."
        ),
        "selected_item_not_ready": "This selected mod is not ready to use.",
        "duplicate_merge_alias": (
            "Two selected mods use the same internal name and cannot be combined."
        ),
        "conflicting_resolution_metadata": (
            "Two selected mods disagree about the same game behavior."
        ),
        "invalid_combination_resolution": (
            "The manager's compatibility fix for this combination could not be loaded."
        ),
        "duplicate_combination_resolution": (
            "More than one compatibility rule tries to resolve the same game "
            "behavior for this selection. The manager will not choose one by order."
        ),
    }.get(code)
    if friendly:
        return friendly
    return (
        message.replace("CAM", "game data")
        .replace("stock-relative", "based on the original game")
        .replace("mod-definition.json", "compatibility information")
        .replace("UUID", "mod ID")
        .replace("package", "mod")
    )


def _snapshot_qol_utilities(snapshot: "ControllerSnapshot") -> tuple[object, ...]:
    if hasattr(snapshot, "qol_utilities"):
        return tuple(getattr(snapshot, "qol_utilities"))
    result: list[object] = []
    for status in getattr(snapshot, "qol_status", ()):
        name = str(status.name)
        folded = name.casefold()
        if "visitor" in folded:
            key = "generic-visitor-lists"
            description = (
                "Keeps visitor lists working for buildings added by combined mods."
            )
        elif "remember" in folded or "persistence" in folded:
            key = "remember-active-mods"
            description = "Restores the exact mod choices saved by this manager."
        else:
            key = "-".join(part for part in folded.split() if part)
            description = "A helper used by the Majesty Mod Manager."
        state = "installed" if status.installed else (
            "available" if status.available else "error"
        )
        result.append(
            _LegacyQolUtility(
                key=key,
                name=name,
                description=description,
                status=state,
                detail=str(status.detail),
            )
        )
    return tuple(result)


def _missing_required_qol_helpers(
    snapshot: "ControllerSnapshot",
) -> tuple[str, ...]:
    """Return missing manager prerequisites in a stable, player-facing order."""

    required = tuple(
        item
        for item in _snapshot_qol_utilities(snapshot)
        if bool(getattr(item, "required_for_manager", False))
    )
    missing: list[str] = []
    matched_ids: set[int] = set()
    for marker, fallback_name in _REQUIRED_QOL_HELPERS:
        utility = next(
            (
                item
                for item in required
                if marker
                in (
                    f"{getattr(item, 'key', '')} "
                    f"{getattr(item, 'name', '')}"
                ).casefold()
            ),
            None,
        )
        if utility is None:
            missing.append(fallback_name)
            continue
        matched_ids.add(id(utility))
        if str(getattr(utility, "status", "")).casefold() != "installed":
            missing.append(str(getattr(utility, "name", fallback_name)))

    for utility in required:
        if (
            id(utility) not in matched_ids
            and str(getattr(utility, "status", "")).casefold() != "installed"
        ):
            missing.append(str(getattr(utility, "name", "Required patch")))
    return tuple(dict.fromkeys(missing))


def _qol_status_text(status: str) -> str:
    return {
        "installed": "INSTALLED",
        "available": "AVAILABLE",
        "missing": "NOT BUNDLED",
        "unsupported": "NOT SUPPORTED",
        "error": "NEEDS ATTENTION",
    }.get(status, status.replace("_", " ").upper())


def _qol_sort_key(utility: object) -> tuple[bool, str, str]:
    """Put optional patches first, alphabetically within both groups."""

    return (
        bool(getattr(utility, "required_for_manager", False)),
        str(getattr(utility, "name", "")).casefold(),
        str(getattr(utility, "key", "")).casefold(),
    )


def _required_qol_explanation(key: str) -> str:
    folded = key.casefold()
    if "visitor" in folded:
        return (
            "Required for combined building mods: it lets their visitor panels use "
            "Majesty's normal visitor-list behavior."
        )
    if "remember" in folded or "persistence" in folded:
        return (
            "Required for reliable launching: it restores the exact mod choices "
            "saved by this manager when Majesty starts."
        )
    return "Required so the Mod Manager can launch this setup reliably."


def _player_progress_text(message: str) -> str:
    return {
        "Validating selected packages": "Checking selected mods",
        "Merging CAM, Description, and GPL resources": "Combining selected mods",
        "Publishing validated profile": "Finishing your combined setup",
    }.get(message, _player_error_text(message))


def _player_notice_text(message: str) -> str:
    if "QOL preflight failed" in message:
        return "The manager could not check the installed game helpers."
    if "Could not extract" in message and "theme art" in message:
        return "Majesty theme art could not be prepared; the standard theme is in use."
    return _player_error_text(message)


def _player_error_text(message: str) -> str:
    return (
        str(message)
        .replace("CAM", "game data")
        .replace("GPL", "game script")
        .replace("stock-relative", "based on the original game")
        .replace("mod-definition.json", "compatibility information")
        .replace("UUID", "mod ID")
        .replace("package", "mod")
        .replace("preflight", "check")
    )


def _set_dynamic_property(widget: "QWidget", name: str, value: object) -> None:
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Start the desktop manager, or explain that the optional UI is absent."""

    if _PYSIDE_IMPORT_ERROR is not None:
        print(
            "Majesty Mod Manager requires the bundled PySide6 desktop runtime. "
            "The command-line merger is still available, but this UI cannot start "
            f"in the current Python environment ({_PYSIDE_IMPORT_ERROR}).",
            file=sys.stderr,
        )
        return 2

    arguments = list(sys.argv if argv is None else argv)
    if not arguments:
        arguments = ["majesty-mod-manager"]
    application = QApplication.instance()
    owns_application = application is None
    if application is None:
        _set_windows_app_user_model_id()
        application = QApplication(arguments)
    application.setApplicationName(APP_NAME)
    application.setApplicationDisplayName(APP_NAME)
    application.setOrganizationName("Majesty Mod Manager")
    manager_icon = _manager_icon()
    if not manager_icon.isNull():
        application.setWindowIcon(manager_icon)
    application.setStyle("Fusion")
    application.setFont(QFont("Segoe UI", 9))
    window = ManagerWindow()
    window.show()
    # Keep the top-level widget alive when main is called from an embedded host.
    setattr(application, "_majesty_manager_window", window)
    return application.exec() if owns_application else 0


if __name__ == "__main__":  # pragma: no cover - manual desktop entry point.
    raise SystemExit(main())

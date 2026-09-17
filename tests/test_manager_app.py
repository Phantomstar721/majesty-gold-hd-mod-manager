from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from majesty_cam.manager import app as manager_app
from majesty_cam.manager.build import BuildIssue, BuildPlan
from majesty_cam.manager.catalog import Catalog, CatalogEntry, CatalogKind, CatalogSource
from majesty_cam.manager.controller import ControllerSnapshot


def _required_utility(key: str, name: str, status: str) -> object:
    return type(
        "RequiredUtility",
        (),
        {
            "key": key,
            "name": name,
            "description": f"Basic description for {name}.",
            "status": status,
            "required_for_manager": True,
            "can_install": status == "available",
            "can_remove": False,
            "detail": "",
        },
    )()


def _snapshot_with_required_qol(
    visitor_status: str,
    remembered_status: str,
) -> ControllerSnapshot:
    return ControllerSnapshot(
        catalog=Catalog(entries=()),
        selections={},
        plan=BuildPlan(
            selected_standard_ids=(),
            selected_merge=(),
            resolution_owners={},
            semantic_resolutions={},
            runtime_capabilities=(),
            fingerprint="test",
            issues=(),
        ),
        selection_source="defaults",
        build_required=False,
        can_build=True,
        can_launch=True,
        managed_build=None,
        qol_status=(),
        qol_utilities=(
            _required_utility(
                "generic-visitors", "Generic Visitor Lists", visitor_status
            ),
            _required_utility(
                "remember-mods", "Remember Active Mods", remembered_status
            ),
        ),
        game_build=None,
        notices=(),
    )


class PlayerIssueTextTests(unittest.TestCase):
    def test_build_issue_keeps_affected_mod_and_specific_reason(self) -> None:
        entry = CatalogEntry("example", "example", "Example Mod", CatalogKind.MERGE,
                             CatalogSource.LOCAL_MODS, Path("example"), Path("example/mod.mmxml"), True, True)
        snapshot = replace(_snapshot_with_required_qol("installed", "installed"),
                           catalog=Catalog((entry,)))
        text = manager_app._build_issue_description(snapshot, BuildIssue(
            "missing_required_mod", "Example Mod requires Base Mod with its AI component enabled.",
            content_id="example"))
        self.assertIn("Example Mod", text)
        self.assertIn("Base Mod with its AI component enabled", text)

    def test_foreach_return_preflight_uses_plain_player_language(self) -> None:
        rendered = manager_app._player_issue_text(
            "unsafe_gpl_foreach_return",
            "GPL return at line 12 is inside a foreach loop begun at line 8.",
        )

        self.assertIn("can crash Majesty", rendered)
        self.assertIn("author needs to update", rendered)
        self.assertNotIn("GPL", rendered)
        self.assertNotIn("foreach", rendered)


@unittest.skipIf(
    manager_app._PYSIDE_IMPORT_ERROR is not None,
    "optional PySide6 desktop runtime is unavailable",
)
class ManagerAppLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.application = QApplication.instance() or QApplication(["manager-ui-tests"])

    def test_combination_blocker_remains_clickable_and_opens_reason_without_building(self):
        controller = SimpleNamespace(paths=SimpleNamespace(game_path=Path("Z:/missing-majesty")))
        with patch.object(manager_app.QTimer, "singleShot"):
            window = manager_app.ManagerWindow(controller)
        base = _snapshot_with_required_qol("installed", "installed")
        issue = BuildIssue("unsafe_runtime_features", "SpecificFunction: incompatible callback boundary")
        snapshot = replace(base, plan=replace(base.plan, issues=(issue,)), can_build=False, can_launch=False)
        window.snapshot = snapshot
        window._render_build_state(snapshot)
        self.assertEqual(window.build_button.text(), "Review Issues")
        self.assertTrue(window.build_button.isEnabled())
        self.assertFalse(window.launch_button.isEnabled())
        self.assertEqual(window.build_button.property("role"), "attention")
        self.assertIn("1 issue", window.build_state.text())
        with patch.object(window, "_run_task") as run, patch.object(
            window, "_resolve_selected_conflicts") as resolve, patch.object(
            manager_app.QMessageBox, "exec", return_value=0):
            window.build_button.click()
        run.assert_not_called()
        resolve.assert_not_called()
        dialog = window.findChildren(manager_app.QMessageBox)[-1]
        self.assertIn(issue.message, dialog.informativeText())
        self.assertIn(issue.code, dialog.detailedText())
        # Reviewing a problem is not gated by missing game helpers either.
        blocked = replace(snapshot, qol_utilities=_snapshot_with_required_qol("available", "installed").qol_utilities)
        window._render_build_state(blocked)
        self.assertTrue(window.build_button.isEnabled())
        window._render_build_state(base)
        self.assertEqual(window.build_button.property("role"), "outline")
        self.assertNotEqual(window.build_button.text(), "Review Issues")
        window.close()

    def test_mixed_conflicts_and_other_issues_do_not_hide_review(self):
        controller = SimpleNamespace(paths=SimpleNamespace(game_path=Path("Z:/missing-majesty")))
        with patch.object(manager_app.QTimer, "singleShot"):
            window = manager_app.ManagerWindow(controller)
        base = _snapshot_with_required_qol("installed", "installed")
        issues = (BuildIssue("unresolved_standard_overlap", "Two mods overlap"),
                  BuildIssue("unsafe_runtime_features", "Specific callback is incompatible"))
        snapshot = replace(base, plan=replace(base.plan, issues=issues), can_build=False, can_launch=False)
        window.snapshot = snapshot
        window._render_build_state(snapshot)
        self.assertEqual(window.build_button.text(), "Review Issues")
        self.assertTrue(window.build_button.isEnabled())
        with patch.object(window, "_show_build_issues") as review, patch.object(
            window, "_resolve_selected_conflicts") as conflicts:
            window.build_button.click()
        review.assert_called_once()
        conflicts.assert_not_called()
        window.close()

    def test_bundled_manager_icon_has_windows_sizes(self) -> None:
        self.assertTrue(manager_app._MANAGER_ICON_PATH.is_file())
        icon = manager_app._manager_icon()
        self.assertFalse(icon.isNull())
        sizes = {(size.width(), size.height()) for size in icon.availableSizes()}
        self.assertTrue({(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes)

    def test_main_sets_the_application_icon(self) -> None:
        previous_icon = self.application.windowIcon()
        try:
            with patch.object(manager_app, "ManagerWindow") as window_type:
                self.assertEqual(manager_app.main(["manager-ui-tests"]), 0)

            window_type.return_value.show.assert_called_once_with()
            actual = self.application.windowIcon().pixmap(32, 32).toImage()
            expected = manager_app._manager_icon().pixmap(32, 32).toImage()
            self.assertEqual(actual, expected)
        finally:
            self.application.setWindowIcon(previous_icon)

    def test_game_icon_stays_in_header_while_window_uses_manager_icon(self) -> None:
        from PySide6.QtGui import QColor, QPixmap
        from PySide6.QtWidgets import QLabel, QPushButton

        class _Paths:
            game_path = Path("Z:/missing-majesty")
            profile_path = Path(tempfile.gettempdir()) / "manager-ui-profile.json"

        class _Controller:
            paths = _Paths()

        with tempfile.TemporaryDirectory() as temp:
            game_icon_path = Path(temp) / "game-icon.png"
            game_icon = QPixmap(42, 42)
            game_icon.fill(QColor(210, 20, 20))
            self.assertTrue(game_icon.save(str(game_icon_path)))
            brand_assets = manager_app.BrandAssets(
                None,
                None,
                game_icon_path,
            )
            with (
                patch.object(manager_app, "ensure_brand_assets", return_value=brand_assets),
                patch.object(manager_app.QTimer, "singleShot"),
            ):
                window = manager_app.ManagerWindow(_Controller())  # type: ignore[arg-type]

            crest = window.findChild(QLabel, "crestImage")
            self.assertIsNotNone(crest)
            self.assertEqual(
                crest.pixmap().toImage().pixelColor(21, 21),
                QColor(210, 20, 20),
            )
            actual = window.windowIcon().pixmap(32, 32).toImage()
            expected = manager_app._manager_icon().pixmap(32, 32).toImage()
            self.assertEqual(actual, expected)
            window.close()

    def test_merge_is_the_initial_tab(self) -> None:
        class _Paths:
            game_path = Path("Z:/missing-majesty")
            profile_path = Path(tempfile.gettempdir()) / "manager-ui-profile.json"

        class _Controller:
            paths = _Paths()

        with patch.object(manager_app.QTimer, "singleShot"):
            window = manager_app.ManagerWindow(_Controller())  # type: ignore[arg-type]
        self.assertEqual(
            [window.tabs.tabText(index) for index in range(window.tabs.count())],
            ["Merge", "Standard", "Quests", "Quality of Life"],
        )
        self.assertEqual(window.tabs.currentIndex(), 0)
        window.close()

    def test_startup_uses_cache_while_rescan_forces_refresh(self) -> None:
        class _Paths:
            game_path = Path("Z:/missing-majesty")
            profile_path = Path(tempfile.gettempdir()) / "manager-ui-profile.json"

        class _Controller:
            paths = _Paths()

            def scan(self, *, force_refresh=False, progress=None):
                return force_refresh

        with patch.object(manager_app.QTimer, "singleShot"):
            window = manager_app.ManagerWindow(_Controller())  # type: ignore[arg-type]

        with patch.object(window, "_run_task") as run:
            window._startup_scan()
            startup_action = run.call_args.args[1]
            self.assertFalse(startup_action(lambda message: None))

            window.scan()
            rescan_action = run.call_args.args[1]
            self.assertTrue(rescan_action(lambda message: None))

        window.close()

    def test_merge_selection_planning_runs_off_the_ui_thread(self) -> None:
        content_id = "8c48289e-7c70-4426-8913-133f3544a182"
        entry = CatalogEntry(
            content_id=content_id,
            raw_content_id=content_id,
            display_name="Merge Fixture",
            kind=CatalogKind.MERGE,
            source=CatalogSource.LOCAL_MODS,
            package_root=Path("C:/Mods/MergeFixture"),
            manifest_path=Path("C:/Mods/MergeFixture/fixture.mmxml"),
            has_cam=True,
            merge_ready=True,
        )

        class _Paths:
            game_path = Path("Z:/missing-majesty")
            profile_path = Path(tempfile.gettempdir()) / "manager-ui-profile.json"

        class _Controller:
            paths = _Paths()

            def set_selected(self, selected_id, enabled):
                raise AssertionError("selection planning ran synchronously")

        with patch.object(manager_app.QTimer, "singleShot"):
            window = manager_app.ManagerWindow(_Controller())  # type: ignore[arg-type]
        window.snapshot = replace(
            _snapshot_with_required_qol("installed", "installed"),
            catalog=Catalog(entries=(entry,)),
            selections={content_id: False},
        )

        with patch.object(window, "_run_task") as run:
            window._selection_changed(content_id, True)

        self.assertEqual(run.call_args.args[0], "Checking selected mod")
        self.assertEqual(run.call_args.args[2], window._selection_finished)
        window.close()

    def test_header_explains_rescan_and_offers_game_location_controls(self) -> None:
        from PySide6.QtWidgets import QLabel, QPushButton

        class _Paths:
            game_path = Path("Z:/missing-majesty")
            game_executable = game_path / "MajestyHD.exe"
            profile_path = Path(tempfile.gettempdir()) / "manager-ui-profile.json"

        class _Controller:
            paths = _Paths()

        with patch.object(manager_app.QTimer, "singleShot"):
            window = manager_app.ManagerWindow(_Controller())  # type: ignore[arg-type]

        buttons = {button.text(): button for button in window.findChildren(QPushButton)}
        self.assertIn("Rescan Content", buttons)
        self.assertIn("Choose…", buttons)
        self.assertIn("Folder", buttons)
        self.assertIn("Desktop Shortcut", buttons)
        self.assertIn("mods and quests", buttons["Rescan Content"].toolTip())
        self.assertIn("MajestyHD.exe", buttons["Choose…"].toolTip())
        install_path = window.findChild(QLabel, "installPath")
        self.assertIsNotNone(install_path)
        self.assertGreaterEqual(install_path.minimumWidth(), 240)
        self.assertGreater(install_path.maximumWidth(), 1000)
        self.assertEqual(buttons["Choose…"].height(), buttons["Folder"].height())
        self.assertEqual(
            buttons["Folder"].height(), buttons["Rescan Content"].height()
        )
        self.assertEqual(buttons["Choose…"].width(), buttons["Folder"].width())
        self.assertEqual(
            buttons["Folder"].width(), buttons["Rescan Content"].width()
        )
        self.assertEqual(buttons["Choose…"].property("role"), "headerAction")
        self.assertEqual(buttons["Folder"].property("role"), "headerAction")
        self.assertEqual(buttons["Desktop Shortcut"].property("role"), "quiet")
        self.assertEqual(
            buttons["Rescan Content"].property("role"), "headerAction"
        )
        header_labels = {
            label.text(): label
            for label in window.findChildren(QLabel)
            if label.text()
            in {"MAJESTY GOLD HD", "GAME VERSION", "GAME INSTALL"}
        }
        self.assertEqual(len(header_labels), 3)
        self.assertEqual(
            {label.height() for label in header_labels.values()}, {14}
        )
        self.assertEqual(
            {
                bool(label.alignment() & manager_app.Qt.AlignmentFlag.AlignTop)
                for label in header_labels.values()
            },
            {True},
        )
        window.close()

    def test_desktop_shortcut_button_creates_shortcut_without_moving_app(self) -> None:
        from PySide6.QtWidgets import QMessageBox, QPushButton

        class _Paths:
            game_path = Path("Z:/missing-majesty")
            profile_path = Path(tempfile.gettempdir()) / "manager-ui-profile.json"

        class _Controller:
            paths = _Paths()

        shortcut = Path("C:/Users/Player/Desktop/Majesty Mod Manager.lnk")
        with patch.object(manager_app.QTimer, "singleShot"), patch.object(
            manager_app, "create_manager_desktop_shortcut", return_value=shortcut
        ) as create, patch.object(QMessageBox, "information") as information:
            window = manager_app.ManagerWindow(_Controller())  # type: ignore[arg-type]
            button = next(
                item
                for item in window.findChildren(QPushButton)
                if item.text() == "Desktop Shortcut"
            )
            button.click()

        create.assert_called_once_with()
        self.assertIn(str(shortcut), information.call_args.args[2])
        window.close()

    def test_footer_does_not_repeat_required_qol_status(self) -> None:
        from PySide6.QtWidgets import QLabel

        class _Paths:
            game_path = Path("Z:/missing-majesty")
            profile_path = Path(tempfile.gettempdir()) / "manager-ui-profile.json"

        class _Controller:
            paths = _Paths()

        with patch.object(manager_app.QTimer, "singleShot"):
            window = manager_app.ManagerWindow(_Controller())  # type: ignore[arg-type]

        self.assertIsNone(window.findChild(QLabel, "qolStatus"))
        footer_text = " ".join(
            label.text()
            for label in window.findChildren(QLabel)
            if label.parent() is not None
            and label.parent().objectName() == "stickyFooter"
        )
        self.assertNotIn("Visitor Lists", footer_text)
        self.assertNotIn("Saved Mod Choices", footer_text)
        window.close()

    def test_first_scan_opens_qol_and_warns_once_when_required_patch_missing(
        self,
    ) -> None:
        class _Paths:
            game_path = Path("Z:/missing-majesty")
            profile_path = Path(tempfile.gettempdir()) / "manager-ui-profile.json"

        class _Controller:
            paths = _Paths()

        with patch.object(manager_app.QTimer, "singleShot"):
            window = manager_app.ManagerWindow(_Controller())  # type: ignore[arg-type]

        missing = _snapshot_with_required_qol("available", "installed")
        with patch.object(manager_app.QMessageBox, "warning") as warning:
            window._scan_finished(missing)
            window._scan_finished(missing)

        self.assertIs(window.tabs.currentWidget(), window.qol_page)
        warning.assert_called_once()
        message = warning.call_args.args[2]
        self.assertIn("Generic Visitor Lists", message)
        self.assertIn("Prepare Selected Mods", message)
        self.assertIn("Launch Majesty", message)
        self.assertFalse(window.build_button.isEnabled())
        self.assertFalse(window.launch_button.isEnabled())

        window._qol_changed(_snapshot_with_required_qol("installed", "installed"))
        self.assertTrue(window.build_button.isEnabled())
        self.assertTrue(window.launch_button.isEnabled())
        window.close()

    def test_first_scan_with_required_patches_installed_does_not_interrupt(self) -> None:
        class _Paths:
            game_path = Path("Z:/missing-majesty")
            profile_path = Path(tempfile.gettempdir()) / "manager-ui-profile.json"

        class _Controller:
            paths = _Paths()

        with patch.object(manager_app.QTimer, "singleShot"):
            window = manager_app.ManagerWindow(_Controller())  # type: ignore[arg-type]

        with patch.object(manager_app.QMessageBox, "warning") as warning:
            window._scan_finished(
                _snapshot_with_required_qol("installed", "installed")
            )

        warning.assert_not_called()
        self.assertEqual(window.tabs.currentIndex(), 0)
        self.assertTrue(window.build_button.isEnabled())
        self.assertTrue(window.launch_button.isEnabled())
        window.close()

    def test_saved_choices_are_plain_language_and_notices_stay_in_notice_bar(self) -> None:
        class _Paths:
            game_path = Path("Z:/missing-majesty")
            profile_path = Path(tempfile.gettempdir()) / "manager-ui-profile.json"

        class _Controller:
            paths = _Paths()

        with (
            patch.object(manager_app.QTimer, "singleShot"),
            patch.object(
                manager_app,
                "ensure_brand_assets",
                return_value=manager_app.BrandAssets(None, None, None),
            ),
        ):
            window = manager_app.ManagerWindow(_Controller())  # type: ignore[arg-type]

        snapshot = replace(
            _snapshot_with_required_qol("installed", "installed"),
            selection_source="manager",
            notices=("QOL preflight failed: fixture",),
        )
        window._render_snapshot(snapshot)

        self.assertEqual(window.selection_note.text(), "Your saved choices are loaded")
        self.assertNotIn("scan", window.selection_note.text().casefold())
        self.assertEqual(window.selection_note.toolTip(), "")
        self.assertFalse(window.notice_bar.isHidden())
        self.assertEqual(
            window.notice_text.text(),
            "The manager could not check the installed game helpers.",
        )
        window.close()

    def test_mod_card_keeps_names_single_line_and_hides_internal_id(self) -> None:
        from PySide6.QtWidgets import QLabel, QPushButton

        entry = CatalogEntry(
            content_id="8C48289E-7C70-4426-8913-133F3544A182",
            raw_content_id=None,
            display_name="Custom Guild: Phantom's Haunt",
            kind=CatalogKind.MERGE,
            source=CatalogSource.WORKSHOP,
            package_root=Path("C:/Steam/workshop/content/73230/123456789"),
            manifest_path=Path("C:/Steam/workshop/content/73230/123456789/mod.xml"),
            has_cam=True,
            merge_ready=True,
            compatibility_applied=True,
        )
        card = manager_app._ModCard(
            entry,
            selected=True,
            prepared=type(
                "Prepared",
                (),
                {
                    "badge": "Improved version retaining the original Elf Guild",
                    "substituted": True,
                },
            )(),
            blocked_preflight=None,
        )

        name = card.findChild(QLabel, "modName")
        self.assertIsNotNone(name)
        self.assertFalse(name.wordWrap())
        self.assertFalse(card.findChildren(QLabel, "contentId"))
        self.assertEqual(
            card.findChild(QLabel, "compatibilityBadge").text(),
            "SUPPORTED",
        )
        details = " ".join(
            label.text() for label in card.findChildren(QLabel, "cardDetail")
        )
        self.assertIn("original Elf Guild remains unchanged", details)

        steam_button = card.findChild(QPushButton, "steamLinkButton")
        self.assertIsNotNone(steam_button)
        self.assertFalse(steam_button.icon().isNull())
        opened: list[str] = []
        card.steam_requested.connect(opened.append)
        steam_button.click()
        self.assertEqual(opened, ["123456789"])
        self.assertIn("Steam Workshop page", steam_button.toolTip())

        unselected_card = manager_app._ModCard(
            entry,
            selected=False,
            prepared=None,
            blocked_preflight=None,
        )
        self.assertEqual(
            unselected_card.findChild(QLabel, "compatibilityBadge").text(),
            "COMPATIBLE",
        )

    def test_standard_overlap_is_a_compact_conflicts_button_not_inline_text(self) -> None:
        from PySide6.QtWidgets import QLabel, QPushButton

        content_id = "10000000-0000-4000-8000-000000000001"
        other_id = "10000000-0000-4000-8000-000000000002"
        entry = CatalogEntry(
            content_id=content_id,
            raw_content_id=content_id,
            display_name="Example Mod",
            kind=CatalogKind.STANDARD,
            source=CatalogSource.WORKSHOP,
            package_root=Path("C:/Steam/workshop/content/73230/123"),
            manifest_path=Path("C:/Steam/workshop/content/73230/123/Example.mmxml"),
            has_cam=False,
            merge_ready=False,
            unresolved_overlap_ids=(other_id,),
            unresolved_overlap_names=("Another Mod",),
        )
        card = manager_app._ModCard(
            entry,
            selected=True,
            prepared=None,
            blocked_preflight=None,
        )

        button = card.findChild(QPushButton, "conflictsButton")
        self.assertIsNotNone(button)
        self.assertEqual(button.text(), "CONFLICTS")
        details = " ".join(
            label.text() for label in card.findChildren(QLabel, "cardDetail")
        )
        self.assertNotIn("Another Mod", details)

    def test_multi_mod_options_are_collapsible_and_update_in_place(self) -> None:
        from PySide6.QtWidgets import QLabel, QPushButton

        ids = (
            "10000000-0000-4000-8000-000000000001",
            "10000000-0000-4000-8000-000000000002",
        )
        root = Path("C:/Steam/workshop/content/73230/123")
        entries = tuple(
            CatalogEntry(
                content_id=content_id,
                raw_content_id=content_id,
                display_name=f"Example - Version {index + 1}",
                kind=CatalogKind.STANDARD,
                source=CatalogSource.WORKSHOP,
                package_root=root,
                manifest_path=root / "Example.mmxml",
                has_cam=False,
                merge_ready=False,
                description=f"Uses ruleset {index + 1}.",
                collection_id="example-collection",
                collection_name="Example",
                collection_index=index,
                collection_size=2,
                variant_label=f"Version {index + 1}",
                incompatible_ids=(ids[1 - index],),
                incompatible_names=(f"Example - Version {2 - index}",),
            )
            for index, content_id in enumerate(ids)
        )
        snapshot = replace(
            _snapshot_with_required_qol("installed", "installed"),
            catalog=Catalog(entries=entries),
            selections={ids[0]: True, ids[1]: False},
        )
        page = manager_app._CatalogPage(CatalogKind.STANDARD)
        page.populate(entries, snapshot, {}, {})

        self.assertEqual(len(page.groups), 1)
        group = page.groups[0]
        self.assertTrue(group.children.isHidden())
        self.assertEqual(group.findChild(QLabel, "variantGroupBadge").text(), "CHOOSE ONE")
        details = " ".join(
            label.text() for label in group.findChildren(QLabel, "cardDetail")
        )
        self.assertNotIn("Uses ruleset 1", details)
        self.assertIn("selecting it turns those off", details)
        author_details = group.findChildren(QLabel, "authorDescription")
        self.assertEqual(len(author_details), 2)
        self.assertTrue(all(label.isHidden() for label in author_details))
        detail_buttons = group.findChildren(QPushButton, "contentDetailsButton")
        self.assertEqual(len(detail_buttons), 2)
        detail_buttons[0].click()
        self.assertFalse(author_details[0].isHidden())
        self.assertIn("Uses ruleset 1", author_details[0].text())
        all_details = group.findChild(QPushButton, "collectionDetailsButton")
        self.assertIsNotNone(all_details)
        all_details.click()
        self.assertTrue(all(not label.isHidden() for label in author_details))
        self.assertFalse(group.children.isHidden())
        self.assertEqual(all_details.text(), "Hide all details")
        all_details.click()
        self.assertTrue(all(label.isHidden() for label in author_details))
        self.assertEqual(len(group.findChildren(QPushButton, "steamLinkButton")), 1)

        original_cards = tuple(page.cards)
        page.update_selections({ids[0]: False, ids[1]: True})
        self.assertEqual(tuple(page.cards), original_cards)
        self.assertEqual(group.summary.text(), "SELECTED · Version 2")
        page.close()

    def test_qol_card_shows_only_basic_description_and_aligned_actions(self) -> None:
        from PySide6.QtWidgets import QLabel, QPushButton

        utility = type(
            "Utility",
            (),
            {
                "key": "example",
                "name": "Example Improvement",
                "description": "A basic explanation of what this patch changes.",
                "status": "installed",
                "required_for_manager": False,
                "can_install": False,
                "can_remove": True,
                "detail": "Internal executable offsets that players do not need.",
            },
        )()
        card = manager_app._QolCard(utility)
        card.resize(850, card.sizeHint().height())
        card.show()
        self.application.processEvents()

        visible_text = " ".join(label.text() for label in card.findChildren(QLabel))
        self.assertIn(utility.description, visible_text)
        self.assertNotIn(utility.detail, visible_text)
        self.assertFalse(card.findChildren(QLabel, "qolDetail"))
        self.assertFalse(card.findChildren(QLabel, "requiredExplanation"))

        name = card.findChild(QLabel, "modName")
        installed = card.findChild(QLabel, "qolStatusBadge")
        action = card.findChild(QPushButton)
        self.assertLess(name.geometry().right(), installed.geometry().right())
        self.assertLess(installed.geometry().right(), action.geometry().left())
        self.assertLessEqual(
            abs(installed.geometry().center().y() - action.geometry().center().y()),
            2,
        )
        card.close()

    def test_qol_sort_places_required_patches_last(self) -> None:
        utility = lambda name, required: type(  # noqa: E731
            "Utility",
            (),
            {
                "name": name,
                "key": name.casefold().replace(" ", "-"),
                "required_for_manager": required,
            },
        )()
        values = (
            utility("Remember Active Mods", True),
            utility("Zoom Out More", False),
            utility("Generic Visitor Lists", True),
            utility("Auto Save", False),
        )
        self.assertEqual(
            [item.name for item in sorted(values, key=manager_app._qol_sort_key)],
            [
                "Auto Save",
                "Zoom Out More",
                "Generic Visitor Lists",
                "Remember Active Mods",
            ],
        )

    def test_windows_taskbar_identity_uses_stable_app_id(self) -> None:
        setter = Mock(return_value=0)
        windll = SimpleNamespace(
            shell32=SimpleNamespace(
                SetCurrentProcessExplicitAppUserModelID=setter,
            )
        )

        with (
            patch.object(manager_app.sys, "platform", "win32"),
            patch.object(manager_app.ctypes, "windll", windll, create=True),
        ):
            manager_app._set_windows_app_user_model_id()

        setter.assert_called_once_with("MajestyGoldHD.ModManager")
        self.assertEqual(manager_app.APP_USER_MODEL_ID, "MajestyGoldHD.ModManager")


if __name__ == "__main__":
    unittest.main()

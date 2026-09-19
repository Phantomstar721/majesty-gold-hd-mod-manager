from pathlib import Path
import json
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.catalog import (
    CatalogIssue,
    CatalogKind,
    CatalogSource,
    IssueSeverity,
    MAJESTY_SCRIPT_MERGER_ID,
    TOOL_DELIVERY_ISSUE_CODE,
    normalize_content_id,
    scan_catalog,
)
from majesty_cam.compose import ComposeError
from majesty_cam.manager.compatibility import CompatibilityRegistry
from majesty_cam.manager.preflight import (
    PreparedMergeMod,
    catalog_merge_preflight,
)


STANDARD_ID = "48cdd934-b338-4373-a4a4-a99a8e7f917f"
MERGE_ID = "{42ba4603-2b13-446d-a2a4-6cf3a55ddac3}"
QUEST_ID = "{BE9E6DFC-10F1-4984-9C79-A2F8F8F8C4A5}"


class ManagerCatalogTests(unittest.TestCase):
    def test_quest_catalog_uses_stock_direct_child_lookup(self):
        with TemporaryDirectory() as tmp:
            workshop = Path(tmp)
            package = workshop / "1234"
            package.mkdir()
            manifest = package / "Quest.mqxml"
            quest = f'<Quest id="{QUEST_ID}"><Name>Fixture</Name></Quest>'
            for xml in (quest, f"<Majesty><Nested>{quest}</Nested></Majesty>",
                        f"<Majesty>{quest}{quest}</Majesty>"):
                manifest.write_text(xml, encoding="utf-8")
                entry = scan_catalog(workshop_roots=(workshop,)).quests[0]
                self.assertIn("invalid_manifest_shape", _issue_codes(entry))
            manifest.write_text(f"<Majesty>{quest}</Majesty>", encoding="utf-8")
            self.assertFalse(scan_catalog(workshop_roots=(workshop,)).quests[0].issues)

    def test_classifies_standard_quest_and_definition_backed_merge_mod(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mods = root / "Mods"
            quests = root / "Quests"
            standard = mods / "Plain"
            merge = mods / "CAM"
            quest = quests / "AQuest"
            standard.mkdir(parents=True)
            merge.mkdir()
            quest.mkdir(parents=True)

            _write_mod(standard, STANDARD_ID, "Plain Mod", cam=False)
            _write_mod(merge, MERGE_ID, "CAM Mod", cam=True)
            _write_definition(merge, MERGE_ID)
            _write_quest(quest, QUEST_ID, name="QUEST_INTERNAL_NAME")

            catalog = scan_catalog(
                local_mods_root=mods,
                local_quests_root=quests,
            )

            self.assertEqual([entry.kind for entry in catalog.entries], [
                CatalogKind.STANDARD,
                CatalogKind.QUEST,
                CatalogKind.MERGE,
            ])
            plain = catalog.standard[0]
            self.assertEqual(plain.content_id, STANDARD_ID.upper())
            self.assertEqual(plain.source, CatalogSource.LOCAL_MODS)
            self.assertTrue(plain.selectable)

            found_quest = catalog.quests[0]
            self.assertEqual(found_quest.display_name, "QUEST_INTERNAL_NAME")
            self.assertFalse(found_quest.selectable)
            self.assertFalse(found_quest.active_mod_selectable)

            found_merge = catalog.merge[0]
            self.assertTrue(found_merge.has_cam)
            self.assertTrue(found_merge.merge_ready)
            self.assertTrue(found_merge.selectable)

    def test_missing_merge_definition_is_disabled_unless_compatibility_claims_id(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            package = mods / "LegacyCAM"
            package.mkdir(parents=True)
            _write_mod(package, MERGE_ID, "Legacy CAM", cam=True)

            without_compatibility = scan_catalog(local_mods_root=mods)
            entry = without_compatibility.merge[0]
            self.assertFalse(entry.merge_ready)
            self.assertFalse(entry.selectable)
            self.assertIn("missing_merge_definition", _issue_codes(entry))

            with_mapping = scan_catalog(
                local_mods_root=mods,
                compatibility={MERGE_ID.lower(): {"definition": "manager-owned"}},
            )
            entry = with_mapping.merge[0]
            self.assertTrue(entry.merge_ready)
            self.assertTrue(entry.compatibility_applied)
            self.assertTrue(entry.selectable)
            self.assertNotIn("missing_merge_definition", _issue_codes(entry))

            callback_calls = []

            def compatibility(content_id, package_root):
                callback_calls.append((content_id, package_root))
                return content_id == normalize_content_id(MERGE_ID)

            with_callback = scan_catalog(
                local_mods_root=mods,
                compatibility=compatibility,
            )
            self.assertTrue(with_callback.merge[0].merge_ready)
            self.assertEqual(callback_calls[0][0], normalize_content_id(MERGE_ID))

    def test_schema_v1_merge_definition_requires_trusted_adapter(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            package = mods / "LegacyDefinition"
            package.mkdir(parents=True)
            _write_mod(package, MERGE_ID, "Legacy Definition CAM", cam=True)
            (package / "mod-definition.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "mod_id": MERGE_ID,
                        "internal_name": "LegacyDefinitionCAM",
                        "display_name": "Legacy Definition CAM",
                        "custom_buildings": [],
                    }
                ),
                encoding="utf-8",
            )

            unadapted = scan_catalog(local_mods_root=mods).merge[0]
            adapted = scan_catalog(
                local_mods_root=mods,
                compatibility={MERGE_ID: {"definition": "trusted-adapter"}},
            ).merge[0]

            self.assertFalse(unadapted.merge_ready)
            self.assertFalse(unadapted.selectable)
            self.assertIn(
                "legacy_merge_definition_requires_adapter",
                _issue_codes(unadapted),
            )
            self.assertTrue(adapted.merge_ready)
            self.assertTrue(adapted.selectable)
            self.assertTrue(adapted.compatibility_applied)

    def test_schema_v3_nonbuilding_definition_is_merge_selectable(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            package = mods / "DeclarativeCAM"
            package.mkdir(parents=True)
            _write_mod(package, MERGE_ID, "Declarative CAM", cam=True)
            (package / "mod-definition.json").write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "mod_id": MERGE_ID,
                        "internal_name": "DeclarativeCAM",
                        "display_name": "Declarative CAM",
                        "custom_buildings": [],
                        "runtime_features": [],
                    }
                ),
                encoding="utf-8",
            )

            entry = scan_catalog(local_mods_root=mods).merge[0]

            self.assertTrue(entry.merge_ready)
            self.assertTrue(entry.selectable)
            self.assertFalse(entry.compatibility_applied)

    def test_unknown_package_owned_runtime_capability_is_red_and_not_selectable(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            package = mods / "FutureRuntime"
            package.mkdir(parents=True)
            _write_mod(package, MERGE_ID, "Future Runtime CAM", cam=True)
            (package / "mod-definition.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "mod_id": MERGE_ID,
                        "internal_name": "FutureRuntimeCAM",
                        "display_name": "Future Runtime CAM",
                        "custom_buildings": [],
                        "runtime_capabilities": ["example.not-supported.v1"],
                    }
                ),
                encoding="utf-8",
            )

            entry = scan_catalog(local_mods_root=mods).merge[0]

            self.assertFalse(entry.merge_ready)
            self.assertFalse(entry.selectable)
            issue = next(
                issue
                for issue in entry.issues
                if issue.code == "unsupported_runtime_capability"
            )
            self.assertIs(issue.severity, IssueSeverity.ERROR)
            self.assertIn("example.not-supported.v1", issue.message)

    def test_manager_derived_runtime_capability_requires_real_discovery(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            package = mods / "SelfDeclaredTextRegistry"
            package.mkdir(parents=True)
            _write_mod(package, MERGE_ID, "Self-declared Text Registry", cam=True)
            (package / "mod-definition.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "mod_id": MERGE_ID,
                        "internal_name": "SelfDeclaredTextRegistry",
                        "display_name": "Self-declared Text Registry",
                        "custom_buildings": [],
                        "runtime_capabilities": [
                            "private-activity-text-registry.v1"
                        ],
                    }
                ),
                encoding="utf-8",
            )

            unadapted = scan_catalog(local_mods_root=mods).merge[0]
            adapted = scan_catalog(
                local_mods_root=mods,
                compatibility={MERGE_ID: {"definition": "trusted-adapter"}},
            ).merge[0]

            self.assertFalse(unadapted.merge_ready)
            self.assertFalse(unadapted.selectable)
            self.assertIn("reserved_runtime_capability", _issue_codes(unadapted))
            self.assertTrue(adapted.merge_ready)
            self.assertTrue(adapted.selectable)
            self.assertTrue(adapted.compatibility_applied)
            self.assertIn(
                "packaged_merge_definition_ignored", _issue_codes(adapted)
            )

    def test_scan_runs_deep_preflight_before_merge_row_becomes_selectable(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            package = mods / "AutomaticCheck"
            package.mkdir(parents=True)
            _write_mod(package, MERGE_ID, "Automatic Check CAM", cam=True)
            _write_definition(package, MERGE_ID)
            calls = []

            def preflight(content_id, display_name, package_root):
                calls.append((content_id, display_name, package_root))
                return (
                    CatalogIssue(
                        code="ambiguous_custom_text_binding",
                        message="A changed text row matches more than one GPL use.",
                        severity=IssueSeverity.ERROR,
                        path=package_root,
                    ),
                )

            entry = scan_catalog(
                local_mods_root=mods,
                merge_preflight=preflight,
            ).merge[0]

            self.assertEqual(
                calls,
                [
                    (
                        normalize_content_id(MERGE_ID),
                        "Automatic Check CAM",
                        package.resolve(),
                    )
                ],
            )
            self.assertFalse(entry.selectable)
            self.assertFalse(entry.merge_ready)
            self.assertIn("ambiguous_custom_text_binding", _issue_codes(entry))

    def test_catalog_preflight_converts_automatic_text_discovery_failure(self):
        package = Path("C:/fixture/merge-mod")
        prepared = PreparedMergeMod(
            content_id=normalize_content_id(MERGE_ID),
            display_name="Automatic Text Fixture",
            source_root=package,
            effective_root=package,
            alias="automatic-text-fixture",
            package=SimpleNamespace(mod_id=normalize_content_id(MERGE_ID)),
            priority=1000,
            runtime_capabilities=(),
            badge=None,
            substituted=False,
            compatibility=None,
            issues=(),
        )
        with patch(
            "majesty_cam.manager.preflight.prepare_merge_package",
            return_value=prepared,
        ), patch(
            "majesty_cam.manager.preflight.discover_selected_private_activity_texts",
            side_effect=ComposeError(
                "automatic-text-fixture: AITX[7] has no unique GPL binding"
            ),
        ):
            issues = catalog_merge_preflight(
                normalize_content_id(MERGE_ID),
                prepared.display_name,
                package,
                registry=CompatibilityRegistry(specs={}),
                game_path=Path("C:/fixture/game"),
            )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "unsafe_custom_text_binding")
        self.assertIs(issues[0].severity, IssueSeverity.ERROR)
        self.assertIn("AITX[7]", issues[0].message)

    def test_catalog_preflight_passes_toggle_ownership_to_stock_evidence(self):
        from majesty_cam.runtime_features import RuntimeFeatureRegistry
        package = Path("C:/fixture/toggle-mod")
        prepared = PreparedMergeMod(
            content_id=normalize_content_id(MERGE_ID),
            display_name="Toggle Fixture",
            source_root=package,
            effective_root=package,
            alias="toggle-fixture",
            package=SimpleNamespace(mod_id=normalize_content_id(MERGE_ID)),
            priority=1000,
            runtime_capabilities=(),
            badge=None,
            substituted=False,
            compatibility=None,
            issues=(),
        )
        inventory = SimpleNamespace()
        toggle = SimpleNamespace(qualified_toggle_key="toggle-fixture::toggle::rentals")
        controller = SimpleNamespace(
            registry=SimpleNamespace(),
            panels=(),
            toggles=(toggle,),
        )
        evidence = "majesty_cam.manager.preflight.validate_controller_stock_evidence"
        with patch(
            "majesty_cam.manager.preflight.prepare_merge_package",
            return_value=prepared,
        ), patch(
            "majesty_cam.manager.preflight.discover_selected_private_activity_texts"
        ), patch(
            "majesty_cam.manager.preflight.inventory_package",
            return_value=inventory,
        ), patch(
            "majesty_cam.manager.preflight.validate_gpl_feature_evidence"
        ), patch(
            "majesty_cam.manager.preflight.resolve_runtime_feature_registry",
            return_value=RuntimeFeatureRegistry(),
        ), patch(
            "majesty_cam.manager.preflight.resolve_building_dialogs",
            return_value=(),
        ), patch(
            "majesty_cam.manager.preflight.resolve_controller_registry",
            return_value=controller,
        ), patch(evidence) as validate:
            issues = catalog_merge_preflight(
                normalize_content_id(MERGE_ID),
                prepared.display_name,
                package,
                registry=CompatibilityRegistry(specs={}),
                game_path=Path("C:/fixture/game"),
            )

        self.assertEqual(issues, ())
        self.assertEqual(validate.call_args.kwargs["controller_toggles"], (toggle,))

    def test_invalid_xml_and_invalid_uuid_are_structured_errors(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            broken = mods / "Broken"
            invalid_id = mods / "InvalidId"
            good = mods / "Good"
            broken.mkdir(parents=True)
            invalid_id.mkdir()
            good.mkdir()
            (broken / "Broken.mmxml").write_text("<Majesty><Mod", encoding="utf-8")
            _write_mod(invalid_id, "not-a-guid", "Invalid ID", cam=False)
            _write_mod(good, STANDARD_ID, "Good", cam=False)

            catalog = scan_catalog(local_mods_root=mods)

            self.assertEqual(len(catalog.entries), 3)
            by_name = {entry.display_name: entry for entry in catalog.entries}
            self.assertFalse(by_name["Broken"].selectable)
            self.assertIn("invalid_manifest_xml", _issue_codes(by_name["Broken"]))
            self.assertFalse(by_name["Invalid ID"].selectable)
            self.assertIn("invalid_content_id", _issue_codes(by_name["Invalid ID"]))
            self.assertTrue(by_name["Good"].selectable)
            self.assertTrue(all(isinstance(issue.code, str) for issue in catalog.issues))

    def test_duplicate_ids_are_deduplicated_deterministically_and_disabled(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mods = root / "Mods"
            workshop = root / "workshop"
            local = mods / "LocalCopy"
            remote = workshop / "123456"
            local.mkdir(parents=True)
            remote.mkdir(parents=True)
            _write_mod(local, STANDARD_ID, "Local Copy", cam=False)
            _write_mod(remote, "{" + STANDARD_ID.upper() + "}", "Workshop Copy", cam=False)

            catalog = scan_catalog(
                local_mods_root=mods,
                workshop_roots=(workshop,),
            )

            self.assertEqual(len(catalog.entries), 1)
            entry = catalog.entries[0]
            self.assertEqual(entry.display_name, "Local Copy")
            self.assertEqual(entry.source, CatalogSource.LOCAL_MODS)
            self.assertFalse(entry.selectable)
            self.assertIn("duplicate_content_id", _issue_codes(entry))
            self.assertEqual(
                [issue.code for issue in catalog.issues].count("duplicate_content_id"),
                1,
            )

    def test_generated_profile_is_internal_but_hidden_from_public_collections(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            generated = mods / "GeneratedProfile"
            generated.mkdir(parents=True)
            _write_mod(generated, MERGE_ID, "Generated Merge", cam=True)
            (generated / "CAM-MERGE-REPORT.json").write_text("{}", encoding="utf-8")

            catalog = scan_catalog(local_mods_root=mods)

            self.assertEqual(catalog.visible_entries, ())
            self.assertEqual(catalog.standard, ())
            self.assertEqual(catalog.quests, ())
            self.assertEqual(catalog.merge, ())
            self.assertEqual(len(catalog.entries), 1)
            entry = catalog.entries[0]
            self.assertTrue(entry.generated)
            self.assertFalse(entry.selectable)
            self.assertFalse(entry.merge_ready)
            self.assertIn("generated_output", _issue_codes(entry))
            self.assertNotIn("missing_merge_definition", _issue_codes(entry))

    def test_broken_generated_manifest_remains_hidden(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            generated = mods / "GeneratedProfile"
            generated.mkdir(parents=True)
            (generated / "Broken.mmxml").write_text("<Majesty><Mod", encoding="utf-8")
            (generated / "CAM-MERGE-REPORT.json").write_text("{}", encoding="utf-8")

            catalog = scan_catalog(local_mods_root=mods)

            self.assertEqual(catalog.visible_entries, ())
            self.assertEqual(len(catalog.entries), 1)
            self.assertTrue(catalog.entries[0].generated)
            self.assertIn("invalid_manifest_xml", _issue_codes(catalog.entries[0]))

    def test_known_script_merger_is_informational_and_not_selectable(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            package = mods / "MajestyScriptMerger"
            package.mkdir(parents=True)
            _write_mod(
                package,
                MAJESTY_SCRIPT_MERGER_ID,
                "Neutral renamed delivery package",
                cam=False,
            )

            catalog = scan_catalog(local_mods_root=mods)

            self.assertEqual(len(catalog.standard), 1)
            entry = catalog.standard[0]
            self.assertTrue(entry.tool_delivery)
            self.assertFalse(entry.selectable)
            self.assertIn(TOOL_DELIVERY_ISSUE_CODE, _issue_codes(entry))
            issue = next(
                issue for issue in entry.issues if issue.code == TOOL_DELIVERY_ISSUE_CODE
            )
            self.assertEqual(issue.severity, IssueSeverity.INFO)

    def test_explicit_tool_delivery_phrases_are_detected_in_manifest_metadata(self):
        cases = (
            ("Majesty Helper (modding tool only)", "Ordinary description"),
            ("Majesty Helper", "Changes nothing in-game; subscribing downloads a tool."),
            ("Majesty Helper", "This item changes nothing in the game."),
        )
        for index, (display_name, description) in enumerate(cases):
            with self.subTest(index=index), TemporaryDirectory() as tmp:
                mods = Path(tmp) / "Mods"
                package = mods / "Tool"
                package.mkdir(parents=True)
                content_id = f"00000000-0000-4000-8000-{index + 1:012d}"
                _write_mod(
                    package,
                    content_id,
                    display_name,
                    cam=False,
                    short_description=description,
                )

                entry = scan_catalog(local_mods_root=mods).standard[0]

                self.assertTrue(entry.tool_delivery)
                self.assertFalse(entry.selectable)

    def test_ordinary_empty_mod_is_not_guessed_to_be_a_tool(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            package = mods / "Empty"
            package.mkdir(parents=True)
            (package / "Empty.mmxml").write_text(
                f"""
                <Majesty>
                  <Mod id="{STANDARD_ID}">
                    <DataConfiguration><Dataset base="Any"><Load/></Dataset></DataConfiguration>
                    <DisplayName lang="en_US">Empty Gameplay Placeholder</DisplayName>
                    <Description lang="en_US"><Short>No resources yet.</Short></Description>
                  </Mod>
                </Majesty>
                """,
                encoding="utf-8",
            )

            entry = scan_catalog(local_mods_root=mods).standard[0]

            self.assertFalse(entry.tool_delivery)
            self.assertTrue(entry.selectable)
            self.assertNotIn(TOOL_DELIVERY_ISSUE_CODE, _issue_codes(entry))

    def test_workshop_accepts_item_roots_or_container_and_skips_empty_folders(self):
        with TemporaryDirectory() as tmp:
            workshop = Path(tmp) / "workshop"
            item_a = workshop / "100"
            item_b = workshop / "200"
            empty = workshop / "300"
            item_a.mkdir(parents=True)
            item_b.mkdir()
            empty.mkdir()
            _write_mod(item_a, STANDARD_ID, "A", cam=False)
            _write_quest(item_b, QUEST_ID, display_name="B")

            from_container = scan_catalog(workshop_roots=(workshop,))
            self.assertEqual([entry.display_name for entry in from_container.entries], ["A", "B"])

            from_items = scan_catalog(workshop_roots=(item_b, item_a))
            self.assertEqual(
                [(entry.display_name, entry.source) for entry in from_items.entries],
                [("A", CatalogSource.WORKSHOP), ("B", CatalogSource.WORKSHOP)],
            )
            self.assertEqual(from_items.entries[0].workshop_item_id, "100")
            self.assertEqual(from_items.entries[1].workshop_item_id, "200")

    def test_workshop_item_id_is_strict_and_never_inferred_for_local_content(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "Mods" / "123"
            valid = root / "workshop" / "18446744073709551615"
            too_large = root / "workshop" / "18446744073709551616"
            leading_zero = root / "workshop" / "00123"
            for package in (local, valid, too_large, leading_zero):
                package.mkdir(parents=True)
            _write_mod(local, STANDARD_ID, "Local", cam=False)
            _write_mod(valid, "00000000-0000-4000-8000-000000000001", "Valid", cam=False)
            _write_mod(too_large, "00000000-0000-4000-8000-000000000002", "Too large", cam=False)
            _write_mod(leading_zero, "00000000-0000-4000-8000-000000000003", "Leading zero", cam=False)

            catalog = scan_catalog(
                local_mods_root=root / "Mods",
                workshop_roots=(root / "workshop",),
            )
            by_name = {entry.display_name: entry for entry in catalog.entries}

            self.assertIsNone(by_name["Local"].workshop_item_id)
            self.assertEqual(
                by_name["Valid"].workshop_item_id, "18446744073709551615"
            )
            self.assertIsNone(by_name["Too large"].workshop_item_id)
            self.assertIsNone(by_name["Leading zero"].workshop_item_id)

    def test_tabs_are_alphabetical_with_standard_tools_at_the_bottom(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mods = root / "Mods"
            quests = root / "Quests"
            fixtures = (
                (mods / "zulu", "00000000-0000-4000-8000-000000000011", "zulu"),
                (mods / "Alpha", "00000000-0000-4000-8000-000000000012", "Alpha"),
                (mods / "tool", "00000000-0000-4000-8000-000000000013", "Aardvark Tool"),
            )
            for package, content_id, name in fixtures:
                package.mkdir(parents=True)
                _write_mod(
                    package,
                    content_id,
                    name,
                    cam=False,
                    short_description=(
                        "This modding tool only changes nothing in game."
                        if name == "Aardvark Tool"
                        else ""
                    ),
                )
            for index, name in enumerate(("quest Zebra", "Quest alpha"), start=21):
                package = quests / name
                package.mkdir(parents=True)
                _write_quest(
                    package,
                    f"00000000-0000-4000-8000-{index:012d}",
                    display_name=name,
                )

            catalog = scan_catalog(local_mods_root=mods, local_quests_root=quests)

            self.assertEqual(
                [entry.display_name for entry in catalog.standard],
                ["Alpha", "zulu", "Aardvark Tool"],
            )
            self.assertEqual(
                [entry.display_name for entry in catalog.quests],
                ["Quest alpha", "quest Zebra"],
            )

    def test_incompatible_merge_entries_sort_after_ready_entries(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            bad_id = "00000000-0000-4000-8000-000000000031"
            ready_id = "00000000-0000-4000-8000-000000000032"
            bad = mods / "bad"
            ready = mods / "ready"
            bad.mkdir(parents=True)
            ready.mkdir(parents=True)
            _write_mod(bad, bad_id, "Alpha Needs Attention", cam=True)
            _write_mod(ready, ready_id, "Zulu Ready", cam=True)

            catalog = scan_catalog(
                local_mods_root=mods,
                compatibility={ready_id: object()},
            )

            self.assertEqual(
                [entry.display_name for entry in catalog.merge],
                ["Zulu Ready", "Alpha Needs Attention"],
            )
            self.assertTrue(catalog.merge[0].selectable)
            self.assertFalse(catalog.merge[1].selectable)

    def test_workshop_container_ignores_non_numeric_backup_directories(self):
        with TemporaryDirectory() as tmp:
            workshop = Path(tmp) / "workshop"
            item = workshop / "100"
            backup = workshop / "100.backup-older"
            item.mkdir(parents=True)
            backup.mkdir()
            _write_mod(item, STANDARD_ID, "Live", cam=False)
            _write_mod(backup, STANDARD_ID, "Backup", cam=False)

            catalog = scan_catalog(workshop_roots=(workshop,))

            self.assertEqual([entry.display_name for entry in catalog.entries], ["Live"])
            self.assertTrue(catalog.entries[0].selectable)

    def test_stock_multi_mod_manifest_expands_to_independent_standard_rows(self):
        with TemporaryDirectory() as tmp:
            workshop = Path(tmp) / "workshop"
            item = workshop / "123456"
            item.mkdir(parents=True)
            manifest = item / "Options.mmxml"
            manifest.write_text(
                """
                <Majesty>
                  <Mod id="{00000000-0000-4000-8000-000000000003}">
                    <DisplayName lang="en_US">Option Charlie</DisplayName>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <GPL><Target>Data/C.bcd</Target><Source>GPL/C.gpl</Source></GPL>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                  <Mod id="{00000000-0000-4000-8000-000000000001}">
                    <DisplayName lang="en_US">Option Alpha</DisplayName>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <Descriptions>Data/A.xml</Descriptions>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                  <Mod id="{00000000-0000-4000-8000-000000000002}">
                    <DisplayName lang="en_US">Option Bravo</DisplayName>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <GPL><Target>Data/B.bcd</Target><Source>GPL/B.gpl</Source></GPL>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                </Majesty>
                """,
                encoding="utf-8",
            )

            catalog = scan_catalog(workshop_roots=(workshop,))

            self.assertEqual(
                [entry.display_name for entry in catalog.standard],
                ["Option Alpha", "Option Bravo", "Option Charlie"],
            )
            self.assertTrue(all(entry.selectable for entry in catalog.standard))
            self.assertTrue(
                all(entry.manifest_path == manifest.resolve() for entry in catalog.standard)
            )
            self.assertEqual(
                {entry.workshop_item_id for entry in catalog.standard}, {"123456"}
            )
            self.assertFalse(
                any("invalid_manifest_shape" in _issue_codes(entry) for entry in catalog.entries)
            )

    def test_multi_mod_collection_detects_only_overlapping_variants(self):
        with TemporaryDirectory() as tmp:
            workshop = Path(tmp) / "workshop"
            item = workshop / "987654"
            item.mkdir(parents=True)
            (item / "Options.mmxml").write_text(
                """
                <Majesty>
                  <Mod id="{00000000-0000-4000-8000-000000000001}">
                    <DisplayName lang="en_US">Example - Attributes V1</DisplayName>
                    <Description lang="en_US">
                      <Short>The simpler attribute set.</Short>
                      <Long>The longer author explanation stays separate.</Long>
                    </Description>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <GPL><Target>Data/Attributes_v1.bcd</Target></GPL>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                  <Mod id="{00000000-0000-4000-8000-000000000002}">
                    <DisplayName lang="en_US">Example - Attributes V2</DisplayName>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <GPL><Target>Data/Attributes_v2.bcd</Target></GPL>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                  <Mod id="{00000000-0000-4000-8000-000000000003}">
                    <DisplayName lang="en_US">Example - Extra Maps</DisplayName>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <Descriptions>Data/ExtraMaps.xml</Descriptions>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                </Majesty>
                """,
                encoding="utf-8",
            )

            entries = scan_catalog(workshop_roots=(workshop,)).standard
            by_name = {entry.display_name: entry for entry in entries}
            v1 = by_name["Example - Attributes V1"]
            v2 = by_name["Example - Attributes V2"]
            maps = by_name["Example - Extra Maps"]

            self.assertEqual({entry.collection_name for entry in entries}, {"Example"})
            self.assertTrue(all(entry.in_collection for entry in entries))
            self.assertEqual(v1.description, "The simpler attribute set.")
            self.assertEqual(
                v1.details, "The longer author explanation stays separate."
            )
            self.assertEqual(v1.incompatible_ids, (v2.content_id,))
            self.assertEqual(v2.incompatible_ids, (v1.content_id,))
            self.assertEqual(maps.incompatible_ids, ())
            self.assertEqual(v1.variant_label, "Attributes V1")

    def test_multi_mod_manifest_blocks_only_cam_changing_elements(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            package = mods / "Mixed"
            package.mkdir(parents=True)
            (package / "Mixed.mmxml").write_text(
                f"""
                <Majesty>
                  <Mod id="{STANDARD_ID}">
                    <DisplayName lang="en_US">Ordinary Option</DisplayName>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <GPL><Target>Data/Plain.bcd</Target><Source>GPL/Plain.gpl</Source></GPL>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                  <Mod id="{MERGE_ID}">
                    <DisplayName lang="en_US">CAM Option</DisplayName>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <CAM>Data/Content.cam</CAM>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                </Majesty>
                """,
                encoding="utf-8",
            )

            catalog = scan_catalog(local_mods_root=mods)

            self.assertEqual(len(catalog.standard), 1)
            self.assertTrue(catalog.standard[0].selectable)
            self.assertEqual(len(catalog.merge), 1)
            self.assertFalse(catalog.merge[0].selectable)
            self.assertIn("multi_mod_merge_manifest", _issue_codes(catalog.merge[0]))
            self.assertNotIn("missing_merge_definition", _issue_codes(catalog.merge[0]))

    def test_explicit_legacy_description_orders_matching_installed_components(self):
        with TemporaryDirectory() as tmp:
            workshop = Path(tmp) / "workshop"
            original = workshop / "100"
            patch = workshop / "200"
            original.mkdir(parents=True)
            patch.mkdir()
            (original / "Original.mmxml").write_text(
                """
                <Majesty>
                  <Mod id="{00000000-0000-4000-8000-000000000001}">
                    <DisplayName lang="en_US">Misc Enhancements - AI Improvements</DisplayName>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <GPL><Target>Data/AI.bcd</Target></GPL>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                  <Mod id="{00000000-0000-4000-8000-000000000002}">
                    <DisplayName lang="en_US">Misc Enhancements - Attributes Version 3</DisplayName>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <GPL><Target>Data/Attributes_v3.bcd</Target></GPL>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                  <Mod id="{00000000-0000-4000-8000-000000000005}">
                    <DisplayName lang="en_US">Misc Enhancements - Attributes Version 2</DisplayName>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <GPL><Target>Data/Attributes_v2.bcd</Target></GPL>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                </Majesty>
                """,
                encoding="utf-8",
            )
            (patch / "Patch.mmxml").write_text(
                """
                <Majesty>
                  <Mod id="{00000000-0000-4000-8000-000000000003}">
                    <DisplayName lang="en_US">ME Patch - AI Tower Fix</DisplayName>
                    <Description lang="en_US"><Long>
                      REQUIRES Miscellaneous Enhancements with its AI Improvements
                      component enabled, loaded BEFORE this patch.
                    </Long></Description>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <GPL><Target>Data/AI_Fix.bcd</Target></GPL>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                  <Mod id="{00000000-0000-4000-8000-000000000004}">
                    <DisplayName lang="en_US">ME Patch - Attributes V3 Spell Fix</DisplayName>
                    <Description lang="en_US">
                      <Short>Load AFTER Miscellaneous Enhancements with its Attributes V3 component.</Short>
                      <Long>Do not combine with Attributes V1 or V2.</Long>
                    </Description>
                    <DataConfiguration><Dataset base="Any"><Load>
                      <GPL><Target>Data/Attributes_Fix.bcd</Target></GPL>
                    </Load></Dataset></DataConfiguration>
                  </Mod>
                </Majesty>
                """,
                encoding="utf-8",
            )

            entries = scan_catalog(workshop_roots=(workshop,)).standard
            by_name = {entry.display_name: entry for entry in entries}
            ai = by_name["Misc Enhancements - AI Improvements"]
            attrs = by_name["Misc Enhancements - Attributes Version 3"]
            ai_patch = by_name["ME Patch - AI Tower Fix"]
            attrs_patch = by_name["ME Patch - Attributes V3 Spell Fix"]

            self.assertEqual(ai_patch.load_after_ids, (ai.content_id,))
            self.assertEqual(attrs_patch.load_after_ids, (attrs.content_id,))
            self.assertEqual(ai_patch.required_ids, (ai.content_id,))
            self.assertEqual(attrs_patch.required_ids, (attrs.content_id,))
            self.assertIn(
                by_name["Misc Enhancements - Attributes Version 2"].content_id,
                attrs_patch.incompatible_ids,
            )
            self.assertEqual(ai.load_before_ids, (ai_patch.content_id,))
            self.assertEqual(attrs.load_before_ids, (attrs_patch.content_id,))

    def test_divergent_standard_definitions_require_a_known_order(self):
        with TemporaryDirectory() as tmp:
            workshop = Path(tmp) / "workshop"
            first = workshop / "100"
            second = workshop / "200"
            third = workshop / "300"
            for package in (first, second, third):
                (package / "GPL").mkdir(parents=True)

            _write_standard_source_mod(
                first,
                "00000000-0000-4000-8000-000000000001",
                "Base Balance",
                "expression #SharedValue 100\n",
            )
            _write_standard_source_mod(
                second,
                "00000000-0000-4000-8000-000000000002",
                "Alternate Balance",
                "expression #SharedValue 200\n",
            )
            _write_standard_source_mod(
                third,
                "00000000-0000-4000-8000-000000000003",
                "Base Balance Copy",
                "expression #SharedValue 100\n",
            )

            by_name = {
                entry.display_name: entry
                for entry in scan_catalog(workshop_roots=(workshop,)).standard
            }
            base = by_name["Base Balance"]
            alternate = by_name["Alternate Balance"]
            copy = by_name["Base Balance Copy"]

            self.assertEqual(alternate.unresolved_overlap_ids, (base.content_id, copy.content_id))
            self.assertNotIn(copy.content_id, base.unresolved_overlap_ids)

    def test_precompiled_mod_uses_bundled_gpl_source_as_overlap_evidence(self):
        with TemporaryDirectory() as tmp:
            workshop = Path(tmp) / "workshop"
            first = workshop / "100"
            second = workshop / "200"
            for package in (first, second):
                (package / "GPL").mkdir(parents=True)
            _write_standard_source_mod(
                first,
                "00000000-0000-4000-8000-000000000001",
                "Source Mod",
                "function peasant_basic(agent thisagent)\nbegin\n return;\nend\n",
            )
            (second / "GPL" / "shipped-source.gpl").write_text(
                "function peasant_basic(agent thisagent)\nbegin\n $stopmoving(thisagent);\nend\n",
                encoding="utf-8",
            )
            (second / "Precompiled.mmxml").write_text(
                """
                <Majesty><Mod id="{00000000-0000-4000-8000-000000000002}">
                  <DisplayName lang="en_US">Precompiled Mod</DisplayName>
                  <DataConfiguration><Dataset base="Any"><Load><GPL>
                    <Target>Data/Precompiled.bcd</Target>
                  </GPL></Load></Dataset></DataConfiguration>
                </Mod></Majesty>
                """,
                encoding="utf-8",
            )

            by_name = {
                entry.display_name: entry
                for entry in scan_catalog(workshop_roots=(workshop,)).standard
            }
            self.assertEqual(
                by_name["Precompiled Mod"].unresolved_overlap_ids,
                (by_name["Source Mod"].content_id,),
            )

    def test_ambiguous_manifests_and_unsafe_xml_fail_closed(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            ambiguous = mods / "Ambiguous"
            unsafe = mods / "Unsafe"
            ambiguous.mkdir(parents=True)
            unsafe.mkdir()
            _write_mod(ambiguous, STANDARD_ID, "First", cam=False, filename="a.mmxml")
            _write_mod(ambiguous, MERGE_ID, "Second", cam=False, filename="b.mmxml")
            (unsafe / "unsafe.mmxml").write_text(
                '<!DOCTYPE x [<!ENTITY y "bad">]><Majesty><Mod id="x">&y;</Mod></Majesty>',
                encoding="utf-8",
            )

            catalog = scan_catalog(local_mods_root=mods)

            self.assertEqual(len(catalog.entries), 3)
            self.assertTrue(all(not entry.selectable for entry in catalog.entries))
            self.assertEqual(
                sum("ambiguous_manifests" in _issue_codes(entry) for entry in catalog.entries),
                2,
            )
            unsafe_entry = next(entry for entry in catalog.entries if entry.display_name == "unsafe")
            self.assertIn("unsafe_xml_declaration", _issue_codes(unsafe_entry))

    def test_missing_scan_root_is_a_warning_not_an_exception(self):
        with TemporaryDirectory() as tmp:
            missing = Path(tmp) / "not-installed"
            catalog = scan_catalog(local_mods_root=missing)

            self.assertEqual(catalog.entries, ())
            self.assertEqual(catalog.issues[0].code, "scan_root_missing")
            self.assertEqual(catalog.issues[0].severity, IssueSeverity.WARNING)


def _write_mod(
    package: Path,
    content_id: str,
    display_name: str,
    *,
    cam: bool,
    filename: str = "Mod.mmxml",
    short_description: str = "",
) -> None:
    load = "<CAM>Data\\Content.cam</CAM>" if cam else "<Strings>Data\\Text.xml</Strings>"
    description = (
        f'<Description lang="en_US"><Short>{short_description}</Short></Description>'
        if short_description
        else ""
    )
    (package / filename).write_text(
        f"""
        <Majesty>
          <Mod id="{content_id}">
            <DataConfiguration><Dataset base="Any"><Load>{load}</Load></Dataset></DataConfiguration>
            <DisplayName lang="en_US">{display_name}</DisplayName>
            {description}
          </Mod>
        </Majesty>
        """,
        encoding="utf-8",
    )


def _write_standard_source_mod(
    package: Path,
    content_id: str,
    display_name: str,
    source_text: str,
) -> None:
    (package / "GPL" / "Content.gpl").write_text(source_text, encoding="utf-8")
    (package / "Mod.mmxml").write_text(
        f"""
        <Majesty><Mod id="{{{content_id}}}">
          <DisplayName lang="en_US">{display_name}</DisplayName>
          <DataConfiguration><Dataset base="Any"><Load><GPL>
            <Target>Data/Content.bcd</Target><Source>GPL/Content.gpl</Source>
          </GPL></Load></Dataset></DataConfiguration>
        </Mod></Majesty>
        """,
        encoding="utf-8",
    )


def _write_quest(
    package: Path,
    content_id: str,
    *,
    display_name: str = "",
    name: str = "",
) -> None:
    label = (
        f'<DisplayName lang="en_US">{display_name}</DisplayName>'
        if display_name
        else f"<Name>{name}</Name>"
    )
    (package / "Quest.mqxml").write_text(
        f"<Majesty><Quest id=\"{content_id}\">{label}</Quest></Majesty>",
        encoding="utf-8",
    )


def _write_definition(package: Path, content_id: str) -> None:
    (package / "mod-definition.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "mod_id": content_id,
                "internal_name": "FixtureCAM",
                "display_name": "Fixture CAM",
                "custom_buildings": [],
                "runtime_capabilities": [],
            }
        ),
        encoding="utf-8",
    )


def _issue_codes(entry) -> set:
    return {issue.code for issue in entry.issues}


if __name__ == "__main__":
    unittest.main()

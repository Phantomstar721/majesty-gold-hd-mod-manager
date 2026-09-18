from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import os
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.gpl import DefinitionKind
from majesty_cam.compose import ComposeError, PackageInventory, SelectedMod
from majesty_cam.intent_text import (
    INTENT_REGISTRY_RELATIVE_PATH,
    allocate_private_activity_text_ids,
    encode_intent_registry,
)
from majesty_cam.runtime_capabilities import (
    RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH,
    encode_runtime_capability_manifest,
)
from majesty_cam.runtime_features import (
    MapFogQueryFeature,
    MovementQueryFeature,
    NativeTimingFeature,
    RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH,
    encode_runtime_feature_registry,
)
from majesty_cam.stock_controller_registry import (
    CONTROLLER_REGISTRY_RELATIVE_PATH,
    encode_stock_controller_registry,
    resolve_stock_controller_registry,
)
from majesty_cam.manager.build import (
    MANAGER_OUTPUT_SENTINEL,
    ManagerBuildError,
    _cleanup_stale_manager_artifacts,
    _canonical_mod_definition,
    _parse_resolution_source,
    _publish_staging,
    _require_current_plan_sources,
    _is_manager_owned_output,
    _order_standard_ids,
    build_merged_package,
    create_build_plan,
    read_managed_build,
    standard_conflict_pair_key,
    standard_content_conflicts,
    standard_selection_issues,
)
from majesty_cam.manager.catalog import (
    Catalog,
    CatalogEntry,
    CatalogKind,
    CatalogSource,
)
from majesty_cam.manager.compatibility import (
    CombinationResolution,
    CompatibilityRegistry,
    CompatibilitySpec,
    ResolutionOwner,
    load_compatibility_registry,
)
from majesty_cam.manager.preflight import PreparedMergeMod
from majesty_cam.package import (
    ModDefinition, ModPackage, ModMetadata, LocalizedText,
    parse_mod_definition, mod_definition_mapping,
)


HAUNT_ID = "8C48289E-7C70-4426-8913-133F3544A182"
ALCHEMIST_ID = "42BA4603-2B13-446D-A2A4-6CF3A55DDAC3"
OTHER_ID = "48CDD934-B338-4373-A4A4-A99A8E7F917F"


class ManagerBuildPlanTests(unittest.TestCase):
    def test_map_query_package_gets_a_stable_feature_sensitive_scan_plan(self):
        self._query_feature_scan_plan(MapFogQueryFeature(), "map_fog_query", "stock.map-fog-query.v1")

    def test_movement_query_package_gets_a_stable_feature_sensitive_scan_plan(self):
        self._query_feature_scan_plan(MovementQueryFeature(), "movement_query", "stock.movement-query.v1")

    def test_native_timing_package_gets_a_stable_feature_sensitive_scan_plan(self):
        self._query_feature_scan_plan(NativeTimingFeature(), "native_timing", "stock.native-timing.v1")

    def _query_feature_scan_plan(self, feature, flag, capability):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = CompatibilityRegistry(specs={})
            definition = ModDefinition(3, OTHER_ID, "MapQueries", "Map Queries", (),
                                       runtime_features=(feature,))
            package = ModPackage(root, root / "package.mmxml",
                                 ModMetadata(OTHER_ID, (LocalizedText(None, "Map Queries"),), (), (), ()),
                                 definition)
            prepared = replace(_prepared(OTHER_ID, "Map Queries", root, registry=registry),
                               package=package, package_file_inputs=(),
                               inventory=PackageInventory(SelectedMod("other-cam", package), (), (), (), ()))
            catalog = Catalog(entries=(_merge_entry(OTHER_ID, "Map Queries", root),))
            with patch("majesty_cam.manager.build.prepare_merge_package", return_value=prepared):
                first = create_build_plan(catalog, {OTHER_ID: True}, registry=registry)
                again = create_build_plan(catalog, {OTHER_ID: True}, registry=registry)
            self.assertEqual(first.issues, ())
            self.assertTrue(getattr(first.runtime_feature_registry, flag))
            self.assertIn(capability, first.runtime_capabilities)
            self.assertEqual(first.fingerprint, again.fingerprint)
            changed_package = replace(package, definition=replace(definition, runtime_features=()))
            without_map = replace(prepared, package=changed_package,
                                  inventory=replace(prepared.inventory, selected=SelectedMod("other-cam", changed_package)))
            with patch("majesty_cam.manager.build.prepare_merge_package", return_value=without_map):
                changed = create_build_plan(catalog, {OTHER_ID: True}, registry=registry)
            self.assertNotEqual(first.fingerprint, changed.fingerprint)

    def test_fingerprint_uses_the_package_serializer_for_all_documented_features(self):
        value = json.loads((REPO_ROOT / "docs/examples/mod-definition-v3-all-features.json").read_text())
        value["runtime_features"].append({"type": "stock.map-fog-query.v1"})
        definition = parse_mod_definition(value)
        canonical = _canonical_mod_definition(definition)
        self.assertEqual(canonical, mod_definition_mapping(definition))
        self.assertEqual(parse_mod_definition(canonical), definition)

    def test_abandoned_manager_staging_is_removed_without_touching_foreign_data(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            mods.mkdir()
            target = mods / "Majesty Mod Manager - Merged"
            target.mkdir()
            (target / MANAGER_OUTPUT_SENTINEL).write_text("{}", encoding="utf-8")
            compose_staging = mods / ".manager-merged-abandoned"
            build_staging = mods / ".MajestyModManager-build-abandoned"
            foreign_backup = mods / f".{target.name}.backup-foreign"
            for path in (compose_staging, build_staging, foreign_backup):
                path.mkdir()
                (path / "payload").write_text("fixture", encoding="utf-8")

            _cleanup_stale_manager_artifacts(mods, target)

            self.assertFalse(compose_staging.exists())
            self.assertFalse(build_staging.exists())
            self.assertTrue(foreign_backup.is_dir())

    def test_interrupted_publication_recovers_last_manager_owned_backup(self):
        with TemporaryDirectory() as tmp:
            mods = Path(tmp) / "Mods"
            mods.mkdir()
            target = mods / "Majesty Mod Manager - Merged"
            backup = mods / f".{target.name}.backup-fixture"
            backup.mkdir()
            (backup / MANAGER_OUTPUT_SENTINEL).write_text("{}", encoding="utf-8")
            (backup / "completed.txt").write_text("safe", encoding="utf-8")

            _cleanup_stale_manager_artifacts(mods, target)

            self.assertFalse(backup.exists())
            self.assertEqual(
                (target / "completed.txt").read_text(encoding="utf-8"), "safe"
            )

    def test_detected_standard_dependency_overrides_saved_order_stably(self):
        prerequisite = CatalogEntry(
            content_id=HAUNT_ID,
            raw_content_id=HAUNT_ID,
            display_name="Original Component",
            kind=CatalogKind.STANDARD,
            source=CatalogSource.WORKSHOP,
            package_root=Path("original"),
            manifest_path=Path("original.mmxml"),
            has_cam=False,
            merge_ready=False,
        )
        patch_entry = CatalogEntry(
            content_id=ALCHEMIST_ID,
            raw_content_id=ALCHEMIST_ID,
            display_name="Patch Component",
            kind=CatalogKind.STANDARD,
            source=CatalogSource.WORKSHOP,
            package_root=Path("patch"),
            manifest_path=Path("patch.mmxml"),
            has_cam=False,
            merge_ready=False,
            load_after_ids=(HAUNT_ID,),
        )
        unrelated = CatalogEntry(
            content_id=OTHER_ID,
            raw_content_id=OTHER_ID,
            display_name="Unrelated",
            kind=CatalogKind.STANDARD,
            source=CatalogSource.WORKSHOP,
            package_root=Path("other"),
            manifest_path=Path("other.mmxml"),
            has_cam=False,
            merge_ready=False,
        )

        ordered = _order_standard_ids(
            (patch_entry, unrelated, prerequisite),
            {ALCHEMIST_ID: 0, OTHER_ID: 1, HAUNT_ID: 2},
        )

        self.assertLess(ordered.index(HAUNT_ID), ordered.index(ALCHEMIST_ID))
        self.assertEqual(set(ordered), {HAUNT_ID, ALCHEMIST_ID, OTHER_ID})

    def test_standard_relationships_block_missing_or_ambiguous_selections(self):
        original = _catalog_entry(HAUNT_ID, "Original Component")
        patch_entry = _catalog_entry(
            ALCHEMIST_ID,
            "Patch Component",
            required_ids=(HAUNT_ID,),
        )
        overlap = _catalog_entry(
            OTHER_ID,
            "Overlapping Mod",
            unresolved_overlap_ids=(ALCHEMIST_ID,),
        )
        patch_entry = replace(
            patch_entry,
            unresolved_overlap_ids=(OTHER_ID,),
        )
        catalog = Catalog(entries=(original, patch_entry, overlap))

        missing = standard_selection_issues(catalog, {ALCHEMIST_ID: True})
        self.assertEqual([issue.code for issue in missing], ["missing_required_mod"])

        ambiguous = standard_selection_issues(
            catalog,
            {HAUNT_ID: True, ALCHEMIST_ID: True, OTHER_ID: True},
        )
        self.assertEqual(
            [issue.code for issue in ambiguous],
            ["unresolved_standard_overlap"],
        )

        winner_key = standard_conflict_pair_key(ALCHEMIST_ID, OTHER_ID)
        resolved = standard_selection_issues(
            catalog,
            {HAUNT_ID: True, ALCHEMIST_ID: True, OTHER_ID: True},
            {winner_key: OTHER_ID},
        )
        self.assertEqual(resolved, ())
        ordered = _order_standard_ids(
            (overlap, patch_entry, original),
            {OTHER_ID: 0, ALCHEMIST_ID: 1, HAUNT_ID: 2},
            {winner_key: OTHER_ID},
        )
        self.assertLess(ordered.index(ALCHEMIST_ID), ordered.index(OTHER_ID))

    def test_standard_conflict_details_list_only_divergent_shared_changes(self):
        left = replace(
            _catalog_entry(HAUNT_ID, "Left Mod"),
            unresolved_overlap_ids=(ALCHEMIST_ID,),
            content_definitions=(("dat_block:shared", "left"), ("dat_block:same", "x")),
        )
        right = replace(
            _catalog_entry(ALCHEMIST_ID, "Right Mod"),
            unresolved_overlap_ids=(HAUNT_ID,),
            content_definitions=(("dat_block:shared", "right"), ("dat_block:same", "x")),
        )
        conflicts = standard_content_conflicts(
            Catalog(entries=(left, right)),
            {HAUNT_ID: True, ALCHEMIST_ID: True},
        )
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].change_keys, ("dat_block:shared",))

    def test_publication_rechecks_target_ownership_before_rename(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "Majesty Mod Manager - Merged"
            target.mkdir()
            (target / "foreign-file.txt").write_text("keep", encoding="utf-8")
            staging = root / ".MajestyModManager-build-fixture"
            staging.mkdir()
            (staging / "new-file.txt").write_text("new", encoding="utf-8")

            with self.assertRaisesRegex(
                ManagerBuildError, "non-manager directory during publication"
            ):
                _publish_staging(staging, target)

            self.assertEqual(
                (target / "foreign-file.txt").read_text(encoding="utf-8"), "keep"
            )
            self.assertTrue(staging.is_dir())

    def test_sentinel_symlink_never_grants_manager_ownership(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            mods = root / "Mods"
            target = mods / "Majesty Mod Manager - Merged"
            target.mkdir(parents=True)
            sentinel = target / MANAGER_OUTPUT_SENTINEL
            sentinel.write_text("{}", encoding="utf-8")
            game = root / "game"
            game.mkdir()
            executable = game / "MajestyHD.exe"
            executable.write_bytes(b"fixture")
            plan = SimpleNamespace(
                has_merge=True,
                valid=True,
                issues=(),
                stock_compose_inputs=(("fixture", "0" * 64),),
            )
            paths = SimpleNamespace(
                game_path=game,
                game_executable=executable,
                local_mods_root=mods,
                merged_output_root=target,
            )

            with patch.object(
                Path,
                "is_symlink",
                autospec=True,
                side_effect=lambda candidate: candidate == sentinel,
            ):
                self.assertFalse(_is_manager_owned_output(target))
                self.assertIsNone(read_managed_build(target))
                with self.assertRaisesRegex(
                    ManagerBuildError, "non-manager directory"
                ):
                    build_merged_package(plan, paths)

            self.assertTrue(target.is_dir())
            self.assertTrue(sentinel.is_file())

    def test_resolution_source_requires_complete_semantic_coverage(self):
        function_one = (
            "function First_Resolution() is integer\n"
            "begin\nreturn 1;\nend\n"
        )
        function_two = (
            "function Second_Resolution() is integer\n"
            "begin\nreturn 2;\nend\n"
        )
        cases = {
            "prefix": "Include \"hidden.gpl\"\n" + function_one,
            "middle": function_one + "UnknownDirective 7\n" + function_two,
            "trailing": function_one + "RunThread Hidden();\n",
        }
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            accepted = root / "comments-only.gpl"
            accepted.write_text(
                "// prefix\n" + function_one + "/* trailing */\n",
                encoding="cp1252",
            )
            self.assertEqual(len(_parse_resolution_source(accepted)), 1)
            for label, source_text in cases.items():
                with self.subTest(label=label):
                    source = root / f"{label}.gpl"
                    source.write_text(source_text, encoding="cp1252")
                    with self.assertRaisesRegex(
                        ManagerBuildError,
                        "unparsed content that cannot be preserved",
                    ):
                        _parse_resolution_source(source)

    def test_managed_build_requires_the_exact_fingerprinted_intent_registry(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_path = root / Path(INTENT_REGISTRY_RELATIVE_PATH)
            registry_path.parent.mkdir(parents=True)
            payload = encode_intent_registry(())
            registry_path.write_bytes(payload)
            manifest = root / "CAMManager-manager-merged.mmxml"
            manifest.write_text("<Majesty/>")
            capability_path = root / Path(
                RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH
            )
            capability_path.parent.mkdir(parents=True)
            capability_payload = encode_runtime_capability_manifest(())
            capability_path.write_bytes(capability_payload)
            capability_record = {
                "path": RUNTIME_CAPABILITY_MANIFEST_RELATIVE_PATH,
                "sha256": hashlib.sha256(capability_payload).hexdigest(),
                "record_count": 0,
            }
            feature_path = root / Path(RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH)
            feature_payload = encode_runtime_feature_registry(())
            feature_path.write_bytes(feature_payload)
            feature_record = {
                "path": RUNTIME_FEATURE_REGISTRY_RELATIVE_PATH,
                "sha256": hashlib.sha256(feature_payload).hexdigest(),
                "name_generator_count": 0,
                "enchantment_row_count": 0,
            }
            controller_path = root / CONTROLLER_REGISTRY_RELATIVE_PATH
            controller_payload = encode_stock_controller_registry(
                resolve_stock_controller_registry((), {})
            )
            controller_path.write_bytes(controller_payload)
            controller_record = {
                "path": CONTROLLER_REGISTRY_RELATIVE_PATH.as_posix(),
                "sha256": hashlib.sha256(controller_payload).hexdigest(),
                "record_count": 0,
            }
            report = root / "CAM-MERGE-REPORT.json"
            report.write_text(
                json.dumps(
                    {
                        "runtime": {
                            "capabilities": [],
                            "capability_manifest": capability_record,
                            "feature_registry": feature_record,
                            "controller_registry": controller_record,
                        }
                    }
                ),
                encoding="utf-8",
            )
            generated_resources = (
                root / "Data" / "Merged.bcd",
                root / "Data" / "merged_textdata.cam",
                root / "GPL" / "merged.gpl",
            )
            for item in generated_resources:
                item.parent.mkdir(parents=True, exist_ok=True)
                item.write_bytes(f"fixture:{item.name}".encode("ascii"))
            generated_files = [
                {
                    "path": item.relative_to(root).as_posix(),
                    "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
                }
                for item in sorted(
                    (item for item in root.rglob("*") if item.is_file()),
                    key=lambda item: item.relative_to(root).as_posix().casefold(),
                )
            ]
            sentinel = {
                "schema_version": 4,
                "fingerprint": "fixture",
                "mod_id": OTHER_ID,
                "selected_source_ids": [],
                "intent_registry": {
                    "path": INTENT_REGISTRY_RELATIVE_PATH,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "record_count": 0,
                },
                "capability_manifest": capability_record,
                "runtime_feature_registry": feature_record,
                "controller_registry": controller_record,
                "generated_files": generated_files,
            }
            (root / MANAGER_OUTPUT_SENTINEL).write_text(
                json.dumps(sentinel), encoding="utf-8"
            )

            package = SimpleNamespace(
                mod_id=OTHER_ID,
                definition=SimpleNamespace(
                    schema_version=2,
                    runtime_capabilities=(),
                ),
            )
            with patch(
                "majesty_cam.manager.build.validate_composed_package",
                return_value={"manifest": manifest.name},
            ), patch(
                "majesty_cam.manager.build.load_package", return_value=package
            ):
                self.assertIsNotNone(read_managed_build(root))
                protected = (
                    manifest,
                    report,
                    capability_path,
                    feature_path,
                    controller_path,
                    registry_path,
                    *generated_resources,
                )
                for protected_path in protected:
                    with self.subTest(tampered=protected_path.name):
                        original = protected_path.read_bytes()
                        protected_path.write_bytes(original + b"tampered")
                        self.assertIsNone(read_managed_build(root))
                        protected_path.write_bytes(original)
                deleted = generated_resources[0]
                original = deleted.read_bytes()
                deleted.unlink()
                self.assertIsNone(read_managed_build(root))
                deleted.write_bytes(original)
                extra = root / "unexpected.bin"
                extra.write_bytes(b"extra")
                self.assertIsNone(read_managed_build(root))
                extra.unlink()
                symlinks = (
                    (root / "unexpected-link.bin", manifest, False),
                    (root / "unexpected-link-dir", root / "Data", True),
                )
                for link, target, is_directory in symlinks:
                    try:
                        link.symlink_to(target, target_is_directory=is_directory)
                    except OSError:
                        continue
                    with self.subTest(symlink=link.name):
                        self.assertIsNone(read_managed_build(root))
                    link.unlink()

    def test_pair_resolution_is_applied_only_when_haunt_and_alchemist_are_selected(self):
        registry = load_compatibility_registry(repo_root=REPO_ROOT)
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_activity_inputs(root)
            haunt_root = root / "Haunt"
            alchemist_root = root / "Alchemist"
            haunt_root.mkdir()
            alchemist_root.mkdir()
            catalog = Catalog(
                entries=(
                    _merge_entry(HAUNT_ID, "Phantoms Haunt", haunt_root),
                    _merge_entry(ALCHEMIST_ID, "Alchemist Guild", alchemist_root),
                )
            )
            prepared = {
                HAUNT_ID: _prepared(
                    HAUNT_ID, "Phantoms Haunt", haunt_root, registry=registry
                ),
                ALCHEMIST_ID: _prepared(
                    ALCHEMIST_ID,
                    "Alchemist Guild",
                    alchemist_root,
                    registry=registry,
                ),
            }

            def prepare(**kwargs):
                return prepared[kwargs["content_id"]]

            discovered = allocate_private_activity_text_ids(
                (
                    (
                        "phantoms-haunt",
                        HAUNT_ID,
                        177,
                        ("#Arbitrary_Haunt_Text",),
                        "warning",
                    ),
                    (
                        "alchemist",
                        ALCHEMIST_ID,
                        309,
                        ("#Arbitrary_Oil_Text",),
                        "oil",
                    ),
                    (
                        "alchemist",
                        ALCHEMIST_ID,
                        310,
                        ("#Arbitrary_Phial_Text",),
                        "phial",
                    ),
                )
            )

            def discover(_game_path, selected):
                ids = {item.package.mod_id for item in selected}
                return tuple(
                    binding
                    for binding in discovered
                    if binding.source_mod_id in ids
                )

            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                side_effect=prepare,
            ), patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                side_effect=discover,
            ):
                haunt_only = create_build_plan(
                    catalog,
                    {HAUNT_ID: True, ALCHEMIST_ID: False},
                    registry=registry,
                    game_path=root,
                )
                alchemist_only = create_build_plan(
                    catalog,
                    {HAUNT_ID: False, ALCHEMIST_ID: True},
                    registry=registry,
                    game_path=root,
                )
                combined = create_build_plan(
                    catalog,
                    {HAUNT_ID: True, ALCHEMIST_ID: True},
                    registry=registry,
                    game_path=root,
                )

            self.assertEqual(haunt_only.semantic_resolutions, {})
            self.assertEqual(alchemist_only.semantic_resolutions, {})
            oil_only = next(
                item
                for item in alchemist_only.private_activity_texts
                if item.source_index == 309
            )
            oil_combined = next(
                item
                for item in combined.private_activity_texts
                if item.source_index == 309
            )
            self.assertEqual(oil_only.runtime_id, oil_combined.runtime_id)
            self.assertEqual(len(haunt_only.private_activity_texts), 1)
            self.assertEqual(len(combined.private_activity_texts), 3)
            self.assertIn(
                "private-activity-text-registry.v1",
                haunt_only.runtime_capabilities,
            )
            self.assertIn(
                "private-activity-text-registry.v1",
                combined.runtime_capabilities,
            )
            self.assertNotIn(
                "alchemist.ap78-private-oil-rows",
                haunt_only.runtime_capabilities,
            )
            for capability in (
                "alchemist.ap78-private-oil-rows",
                "alchemist.cgbrewing-secondary-controller",
                "alchemist.nm18-name-generator",
            ):
                self.assertIn(capability, alchemist_only.runtime_capabilities)
                self.assertIn(capability, combined.runtime_capabilities)
            self.assertEqual(
                set(combined.semantic_resolutions),
                {
                    (DefinitionKind.FUNCTION, "random_hero_type"),
                    (DefinitionKind.FUNCTION, "spell_extra_value"),
                },
            )
            self.assertTrue(combined.valid)

    def test_duplicate_effective_package_uuid_is_rejected_after_substitution(self):
        registry = CompatibilityRegistry(specs={})
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            roots = (root / "one", root / "two")
            for package_root in roots:
                package_root.mkdir()
            catalog = Catalog(
                entries=(
                    _merge_entry(HAUNT_ID, "One", roots[0]),
                    _merge_entry(ALCHEMIST_ID, "Two", roots[1]),
                )
            )
            for substitution_flags in ((False, True), (True, True)):
                prepared = []
                for index, (content_id, package_root) in enumerate(
                    zip((HAUNT_ID, ALCHEMIST_ID), roots)
                ):
                    item = _prepared(
                        content_id,
                        f"Item {index}",
                        package_root,
                        registry=registry,
                    )
                    prepared.append(
                        PreparedMergeMod(
                            **{
                                **item.__dict__,
                                "alias": f"item-{index}",
                                "package": SimpleNamespace(mod_id=OTHER_ID),
                                "substituted": substitution_flags[index],
                            }
                        )
                    )
                prepared_by_id = {
                    item.content_id: item for item in prepared
                }
                with self.subTest(substitutions=substitution_flags), patch(
                    "majesty_cam.manager.build.prepare_merge_package",
                    side_effect=lambda **kwargs: prepared_by_id[
                        kwargs["content_id"]
                    ],
                ):
                    plan = create_build_plan(
                        catalog,
                        {HAUNT_ID: True, ALCHEMIST_ID: True},
                        registry=registry,
                    )
                self.assertIn(
                    "duplicate_effective_mod_id",
                    [issue.code for issue in plan.issues],
                )

    def test_overlapping_n_way_combination_rules_fail_without_order_choice(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first_source = root / "first.gpl"
            second_source = root / "second.gpl"
            first_source.write_text(
                "function Shared_Resolution() is integer\n"
                "begin\nreturn 1;\nend\n",
                encoding="cp1252",
            )
            second_source.write_text(
                "function Shared_Resolution() is integer\n"
                "begin\nreturn 2;\nend\n",
                encoding="cp1252",
            )
            requested = ResolutionOwner(
                kind=DefinitionKind.FUNCTION,
                name="Shared_Resolution",
            )
            combinations = (
                CombinationResolution(
                    required_mod_ids=(HAUNT_ID, ALCHEMIST_ID),
                    source_path=first_source,
                    items=(requested,),
                ),
                CombinationResolution(
                    required_mod_ids=(ALCHEMIST_ID, OTHER_ID),
                    source_path=second_source,
                    items=(requested,),
                ),
            )
            registry = CompatibilityRegistry(
                specs={},
                combination_resolutions=combinations,
            )
            roots = {
                content_id: root / content_id
                for content_id in (HAUNT_ID, ALCHEMIST_ID, OTHER_ID)
            }
            for package_root in roots.values():
                package_root.mkdir()
            catalog = Catalog(
                entries=tuple(
                    _merge_entry(content_id, "Same Display Name", roots[content_id])
                    for content_id in roots
                )
            )
            prepared = {
                content_id: PreparedMergeMod(
                    content_id=content_id,
                    display_name="Same Display Name",
                    source_root=package_root,
                    effective_root=package_root,
                    alias=(
                        "same-display-name-"
                        + content_id.replace("-", "").casefold()
                    ),
                    package=SimpleNamespace(mod_id=content_id),
                    priority=1000,
                    runtime_capabilities=(),
                    badge=None,
                    substituted=False,
                    compatibility=None,
                    issues=(),
                )
                for content_id, package_root in roots.items()
            }

            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                side_effect=lambda **kwargs: prepared[kwargs["content_id"]],
            ):
                forward = create_build_plan(
                    catalog,
                    {content_id: True for content_id in roots},
                    registry=registry,
                )
                reversed_rules = create_build_plan(
                    catalog,
                    {content_id: True for content_id in roots},
                    registry=CompatibilityRegistry(
                        specs={},
                        combination_resolutions=tuple(reversed(combinations)),
                    ),
                )

            key = (DefinitionKind.FUNCTION, "shared_resolution")
            self.assertNotIn(key, forward.semantic_resolutions)
            self.assertNotIn(key, reversed_rules.semantic_resolutions)
            self.assertEqual(
                [issue.code for issue in forward.issues],
                ["duplicate_combination_resolution"],
            )
            self.assertEqual(forward.issues, reversed_rules.issues)
            self.assertFalse(forward.valid)

    def test_resolution_source_rejects_duplicate_requested_definition(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "duplicates.gpl"
            source.write_text(
                "function Repeated_Resolution() is integer\n"
                "begin\nreturn 1;\nend\n"
                "function Repeated_Resolution() is integer\n"
                "begin\nreturn 2;\nend\n",
                encoding="cp1252",
            )
            combination = CombinationResolution(
                required_mod_ids=(HAUNT_ID, ALCHEMIST_ID),
                source_path=source,
                items=(
                    ResolutionOwner(
                        kind=DefinitionKind.FUNCTION,
                        name="Repeated_Resolution",
                    ),
                ),
            )
            registry = CompatibilityRegistry(
                specs={},
                combination_resolutions=(combination,),
            )
            roots = {
                HAUNT_ID: root / "first",
                ALCHEMIST_ID: root / "second",
            }
            for package_root in roots.values():
                package_root.mkdir()
            catalog = Catalog(
                entries=tuple(
                    _merge_entry(content_id, content_id, package_root)
                    for content_id, package_root in roots.items()
                )
            )
            prepared = {
                content_id: PreparedMergeMod(
                    content_id=content_id,
                    display_name=content_id,
                    source_root=package_root,
                    effective_root=package_root,
                    alias="generic-" + content_id.casefold(),
                    package=SimpleNamespace(mod_id=content_id),
                    priority=1000,
                    runtime_capabilities=(),
                    badge=None,
                    substituted=False,
                    compatibility=None,
                    issues=(),
                )
                for content_id, package_root in roots.items()
            }

            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                side_effect=lambda **kwargs: prepared[kwargs["content_id"]],
            ):
                plan = create_build_plan(
                    catalog,
                    {content_id: True for content_id in roots},
                    registry=registry,
                )

            self.assertEqual(
                [issue.code for issue in plan.issues],
                ["invalid_combination_resolution"],
            )
            self.assertIn("duplicate function", plan.issues[0].message)

    def test_build_rejects_combination_resolution_source_mutation_after_prepare(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            _write_stock_activity_inputs(game)
            (game / "MajestyHD.exe").write_bytes(b"exe")
            source = root / "pair-resolution.gpl"
            source.write_text(
                "function Shared_Resolution() is integer\n"
                "begin\nreturn 1;\nend\n",
                encoding="cp1252",
            )
            combination = CombinationResolution(
                required_mod_ids=(HAUNT_ID, ALCHEMIST_ID),
                source_path=source,
                items=(
                    ResolutionOwner(
                        kind=DefinitionKind.FUNCTION,
                        name="Shared_Resolution",
                    ),
                ),
            )
            registry = CompatibilityRegistry(
                specs={},
                combination_resolutions=(combination,),
            )
            roots = {
                HAUNT_ID: root / "first",
                ALCHEMIST_ID: root / "second",
            }
            for package_root in roots.values():
                package_root.mkdir()
            catalog = Catalog(
                entries=tuple(
                    _merge_entry(content_id, content_id, package_root)
                    for content_id, package_root in roots.items()
                )
            )
            prepared = {
                content_id: PreparedMergeMod(
                    content_id=content_id,
                    display_name=content_id,
                    source_root=package_root,
                    effective_root=package_root,
                    alias="generic-" + content_id.casefold(),
                    package=SimpleNamespace(mod_id=content_id),
                    priority=1000,
                    runtime_capabilities=(),
                    badge=None,
                    substituted=False,
                    compatibility=None,
                    issues=(),
                )
                for content_id, package_root in roots.items()
            }
            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                side_effect=lambda **kwargs: prepared[kwargs["content_id"]],
            ), patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                return_value=(),
            ):
                plan = create_build_plan(
                    catalog,
                    {content_id: True for content_id in roots},
                    registry=registry,
                    game_path=game,
                )

            self.assertTrue(plan.valid)
            self.assertEqual(len(plan.compatibility_file_inputs), 1)
            source.write_text(
                "function Shared_Resolution() is integer\n"
                "begin\nreturn 2;\nend\n",
                encoding="cp1252",
            )
            paths = SimpleNamespace(
                game_path=game,
                game_executable=game / "MajestyHD.exe",
                local_mods_root=root / "Mods",
                merged_output_root=root / "Mods/Majesty Mod Manager - Merged",
            )
            with patch("majesty_cam.manager.build.compose_package") as composer:
                with self.assertRaisesRegex(
                    ManagerBuildError, "changed before composition"
                ):
                    build_merged_package(plan, paths)
            composer.assert_not_called()

    def test_fingerprint_is_stable_until_an_effective_package_changes(self):
        registry = CompatibilityRegistry(specs={})
        with TemporaryDirectory() as tmp:
            package_root = Path(tmp) / "MergeMod"
            package_root.mkdir()
            payload = package_root / "payload.bin"
            payload.write_bytes(b"first")
            catalog = Catalog(
                entries=(_merge_entry(OTHER_ID, "Other CAM", package_root),)
            )
            prepared = _prepared(
                OTHER_ID, "Other CAM", package_root, registry=registry
            )

            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                return_value=prepared,
            ):
                first = create_build_plan(
                    catalog, {OTHER_ID: True}, registry=registry
                )
                unchanged = create_build_plan(
                    catalog, {OTHER_ID: True}, registry=registry
                )
                original_stat = payload.stat()
                payload.write_bytes(b"other")
                os.utime(
                    payload,
                    ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
                )
                changed = create_build_plan(
                    catalog, {OTHER_ID: True}, registry=registry
                )

            self.assertEqual(first.fingerprint, unchanged.fingerprint)
            self.assertNotEqual(first.fingerprint, changed.fingerprint)

    def test_fingerprint_includes_external_adapter_and_canonical_definition(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_activity_inputs(root)
            (root / "MajestyHD.exe").write_bytes(b"exe")
            package_root = root / "MergeMod"
            package_root.mkdir()
            (package_root / "payload.bin").write_bytes(b"fixture")
            adapter_path = root / "adapter-definition.json"
            adapter_path.write_text('{"revision":1}', encoding="utf-8")
            spec = CompatibilitySpec(
                mod_id=OTHER_ID,
                alias="other-cam",
                definition_path=adapter_path,
                replacement_roots=(),
                merge_priority=1000,
                badge="Trusted adapter",
                runtime_capabilities=(
                    "expanded-building-slots.cg-prefix",
                    "freestyle-cam-rebind.v1",
                ),
                resolution_owners=(),
            )
            registry = CompatibilityRegistry(specs={OTHER_ID: spec})
            catalog = Catalog(
                entries=(_merge_entry(OTHER_ID, "Other CAM", package_root),)
            )
            first_definition = ModDefinition(
                schema_version=1,
                mod_id=OTHER_ID,
                internal_name="FirstAdapterDefinition",
                display_name="Other CAM",
                custom_buildings=(),
            )
            second_definition = ModDefinition(
                schema_version=1,
                mod_id=OTHER_ID,
                internal_name="SecondAdapterDefinition",
                display_name="Other CAM",
                custom_buildings=(),
            )

            def prepared(definition):
                value = _prepared(
                    OTHER_ID,
                    "Other CAM",
                    package_root,
                    registry=registry,
                )
                return PreparedMergeMod(
                    **{
                        **value.__dict__,
                        "package": SimpleNamespace(
                            mod_id=OTHER_ID,
                            definition=definition,
                        ),
                    }
                )

            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                return_value=prepared(first_definition),
            ), patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                return_value=(),
            ):
                first = create_build_plan(
                    catalog,
                    {OTHER_ID: True},
                    registry=registry,
                    game_path=root,
                )
                adapter_path.write_text('{"revision":2}', encoding="utf-8")
                with self.assertRaisesRegex(
                    ManagerBuildError, "changed after Prepare"
                ):
                    _require_current_plan_sources(
                        first,
                        game_path=root,
                        phase="after Prepare",
                    )
                adapter_changed = create_build_plan(
                    catalog,
                    {OTHER_ID: True},
                    registry=registry,
                    game_path=root,
                )

            adapter_path.write_text('{"revision":2}', encoding="utf-8")
            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                return_value=prepared(second_definition),
            ), patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                return_value=(),
            ):
                canonical_changed = create_build_plan(
                    catalog,
                    {OTHER_ID: True},
                    registry=registry,
                    game_path=root,
                )

            self.assertNotEqual(first.fingerprint, adapter_changed.fingerprint)
            self.assertNotEqual(
                adapter_changed.fingerprint,
                canonical_changed.fingerprint,
            )

    def test_fingerprint_includes_every_discovered_alias_deterministically(self):
        registry = CompatibilityRegistry(specs={})
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_stock_activity_inputs(root)
            package_root = root / "MergeMod"
            package_root.mkdir()
            (package_root / "payload.bin").write_bytes(b"fixture")
            catalog = Catalog(
                entries=(_merge_entry(OTHER_ID, "Other CAM", package_root),)
            )
            prepared = _prepared(
                OTHER_ID, "Other CAM", package_root, registry=registry
            )
            aliases_ab = allocate_private_activity_text_ids(
                (("other-cam", OTHER_ID, 77, ("#Beta", "#Alpha"), "text"),)
            )
            aliases_ba = allocate_private_activity_text_ids(
                (("other-cam", OTHER_ID, 77, ("#Alpha", "#Beta"), "text"),)
            )
            aliases_ac = allocate_private_activity_text_ids(
                (("other-cam", OTHER_ID, 77, ("#Alpha", "#Gamma"), "text"),)
            )

            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                return_value=prepared,
            ), patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                side_effect=(aliases_ab, aliases_ba, aliases_ac),
            ):
                first = create_build_plan(
                    catalog, {OTHER_ID: True}, registry=registry, game_path=root
                )
                reordered = create_build_plan(
                    catalog, {OTHER_ID: True}, registry=registry, game_path=root
                )
                changed = create_build_plan(
                    catalog, {OTHER_ID: True}, registry=registry, game_path=root
                )

            self.assertEqual(first.fingerprint, reordered.fingerprint)
            self.assertNotEqual(first.fingerprint, changed.fingerprint)

    def test_fingerprint_includes_complete_stock_compose_inputs(self):
        registry = CompatibilityRegistry(specs={})
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            _write_stock_activity_inputs(game)
            package_root = root / "MergeMod"
            package_root.mkdir()
            (package_root / "payload.bin").write_bytes(b"fixture")
            catalog = Catalog(
                entries=(_merge_entry(OTHER_ID, "Other CAM", package_root),)
            )
            prepared = _prepared(
                OTHER_ID, "Other CAM", package_root, registry=registry
            )

            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                return_value=prepared,
            ), patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                return_value=(),
            ):
                first = create_build_plan(
                    catalog, {OTHER_ID: True}, registry=registry, game_path=game
                )
                (game / "SDK/OriginalQuests/GPLMx/mx_defines.gpl").write_bytes(
                    b"changed stock defines"
                )
                changed = create_build_plan(
                    catalog, {OTHER_ID: True}, registry=registry, game_path=game
                )

            self.assertEqual(len(first.stock_compose_inputs), 13)
            self.assertEqual(
                dict(first.stock_compose_inputs)["DataMX/mx_maindata.cam"],
                "absent",
            )
            self.assertEqual(
                dict(first.stock_compose_inputs)["DataMX/mx_interfacedata.cam"],
                "absent",
            )
            self.assertEqual(
                dict(first.stock_compose_inputs)["DataMX/mx_textdata.cam"],
                "absent",
            )
            self.assertNotEqual(first.fingerprint, changed.fingerprint)
            (game / "MajestyHD.exe").write_bytes(b"exe")
            paths = SimpleNamespace(
                game_path=game,
                game_executable=game / "MajestyHD.exe",
                local_mods_root=root / "Mods",
                merged_output_root=root / "Mods/Majesty Mod Manager - Merged",
            )
            with patch("majesty_cam.manager.build.compose_package") as composer:
                with self.assertRaisesRegex(
                    ManagerBuildError, "changed before composition"
                ):
                    build_merged_package(first, paths)
            composer.assert_not_called()

    def test_stock_xml_change_addition_and_deletion_invalidate_plan(self):
        registry = CompatibilityRegistry(specs={})
        mutations = {
            "change": lambda game: (
                game / "SDK/OriginalQuests/Data/stock.xml"
            ).write_bytes(b"<Descriptions changed='yes' />"),
            "addition": lambda game: (
                game / "SDK/OriginalQuests/Data/new-stock.xml"
            ).write_bytes(b"<Descriptions />"),
            "deletion": lambda game: (
                game / "SDK/OriginalQuests/DataMX/stock-mx.xml"
            ).unlink(),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), TemporaryDirectory() as tmp:
                root = Path(tmp)
                game = root / "game"
                _write_stock_activity_inputs(game)
                package_root = root / "MergeMod"
                package_root.mkdir()
                (package_root / "payload.bin").write_bytes(b"fixture")
                catalog = Catalog(
                    entries=(
                        _merge_entry(OTHER_ID, "Other CAM", package_root),
                    )
                )
                prepared = _prepared(
                    OTHER_ID, "Other CAM", package_root, registry=registry
                )
                with patch(
                    "majesty_cam.manager.build.prepare_merge_package",
                    return_value=prepared,
                ), patch(
                    "majesty_cam.manager.build.discover_selected_private_activity_texts",
                    return_value=(),
                ):
                    plan = create_build_plan(
                        catalog,
                        {OTHER_ID: True},
                        registry=registry,
                        game_path=game,
                    )

                self.assertTrue(plan.valid)
                mutate(game)
                with self.assertRaisesRegex(
                    ManagerBuildError,
                    "stock composition inputs changed after Prepare",
                ):
                    _require_current_plan_sources(
                        plan,
                        game_path=game,
                        phase="after Prepare",
                    )

    def test_optional_mx_art_presence_hash_and_absence_invalidate_plan(self):
        registry = CompatibilityRegistry(specs={})
        optional_paths = (
            "DataMX/mx_maindata.cam",
            "DataMX/mx_interfacedata.cam",
        )
        mutations = (
            ("appears", None, b"appeared"),
            ("changes", b"original", b"changed"),
            ("disappears", b"original", None),
        )
        for relative in optional_paths:
            for label, initial, changed in mutations:
                with self.subTest(path=relative, mutation=label), TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    game = root / "game"
                    _write_stock_activity_inputs(game)
                    optional = game / relative
                    if initial is not None:
                        optional.parent.mkdir(parents=True, exist_ok=True)
                        optional.write_bytes(initial)
                    package_root = root / "MergeMod"
                    package_root.mkdir()
                    (package_root / "payload.bin").write_bytes(b"fixture")
                    catalog = Catalog(
                        entries=(
                            _merge_entry(OTHER_ID, "Other CAM", package_root),
                        )
                    )
                    prepared = _prepared(
                        OTHER_ID, "Other CAM", package_root, registry=registry
                    )
                    with patch(
                        "majesty_cam.manager.build.prepare_merge_package",
                        return_value=prepared,
                    ), patch(
                        "majesty_cam.manager.build.discover_selected_private_activity_texts",
                        return_value=(),
                    ):
                        before = create_build_plan(
                            catalog,
                            {OTHER_ID: True},
                            registry=registry,
                            game_path=game,
                        )
                        if changed is None:
                            optional.unlink()
                        else:
                            optional.parent.mkdir(parents=True, exist_ok=True)
                            optional.write_bytes(changed)
                        after = create_build_plan(
                            catalog,
                            {OTHER_ID: True},
                            registry=registry,
                            game_path=game,
                        )

                    self.assertTrue(before.valid)
                    self.assertTrue(after.valid)
                    self.assertNotEqual(before.fingerprint, after.fingerprint)
                    with self.assertRaisesRegex(
                        ManagerBuildError,
                        "stock composition inputs changed after Prepare",
                    ):
                        _require_current_plan_sources(
                            before,
                            game_path=game,
                            phase="after Prepare",
                        )

    def test_missing_or_symlinked_stock_input_fails_closed(self):
        registry = CompatibilityRegistry(specs={})
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            _write_stock_activity_inputs(game)
            package_root = root / "MergeMod"
            package_root.mkdir()
            (package_root / "payload.bin").write_bytes(b"fixture")
            catalog = Catalog(
                entries=(_merge_entry(OTHER_ID, "Other CAM", package_root),)
            )
            prepared = _prepared(
                OTHER_ID, "Other CAM", package_root, registry=registry
            )
            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                return_value=prepared,
            ), patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                return_value=(),
            ):
                plan = create_build_plan(
                    catalog,
                    {OTHER_ID: True},
                    registry=registry,
                    game_path=game,
                )

            fixed_input = game / "Data/textdata.cam"
            fixed_input.unlink()
            with self.assertRaisesRegex(
                ManagerBuildError,
                "stock composition inputs could not be revalidated after deletion",
            ):
                _require_current_plan_sources(
                    plan,
                    game_path=game,
                    phase="after deletion",
                )

            target = game / "Data/textdata-target.cam"
            target.write_bytes(b"replacement")
            try:
                fixed_input.symlink_to(target)
            except OSError:
                self.skipTest("file symlinks are unavailable on this Windows host")
            with self.assertRaisesRegex(
                ManagerBuildError,
                "stock composition inputs could not be revalidated after symlink",
            ):
                _require_current_plan_sources(
                    plan,
                    game_path=game,
                    phase="after symlink",
                )

    def test_prepare_does_not_reparse_an_unchanged_package(self):
        registry = CompatibilityRegistry(specs={})
        with TemporaryDirectory() as tmp:
            package_root = Path(tmp) / "MergeMod"
            package_root.mkdir()
            (package_root / "payload.bin").write_bytes(b"current bytes")
            catalog = Catalog(
                entries=(_merge_entry(OTHER_ID, "Other CAM", package_root),)
            )
            first = _prepared(
                OTHER_ID, "Other CAM", package_root, registry=registry
            )
            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                return_value=first,
            ) as prepare:
                plan = create_build_plan(
                    catalog,
                    {OTHER_ID: True},
                    registry=registry,
                )

            prepare.assert_called_once()
            self.assertTrue(plan.valid)

    def test_build_reuses_prepared_activity_text_without_rediscovery(self):
        registry = CompatibilityRegistry(specs={})
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            game = root / "game"
            _write_stock_activity_inputs(game)
            (game / "MajestyHD.exe").write_bytes(b"exe")
            package_root = root / "MergeMod"
            package_root.mkdir()
            (package_root / "payload.bin").write_bytes(b"fixture")
            catalog = Catalog(
                entries=(_merge_entry(OTHER_ID, "Other CAM", package_root),)
            )
            prepared = _prepared(
                OTHER_ID, "Other CAM", package_root, registry=registry
            )
            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                return_value=prepared,
            ), patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                return_value=(),
            ):
                plan = create_build_plan(
                    catalog, {OTHER_ID: True}, registry=registry, game_path=game
                )

            paths = SimpleNamespace(
                game_path=game,
                game_executable=game / "MajestyHD.exe",
                local_mods_root=root / "Mods",
                merged_output_root=root / "Mods/Majesty Mod Manager - Merged",
            )
            newly_discovered = allocate_private_activity_text_ids(
                (("other-cam", OTHER_ID, 77, (), "new private text"),)
            )
            with patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                return_value=newly_discovered,
            ) as discover, patch(
                "majesty_cam.manager.build.compose_package",
                side_effect=ComposeError("fixture stop"),
            ) as composer:
                with self.assertRaisesRegex(ManagerBuildError, "fixture stop"):
                    build_merged_package(plan, paths)

            discover.assert_not_called()
            self.assertEqual(
                composer.call_args.kwargs["private_activity_texts"],
                plan.private_activity_texts,
            )

    def test_build_refuses_source_mutation_during_composition(self):
        registry = CompatibilityRegistry(specs={})
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            package_root = root / "MergeMod"
            package_root.mkdir()
            payload = package_root / "payload.bin"
            payload.write_bytes(b"first!")
            catalog = Catalog(
                entries=(_merge_entry(OTHER_ID, "Other CAM", package_root),)
            )
            prepared = _prepared(
                OTHER_ID, "Other CAM", package_root, registry=registry
            )
            game = root / "game"
            _write_stock_activity_inputs(game)
            (game / "MajestyHD.exe").write_bytes(b"exe")
            with patch(
                "majesty_cam.manager.build.prepare_merge_package",
                return_value=prepared,
            ), patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                return_value=(),
            ):
                plan = create_build_plan(
                    catalog, {OTHER_ID: True}, registry=registry, game_path=game
                )

            mods = root / "Mods"
            paths = SimpleNamespace(
                game_path=game,
                game_executable=game / "MajestyHD.exe",
                local_mods_root=mods,
                merged_output_root=mods / "Majesty Mod Manager - Merged",
            )

            def compose(_game, staging, _selected, **_kwargs):
                staging.mkdir(parents=True)
                payload.write_bytes(b"second")
                return SimpleNamespace()

            with patch(
                "majesty_cam.manager.build.compose_package", side_effect=compose
            ) as composer, patch(
                "majesty_cam.manager.build.discover_selected_private_activity_texts",
                return_value=(),
            ):
                with self.assertRaisesRegex(
                    ManagerBuildError, "changed during composition"
                ):
                    build_merged_package(plan, paths)

            composer.assert_called_once()
            self.assertFalse(paths.merged_output_root.exists())
            self.assertEqual(
                list(mods.glob(".MajestyModManager-build-*")),
                [],
            )


def _merge_entry(content_id: str, display_name: str, root: Path) -> CatalogEntry:
    return CatalogEntry(
        content_id=content_id,
        raw_content_id=content_id,
        display_name=display_name,
        kind=CatalogKind.MERGE,
        source=CatalogSource.LOCAL_MODS,
        package_root=root,
        manifest_path=root / "package.mmxml",
        has_cam=True,
        merge_ready=True,
    )


def _catalog_entry(
    content_id: str,
    display_name: str,
    **values,
) -> CatalogEntry:
    return CatalogEntry(
        content_id=content_id,
        raw_content_id=content_id,
        display_name=display_name,
        kind=CatalogKind.STANDARD,
        source=CatalogSource.WORKSHOP,
        package_root=Path(display_name),
        manifest_path=Path(f"{display_name}.mmxml"),
        has_cam=False,
        merge_ready=False,
        **values,
    )


def _prepared(
    content_id: str,
    display_name: str,
    root: Path,
    *,
    registry: CompatibilityRegistry,
) -> PreparedMergeMod:
    spec = registry.get(content_id)
    return PreparedMergeMod(
        content_id=content_id,
        display_name=display_name,
        source_root=root,
        effective_root=root,
        alias=spec.alias if spec is not None else "other-cam",
        package=SimpleNamespace(mod_id=content_id),
        priority=spec.merge_priority if spec is not None else 1000,
        runtime_capabilities=(
            spec.runtime_capabilities
            if spec is not None
            else ("expanded-building-slots.cg-prefix", "freestyle-cam-rebind.v1")
        ),
        badge=spec.badge if spec is not None else None,
        substituted=False,
        compatibility=spec,
        issues=(),
    )


def _write_stock_activity_inputs(game: Path) -> None:
    payloads = {
        "Data/textdata.cam": b"stock text CAM",
        "Data/miscdata.cam": b"stock Original misc CAM",
        "Data/maindata.cam": b"stock main CAM",
        "Data/interfacedata.cam": b"stock interface CAM",
        "DataMX/mx_gpltext.cam": b"stock AITX CAM",
        "DataMX/mx_miscdata.cam": b"stock misc CAM",
        "SDK/Gplbcc.exe": b"stock GPL compiler",
        "SDK/OriginalQuests/GPLMx/mx_defines.gpl": b"stock activity defines",
        "SDK/OriginalQuests/Data/stock.xml": b"<Descriptions />",
        "SDK/OriginalQuests/DataMX/stock-mx.xml": b"<Descriptions />",
    }
    for relative, payload in payloads.items():
        path = game / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


if __name__ == "__main__":
    unittest.main()

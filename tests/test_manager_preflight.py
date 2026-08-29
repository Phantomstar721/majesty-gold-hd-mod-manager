from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.compatibility import (
    CompatibilityRegistry,
    CompatibilitySpec,
)
from majesty_cam.manager.preflight import prepare_merge_package
from majesty_cam.package import ModDefinition


MOD_ID = "5F6B48D1-7B27-4D0E-92A4-52F12A997384"
OTHER_MOD_ID = "818F1460-3095-4B42-A64C-D55C11D7624E"


class ManagerPreflightTests(unittest.TestCase):
    def test_trusted_adapter_cannot_remove_generic_runtime_prerequisites(self):
        definition = ModDefinition(
            schema_version=1,
            mod_id=MOD_ID,
            internal_name="LegacyFixture",
            display_name="Legacy Fixture",
            custom_buildings=(),
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter_path = root / "adapter.json"
            adapter_path.write_text("{}", encoding="utf-8")
            spec = CompatibilitySpec(
                mod_id=MOD_ID,
                alias="legacy-fixture",
                definition_path=adapter_path,
                replacement_roots=(),
                merge_priority=1000,
                badge="Trusted adapter",
                runtime_capabilities=(),
                resolution_owners=(),
            )
            package = SimpleNamespace(
                definition=definition,
                mod_id=MOD_ID,
                manifest_path=root / "fixture.mmxml",
            )
            with patch(
                "majesty_cam.manager.preflight.load_package", return_value=package
            ), patch("majesty_cam.manager.preflight._validate_package"):
                result = prepare_merge_package(
                    content_id=MOD_ID,
                    display_name="Legacy Fixture",
                    source_root=root,
                    registry=CompatibilityRegistry(specs={MOD_ID: spec}),
                )
        self.assertEqual(
            result.runtime_capabilities,
            (
                "expanded-building-slots.cg-prefix",
                "freestyle-cam-rebind.v1",
            ),
        )
        self.assertFalse(result.issues)

    def test_direct_package_identity_must_match_catalog_but_substitution_may_differ(self):
        definition = ModDefinition(
            schema_version=2,
            mod_id=OTHER_MOD_ID,
            internal_name="ReplacementFixture",
            display_name="Replacement Fixture",
            custom_buildings=(),
            runtime_capabilities=(),
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            replacement = root / "replacement"
            replacement.mkdir()
            adapter_path = root / "adapter.json"
            adapter_path.write_text("{}", encoding="utf-8")
            package = SimpleNamespace(
                definition=definition,
                mod_id=OTHER_MOD_ID,
                manifest_path=replacement / "fixture.mmxml",
            )
            spec = CompatibilitySpec(
                mod_id=MOD_ID,
                alias="replacement-fixture",
                definition_path=adapter_path,
                replacement_roots=(replacement,),
                merge_priority=1000,
                badge="Trusted replacement",
                runtime_capabilities=(),
                resolution_owners=(),
            )
            with patch(
                "majesty_cam.manager.preflight.load_package", return_value=package
            ), patch("majesty_cam.manager.preflight._validate_package"):
                direct = prepare_merge_package(
                    content_id=MOD_ID,
                    display_name="Direct Fixture",
                    source_root=replacement,
                    registry=CompatibilityRegistry(specs={}),
                )
                substituted = prepare_merge_package(
                    content_id=MOD_ID,
                    display_name="Replacement Fixture",
                    source_root=root / "workshop",
                    registry=CompatibilityRegistry(specs={MOD_ID: spec}),
                )
        self.assertIn("stale_catalog_identity", [item.code for item in direct.issues])
        self.assertNotIn(
            "stale_catalog_identity", [item.code for item in substituted.issues]
        )

    def test_generic_same_display_names_receive_uuid_unique_aliases(self):
        definition = ModDefinition(
            schema_version=2,
            mod_id=MOD_ID,
            internal_name="AliasFixture",
            display_name="Same Display Name",
            custom_buildings=(),
            runtime_capabilities=(),
        )
        package = SimpleNamespace(
            definition=definition, mod_id=MOD_ID, manifest_path=Path("fixture.mmxml")
        )
        with TemporaryDirectory() as tmp, patch(
            "majesty_cam.manager.preflight.load_package",
            return_value=package,
        ), patch("majesty_cam.manager.preflight._validate_package"):
            first = prepare_merge_package(
                content_id=MOD_ID,
                display_name="Same Display Name",
                source_root=Path(tmp),
                registry=CompatibilityRegistry(specs={}),
            )
            second = prepare_merge_package(
                content_id=OTHER_MOD_ID,
                display_name="Same Display Name",
                source_root=Path(tmp),
                registry=CompatibilityRegistry(specs={}),
            )

        self.assertNotEqual(first.alias, second.alias)
        self.assertTrue(first.alias.startswith("same-display-name-"))
        self.assertTrue(first.alias.endswith(MOD_ID.replace("-", "").casefold()))
        self.assertTrue(second.alias.endswith(OTHER_MOD_ID.replace("-", "").casefold()))

    def test_schema_v1_package_requires_trusted_compatibility_spec(self):
        definition = ModDefinition(
            schema_version=1,
            mod_id=MOD_ID,
            internal_name="LegacyFixture",
            display_name="Legacy Fixture",
            custom_buildings=(),
        )
        package = SimpleNamespace(
            definition=definition, mod_id=MOD_ID, manifest_path=Path("fixture.mmxml")
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            adapter_path = root / "trusted-adapter.json"
            adapter_path.write_text("{}", encoding="utf-8")
            spec = CompatibilitySpec(
                mod_id=MOD_ID,
                alias="legacy-fixture",
                definition_path=adapter_path,
                replacement_roots=(),
                merge_priority=1000,
                badge="Trusted compatibility adapter",
                runtime_capabilities=(
                    "expanded-building-slots.cg-prefix",
                    "freestyle-cam-rebind.v1",
                ),
                resolution_owners=(),
            )
            with patch(
                "majesty_cam.manager.preflight.load_package",
                return_value=package,
            ), patch("majesty_cam.manager.preflight._validate_package"):
                unadapted = prepare_merge_package(
                    content_id=MOD_ID,
                    display_name="Legacy Fixture",
                    source_root=root,
                    registry=CompatibilityRegistry(specs={}),
                )
                adapted = prepare_merge_package(
                    content_id=MOD_ID,
                    display_name="Legacy Fixture",
                    source_root=root,
                    registry=CompatibilityRegistry(specs={MOD_ID: spec}),
                )

        self.assertIn(
            "legacy_merge_definition_requires_adapter",
            [issue.code for issue in unadapted.issues],
        )
        self.assertFalse(adapted.issues)

    def test_v2_package_runtime_capabilities_join_generic_launcher_features(self):
        definition = ModDefinition(
            schema_version=2,
            mod_id=MOD_ID,
            internal_name="CapabilityFixture",
            display_name="Capability Fixture",
            custom_buildings=(),
            runtime_capabilities=("alchemist.nm18-name-generator",),
        )
        package = SimpleNamespace(
            definition=definition, mod_id=MOD_ID, manifest_path=Path("fixture.mmxml")
        )
        with TemporaryDirectory() as tmp, patch(
            "majesty_cam.manager.preflight.load_package",
            return_value=package,
        ), patch("majesty_cam.manager.preflight._validate_package"):
            result = prepare_merge_package(
                content_id=MOD_ID,
                display_name="Capability Fixture",
                source_root=Path(tmp),
                registry=CompatibilityRegistry(specs={}),
            )

        self.assertEqual(
            result.runtime_capabilities,
            (
                "expanded-building-slots.cg-prefix",
                "freestyle-cam-rebind.v1",
                "alchemist.nm18-name-generator",
            ),
        )
        self.assertFalse(result.issues)

    def test_private_activity_text_capability_is_manager_derived_only(self):
        definition = ModDefinition(
            schema_version=2,
            mod_id=MOD_ID,
            internal_name="InvalidCapabilityFixture",
            display_name="Invalid Capability Fixture",
            custom_buildings=(),
            runtime_capabilities=("private-activity-text-registry.v1",),
        )
        package = SimpleNamespace(
            definition=definition,
            mod_id=MOD_ID,
            manifest_path=Path("fixture.mmxml"),
        )
        with TemporaryDirectory() as tmp, patch(
            "majesty_cam.manager.preflight.load_package",
            return_value=package,
        ), patch("majesty_cam.manager.preflight._validate_package"):
            result = prepare_merge_package(
                content_id=MOD_ID,
                display_name="Invalid Capability Fixture",
                source_root=Path(tmp),
                registry=CompatibilityRegistry(specs={}),
            )
        self.assertEqual(
            [issue.code for issue in result.issues],
            ["reserved_runtime_capability"],
        )
        self.assertNotIn(
            "private-activity-text-registry.v1", result.runtime_capabilities
        )

    def test_unknown_v2_runtime_capability_fails_closed(self):
        definition = ModDefinition(
            schema_version=2,
            mod_id=MOD_ID,
            internal_name="CapabilityFixture",
            display_name="Capability Fixture",
            custom_buildings=(),
            runtime_capabilities=("example.future-runtime.v9",),
        )
        package = SimpleNamespace(
            definition=definition, mod_id=MOD_ID, manifest_path=Path("fixture.mmxml")
        )
        with TemporaryDirectory() as tmp, patch(
            "majesty_cam.manager.preflight.load_package",
            return_value=package,
        ), patch("majesty_cam.manager.preflight._validate_package"):
            result = prepare_merge_package(
                content_id=MOD_ID,
                display_name="Capability Fixture",
                source_root=Path(tmp),
                registry=CompatibilityRegistry(specs={}),
            )

        self.assertEqual(
            [issue.code for issue in result.issues],
            ["unsupported_runtime_capability"],
        )
        self.assertIn("example.future-runtime.v9", result.issues[0].message)


if __name__ == "__main__":
    unittest.main()

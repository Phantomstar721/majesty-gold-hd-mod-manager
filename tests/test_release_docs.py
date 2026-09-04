from pathlib import Path
import json
import re
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.package import parse_mod_definition


class ReleaseDocumentationTests(unittest.TestCase):
    def test_public_schema_v3_all_features_example_matches_the_parser(self):
        path = REPO_ROOT / "docs/examples/mod-definition-v3-all-features.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        definition = parse_mod_definition(value)
        self.assertEqual(definition.schema_version, 3)
        self.assertNotIn("dialog_id", value["custom_buildings"][0])
        feature_types = {item["type"] for item in value["runtime_features"]}
        self.assertEqual(
            feature_types,
            {
                "stock.name-generator.v1",
                "stock.ap78-enchantment-row.v1",
                "stock.ap10-ap69-secondary-panel.v1",
                "stock.mx09-ap41-reward-panel.v1",
                "stock.ap41-fl00-hostile-monster-flag.v1",
                "stock.mx22-building-open-toggle.v1",
                "stock.gplmx-purchase-equipment-tail.v1",
                "stock.gplmx-purchase-bazaar-tail.v1",
                "stock.ap22-resource-meter.v1",
                "stock.ap99-research-row.v1",
                "stock.ap17-upgrade-research-gate.v1",
                "stock.ap24-timed-rage-action.v1",
                "stock.ap24-rage-command-action.v1",
                "stock.ap69-sovereign-target-action.v1",
            },
        )
        sovereign = next(
            item
            for item in value["runtime_features"]
            if item["type"] == "stock.ap69-sovereign-target-action.v1"
        )
        self.assertEqual(sovereign["stock_executor_mode"], "Sp14")

    def test_public_readme_is_player_facing_and_links_release_documents(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "# Majesty Mod Manager",
            "## Install and use",
            "## Compatibility and safety",
            "## License",
            "THIRD-PARTY-NOTICES.md",
            "docs/manager-merge-contract.md",
        ):
            self.assertIn(required, text)
        for forbidden in (
            r"C:\Users\bterr",
            "local/poc",
            "reference-repos/",
            "rejected approach",
            "failure commentary",
        ):
            self.assertNotIn(forbidden.casefold(), text.casefold())

    def test_workshop_project_has_one_generated_location(self):
        self.assertFalse((REPO_ROOT / "workshop").exists())
        script = (REPO_ROOT / "scripts/Stage-Workshop.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn('Join-Path $distRoot "workshop-upload"', script)
        self.assertIn('$projectName = "MajestyModManager.mswproj"', script)
        self.assertNotIn("$projectSource", script)

    def test_workshop_text_is_the_generated_project_description(self):
        canonical = (REPO_ROOT / "WORKSHOP.md").read_text(encoding="utf-8")
        self.assertIn("majesty-gold-hd-mod-manager", canonical)
        self.assertNotIn("majesty-gold-hd-cam-merger", canonical)
        script = (REPO_ROOT / "scripts/Stage-Workshop.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn('$descriptionSource = Join-Path $repoRoot "WORKSHOP.md"', script)
        self.assertIn("<Description lang=", script)

    def test_release_licenses_and_workshop_sources_are_present(self):
        required = (
            "LICENSE",
            "THIRD-PARTY-NOTICES.md",
            "WORKSHOP.md",
            "release/START HERE.txt",
            "artwork/workshop-preview.jpg",
            "licenses/PYTHON-3.9.txt",
            "licenses/LGPL-3.0.txt",
            "licenses/GPL-3.0.txt",
            "licenses/PYINSTALLER.txt",
            "licenses/FREESTYLE-CAM-SIDECAR.txt",
            "runtime/MajestyBuildingRuntimeLauncher.cpp",
            "runtime/FreestyleCamRuntime.cpp",
            "scripts/Build-Runtime.ps1",
            "scripts/Stage-Workshop.ps1",
        )
        missing = [item for item in required if not (REPO_ROOT / item).is_file()]
        self.assertEqual(missing, [])

    def test_workshop_copy_does_not_claim_the_exe_is_standalone(self):
        instructions = (REPO_ROOT / "release/START HERE.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn('requires the\nnearby "_internal" folder', instructions)
        self.assertIn("Always launch through the manager", instructions)
        self.assertNotRegex(instructions, re.compile(r"nothing to install", re.I))

    def test_application_build_copies_release_licenses(self):
        script = (REPO_ROOT / "scripts/Build-ModManagerExe.ps1").read_text(
            encoding="utf-8-sig"
        )
        for required in (
            "START HERE.txt",
            "LICENSE.txt",
            "THIRD-PARTY-NOTICES.md",
            "PYTHON-3.9.txt",
            "LGPL-3.0.txt",
            "GPL-3.0.txt",
            "PYINSTALLER.txt",
            "FREESTYLE-CAM-SIDECAR.txt",
            "STEAM-ICON-NOTICE.txt",
        ):
            self.assertIn(required, script)

    def test_native_runtime_is_built_from_manager_owned_source(self):
        stage_script = (
            REPO_ROOT / "scripts/Stage-ModManagerPayload.ps1"
        ).read_text(encoding="utf-8-sig")
        notices = (REPO_ROOT / "THIRD-PARTY-NOTICES.md").read_text(
            encoding="utf-8"
        )
        self.assertIn('Join-Path $repoRoot "scripts\\Build-Runtime.ps1"', stage_script)
        self.assertIn('Join-Path $repoRoot "runtime\\MajestyBuildingRuntimeLauncher.cpp"', stage_script)
        self.assertNotIn("majesty-gold-hd-expanded-building-slots", stage_script)
        self.assertNotIn("majesty-gold-hd-expanded-building-slots", notices)
        self.assertIn("majesty-gold-hd-mod-manager/tree/main/runtime", notices)

    def test_workshop_stager_generates_the_canonical_project_paths(self):
        script = (REPO_ROOT / "scripts/Stage-Workshop.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("$finalContentPath", script)
        self.assertIn("$finalPreviewPath", script)
        self.assertIn("<ContentPath>$finalContentPath</ContentPath>", script)
        self.assertIn("<PreviewImagePath>$finalPreviewPath</PreviewImagePath>", script)
        self.assertIn('[string]$ApplicationRoot = ""', script)
        self.assertIn('[string]$WorkshopId = "3793024054"', script)

    def test_workshop_stager_preserves_user_added_files(self):
        script = (REPO_ROOT / "scripts/Stage-Workshop.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("$managedRootNames", script)
        self.assertIn("$userFileBackupRoot", script)
        self.assertIn("workshop-user-files-backup", script)
        self.assertIn("$_.Name -notin $managedRootNames", script)
        self.assertIn(
            "Copy-Item -LiteralPath $item.FullName -Destination $stage",
            script,
        )
        self.assertIn(
            "Copy-Item -LiteralPath $item.FullName -Destination $userFileBackupRoot",
            script,
        )


if __name__ == "__main__":
    unittest.main()

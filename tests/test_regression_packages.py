"""Read-only admission of the actual development test loadout on all builds."""
import os
from pathlib import Path
import unittest
from contextlib import ExitStack
from unittest.mock import patch
import xml.etree.ElementTree as ET
from majesty_cam.manager.compatibility import load_compatibility_registry
from majesty_cam.manager.preflight import prepare_merge_package, prepared_catalog_merge_preflight
from majesty_cam.manager import preflight
from majesty_cam import native_impact

ROOT = Path(__file__).resolve().parents[1]

class InstalledPackageAdmissionTests(unittest.TestCase):
    def test_actual_guilds_on_each_supported_profile(self):
        game = Path(os.environ.get("MAJESTY_STOCK_ROOT", str(Path(os.environ["MAJESTY_PUBLIC_EXE"]).parent)))
        workshop = game.parents[1] / "workshop/content/73230"
        development = Path(os.environ.get("MAJESTY_DEVELOPMENT_PACKAGE",
            str(Path(os.environ["USERPROFILE"]) / "Documents/My Games/MajestyHD/Mods/WitchHunterFourSkills")))
        roots = [workshop / item for item in ("3813128205", "3793509198", "3769947406")] + [development]
        registry = load_compatibility_registry(repo_root=ROOT)
        for root in roots:
            manifests = sorted(root.glob("*.mmxml"))
            self.assertEqual(len(manifests), 1, str(root) + ": required regression package unavailable")
            for mod in ET.parse(manifests[0]).getroot().findall("Mod"):
                package = prepare_merge_package(content_id=mod.attrib["id"], display_name=str(root.name),
                                                source_root=root, registry=registry)
                self.assertFalse(package.issues, str(root) + ": " + "; ".join(i.message for i in package.issues))
                for branch in ("PUBLIC", "BETA2", "GOG"):
                    with self.subTest(package=str(root), profile=branch):
                        executable = Path(os.environ["MAJESTY_" + branch + "_EXE"])
                        # Redirect only the fixture path; execute every real guard.
                        # Stock data remains read-only at game, never copied into Mods.
                        with ExitStack() as stack:
                            for module, name in ((native_impact, 'require_exact_profile'),
                                    (preflight, 'require_attack_observation_profile'),
                                    (preflight, 'require_exploration_profile'),
                                    (preflight, 'require_supported_runtime')):
                                original = getattr(module, name)
                                stack.enter_context(patch.object(module, name,
                                    side_effect=lambda path, guard=original: guard(executable)))
                            issues = prepared_catalog_merge_preflight(package, game_path=game)
                        self.assertFalse(issues, "; ".join(i.message for i in issues))


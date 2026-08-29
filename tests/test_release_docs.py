from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


class ReleaseDocumentationTests(unittest.TestCase):
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

    def test_workshop_project_is_private_and_points_at_staged_content(self):
        project = REPO_ROOT / "workshop/MajestyModManager.mswproj"
        root = ET.fromstring(project.read_text(encoding="utf-8"))
        workshop = root.find("SteamWorkshop")
        self.assertIsNotNone(workshop)
        assert workshop is not None
        self.assertEqual(workshop.attrib["id"], "0")
        self.assertEqual(workshop.attrib["visibility"], "Private")
        self.assertEqual(workshop.findtext("Title"), "Majesty Mod Manager")
        self.assertTrue(
            workshop.findtext("ContentPath", "").endswith(
                r"dist\workshop-upload\content"
            )
        )
        self.assertTrue(
            workshop.findtext("PreviewImagePath", "").endswith(
                r"dist\workshop-upload\workshop-preview.jpg"
            )
        )
        self.assertIn("private-preview", workshop.findtext("Description", ""))
        self.assertNotIn(
            r"C:\Users", project.read_text(encoding="utf-8"),
            "the tracked Workshop template must remain portable",
        )

    def test_release_licenses_and_workshop_sources_are_present(self):
        required = (
            "LICENSE",
            "THIRD-PARTY-NOTICES.md",
            "WORKSHOP.md",
            "workshop/START HERE.txt",
            "workshop/workshop-preview.jpg",
            "licenses/PYTHON-3.9.txt",
            "licenses/LGPL-3.0.txt",
            "licenses/GPL-3.0.txt",
            "licenses/PYINSTALLER.txt",
            "scripts/Stage-Workshop.ps1",
        )
        missing = [item for item in required if not (REPO_ROOT / item).is_file()]
        self.assertEqual(missing, [])

    def test_workshop_copy_does_not_claim_the_exe_is_standalone(self):
        instructions = (REPO_ROOT / "workshop/START HERE.txt").read_text(
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
            "LICENSE.txt",
            "THIRD-PARTY-NOTICES.md",
            "PYTHON-3.9.txt",
            "LGPL-3.0.txt",
            "GPL-3.0.txt",
            "PYINSTALLER.txt",
            "STEAM-ICON-NOTICE.txt",
        ):
            self.assertIn(required, script)

    def test_workshop_stager_resolves_portable_template_paths(self):
        script = (REPO_ROOT / "scripts/Stage-Workshop.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("$finalContentPath", script)
        self.assertIn("$finalPreviewPath", script)
        self.assertIn("<ContentPath>.*?</ContentPath>", script)
        self.assertIn("<PreviewImagePath>.*?</PreviewImagePath>", script)


if __name__ == "__main__":
    unittest.main()

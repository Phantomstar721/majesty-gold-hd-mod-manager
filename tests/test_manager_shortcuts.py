from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from majesty_cam.manager.shortcuts import (
    SHORTCUT_NAME,
    ShortcutError,
    create_manager_desktop_shortcut,
)


class DesktopShortcutTests(unittest.TestCase):
    def test_creates_shortcut_to_complete_manager_installation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            application = root / "Workshop Item" / "Majesty Mod Manager.exe"
            application.parent.mkdir()
            application.write_bytes(b"fixture")
            desktop = root / "OneDrive" / "Desktop"
            desktop.mkdir(parents=True)
            calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

            def runner(command, **options):
                calls.append((tuple(command), options))
                environment = options["env"]
                Path(environment["MMM_SHORTCUT_PATH"]).write_bytes(b"shortcut")
                return subprocess.CompletedProcess(command, 0, "", "")

            result = create_manager_desktop_shortcut(
                application_executable=application,
                desktop_root=desktop,
                runner=runner,
            )

            self.assertEqual(result, desktop / SHORTCUT_NAME)
            self.assertTrue(result.is_file())
            command, options = calls[0]
            self.assertEqual(command[0], "powershell.exe")
            self.assertNotIn(str(application), " ".join(command))
            self.assertEqual(options["env"]["MMM_EXECUTABLE_PATH"], str(application))
            self.assertEqual(
                options["env"]["MMM_WORKING_DIRECTORY"], str(application.parent)
            )
            self.assertTrue(options["capture_output"])

    def test_rejects_missing_application(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ShortcutError, "executable was not found"):
                create_manager_desktop_shortcut(
                    application_executable=root / "missing.exe",
                    desktop_root=root,
                )

    def test_surfaces_hidden_helper_failure(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            application = root / "Majesty Mod Manager.exe"
            application.write_bytes(b"fixture")

            def runner(command, **options):
                return subprocess.CompletedProcess(command, 1, "", "access denied")

            with self.assertRaisesRegex(ShortcutError, "access denied"):
                create_manager_desktop_shortcut(
                    application_executable=application,
                    desktop_root=root,
                    runner=runner,
                )
